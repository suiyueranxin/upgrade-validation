import json
import logging as log
import os
import platform
import re
import subprocess
import sys
import time

import xml.etree.ElementTree as XML
import requests
import urllib3
urllib3.disable_warnings()

from pylibs.logstream import LogStream

# TODO: functions are somewhat inconsistent wrt. error behaviour:
# some return None, some return False, others raise exceptions.

#### reading / parsing common data formats #################################

## XML ####


def parse_xml(url):
    """Parse XML file, ignoring pesky namespaces."""
    output = read_from_url_or_file(url)
    try:
        xml_tree = XML.fromstring(output)
    except XML.ParseError as ex:
        log.error("parsing XML failed for %s: %s", output, ex)
        sys.exit(-1)
    for elem in xml_tree.iter():
        _ns, elem.tag = re.match(r"(\{[^{}]+\})?(.+)", elem.tag).groups()
    return xml_tree


def xml_replace_namespaces(xml_tree, namespace_map):

    def namespace_repl(tag):
        ns, tag = re.match(r"(\{[^{}]+\})?(.+)", tag).groups()
        if ns and ns in namespace_map:
            if namespace_map[ns]:
                return namespace_map[ns] + ":" + tag
            else:
                return tag
        else:
            return ns + tag

    for elem in xml_tree.iter():
        elem.tag = namespace_repl(elem.tag)


def dig_in_xml(url, path, namespace_map={}, firstonly=False):
    """Get the content of an element in an XML file for a given URL."""
    output = read_from_url_or_file(url)
    xml_tree = XML.fromstring(output)
    xml_replace_namespaces(xml_tree, namespace_map)

    if firstonly:
        find_func = xml_tree.find
    else:
        find_func = xml_tree.findall
    if path.endswith("/text()"):
        solutions = find_func(path[:-7])
        if firstonly:
            return solutions.text
        else:
            return [elem.text for elem in solutions]
    else:
        return find_func(path)

## JSON ####


def read_json_from(url):
    """Read JSON string from the given URL / file and return it as a dictionary."""
    output = read_from_url_or_file(url)
    if len(output) == 0 or output[0] != '{':  # check if this is actually JSON
        raise(Exception("Error: no proper JSON found at " + url + ": " + output))
    return json.loads(output)

## Arbitrary text files ####


def read_regex_from(url, regex):
    """Grep-like function. Return all strings matching regex present in URL."""
    output = read_from_url_or_file(url)
    return re.findall(regex, output)

#### Fetching remote files #################################################


ARTIFACTORY_URL = "https://int.repositories.cloud.sap/artifactory/build-milestones/"


def get_github_token():
    return os.getenv("UPGRADE_VALIDATION_GITHUB_TOKEN")


def read_from_url_or_file(url):
    """Return contents of the given URL / file."""
    if url.find("://") != -1:
        # this looks like an URL, so get it with curl
        curl_cmd = ['curl', "-sk", url, "--retry", str(12)]
        if 'github.wdf.sap.corp' in url:
            github_token = get_github_token()
            if github_token:
                curl_cmd.extend(["-u", "di-upgrade-validation-bot:" + github_token])
            else:
                log.warning("GitHub token not found. Using anonymous access!")
        proc = subprocess.Popen(curl_cmd, stdout=subprocess.PIPE)
        output = proc.stdout.read().decode("UTF-8")
    else:
        # regular file, just read it
        output = open(url).read()
    return output


def get_file_from(url, retries=12, auth=None):
    """Download the content from the given url, with optional retries.
    Returns None when the file cannot be downloaded."""
    log.getLogger("requests").setLevel(log.ERROR)  # turn off INFO/DEBUG messages from the requests package
    for i in range(1, retries + 1):
        try:
            req = requests.get(url, verify=False, allow_redirects=True, auth=auth)
            break  # finish if nothing goes wrong
            log.debug("retrying %s", url)
        except requests.exceptions.ConnectionError as e1:
            log.error(e1, exc_info=True)
            if i == retries:
                print("exceeded maximum number of connection error retries (%d)", retries)
                return req.status_code
        except requests.exceptions.Timeout as e2:
            log.error(e2, exc_info=True)
            if i == retries:
                print("exceeded maximum number of timeout error retries (%d)", retries)
                return req.status_code
        time.sleep(10)
    if req.status_code == 404:
        log.error("Download failed: %s not found", url)
        return req.status_code
    req.raise_for_status()
    return req.text


def request_file_from(url, filename, retries=12):
    """Downloads the file from the given url and saves it to filename, with optional retries"""
    text = get_file_from(url, filename, retries)
    if text == None:
        return False
    # write the result to a file
    with open(filename, 'w') as f:
        f.write(text)
    return True


def get_from_github_or_local(repo, path, version, **kwargs):
    """Get the contents of the file under $path from the given repo.
    If a local copy exists under repos/$repo/$path, use that.
    Otherwise, download the file for the given version from corporate github.
    """
    local_dir = kwargs.get("local_dir", "repos")
    full_path = os.path.join(local_dir, repo, path)
    if os.path.isfile(full_path):
        # just assume it's the right version and get the file from local storage
        log.debug("getting file %s from local dir", full_path)
        f = open(full_path)
        return f.read()
    else:
        # not there - fetch it directly from github
        log.debug("fetching %s from github repo %s:%s", path, repo, version)
        return get_from_github(repo, path, version, not_found_ok=True)


def download_repo_from_github(repo, branch, remove_archive=False, outdir=None):
    """Download a repo from corporate github and put it into a matching dir."""
    if not outdir:
        outdir = os.path.join("repos", repo)
    zipfile = "{}-{}.zip".format(outdir.replace('/', '-'), branch)
    url = "https://github.wdf.sap.corp/{}/archive/{}.zip".format(repo, branch)
    if os.path.isdir(outdir):
        log.debug("repository %s is already present, skipping download", repo)
        return outdir

    dbg = open(os.devnull, 'wb')

    # download an archive from github
    if not os.path.isfile(zipfile):
        log.info("downloading repository %s from %s", repo, url)
        curl_cmd = ["curl", "-Lfk", url, "-o", zipfile, "--retry", str(12)]
        github_token = get_github_token()
        if github_token:
            curl_cmd.extend(["-u", "di-upgrade-validation-bot:" + github_token])
        else:
            log.warning("GitHub token not found. Using anonymous access!")
        if subprocess.call(curl_cmd, stderr=dbg) != 0:
            log.fatal("Error fetching branch %s from github: %s", branch, url)
            sys.exit(-1)

    # unzip it into outdir
    log.info("unpacking repository %s to %s", repo, outdir)
    cmd = ["ditto", "-xk", zipfile, "tmp"] if platform.system() == "Darwin" else ["unzip", zipfile, "-d", "tmp"]
    if subprocess.call(cmd, stdout=dbg) != 0:
        log.fatal("error unpacking %s", zipfile)
        sys.exit(-1)
    os.makedirs(outdir)
    os.rename("tmp/" + repo.split('/')[1] + "-" + branch, outdir)

    # remove archive file, if desired
    if remove_archive:
        os.remove(zipfile)
    return outdir


def get_from_github(repo, path, version, not_found_ok):
    """Fetch a file from corporate GitHub and return it as a string."""
    url = "https://github.wdf.sap.corp/raw/{}/{}/{}".format(repo, version, path)
    github_token = get_github_token()
    auth = None
    if github_token:
        auth = requests.auth.HTTPBasicAuth("di-upgrade-validation-bot", github_token)
    else:
        log.warning("GitHub token not found. Using anonymous access!")

    content = get_file_from(url, auth=auth)
    if isinstance(content, str):
        return content
    elif content == 404 and not_found_ok:
        return False
    else:
        raise Exception("Error while downloading " + url + ": " + str(content))


def download_from_artifactory(group, artifact, version, outdir=None):
    """Download an artifact from Artifactory and put it in a directory prefixed by prefix."""
    if not outdir:
        outdir = artifact
    url_base = ARTIFACTORY_URL + group.replace(".", "/") + "/" + artifact + "/" + version + "/"
    url_file = artifact + "-" + version

    log.info("downloading artifact %s:%s from %s", artifact, version, url_base + url_file)
    success = False
    dbg = LogStream(log.debug)

    for suffix in [".zip", ".tar.gz", "-linuxx86_64.zip", "-linuxx86_64.tar.gz"]:
        filename = url_file + suffix
        if subprocess.call(["curl", "-Lfk", url_base + filename, "-o", filename, "--retry", str(12)], stderr=dbg) == 0:
            success = True
            break
    if not success:
        log.warning("cannot download package from %s", url_base + filename)
        return False

    if filename.endswith("tar.gz"):
        if subprocess.call(["tar", "xzf", filename, "--one-top-level=" + outdir], stderr=dbg) != 0:
            log.fatal("error unpacking %s", filename)
            sys.exit(-1)
    elif filename.endswith(".zip"):
        if subprocess.call(["unzip", "-o", filename, "-d", outdir], stdout=dbg) != 0:
            log.fatal("error unpacking %s", filename)
            sys.exit(-1)
    else:
        log.fatal("cannot unpack file %s", filename)
        sys.exit(-1)
    return True


def unpack_file(filename, outdir, make_subdir=False):
    """Unpack an archive (zip, tar.gz) into outdir."""
    # Optionally, create a subdirectory from the given filename.
    if make_subdir:
        if filename.endswith(".tar.gz"):
            outdir += "/" + filename[:-7]
        elif filename.endswith(".zip"):
            outdir += "/" + filename[:-4]

    # No need to unpack if the directory already exists
    if os.path.isdir(outdir):
        log.debug("directory %s already exists, skip unpacking", outdir)
        return outdir

    log.info("unpacking %s to %s", filename, outdir)
    dbg = LogStream(log.debug)
    if filename.endswith("tar.gz"):
        if subprocess.call(["tar", "xzf", filename, "--one-top-level=" + outdir], stderr=dbg) != 0:
            log.fatal("error unpacking %s", filename)
            sys.exit(-1)
    elif filename.endswith(".zip"):
        if subprocess.call(["unzip", "-o", filename, "-d", outdir], stdout=dbg) != 0:
            log.fatal("error unpacking %s", filename)
            sys.exit(-1)
    else:
        log.fatal("cannot unpack file %s", filename)
        sys.exit(-1)

    return outdir


def check_dirs(list_of_dirs):
    """Check if all directories in the list do actually exist."""
    for d in list_of_dirs:
        if not os.path.isdir(d):
            log.fatal("Directory %s does not exist.", d)
            sys.exit(-1)
