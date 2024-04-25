#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging as log
import os
import re
import sys
import yaml

sys.path.append(sys.path[0] + "/../")
from pylibs.fileops import read_from_url_or_file, read_json_from, read_regex_from, parse_xml, get_from_github

ARTIFACTORY_URL = "https://int.repositories.cloud.sap/artifactory/build-releases/com/sap/datahub/SAPDataHub/"
ARTIFACTORY_REL_URL = "https://int.repositories.cloud.sap/artifactory/build-milstones/com/sap/hana/hl/linuxx86_64/"
VSOLUTION_URL = "https://github.wdf.sap.corp/raw/velocity/vsolution/rel/"

COMPONENTS = ["RELEASEPACK", "VSYSTEM", "HANALITE", "STORAGEGATEWAY", "DIAGNOSTICS",
              "VFLOW", "AXINO", "FLOWAGENT", "CODE_SERVER", "APP_BASE", "APP_DATA",
              "ML_API", "ML_DM_API", "ML_TRACKING", "FEDERATION", "RMS"]


def is_version_str(s):
    """Find out whether a string is a version number."""
    if re.search("^[0-9]+\\.[0-9]+\\.[0-9]+(-ms)?(-dis\\.[0-9]+)?$", s):
        return True
    return False


def is_branch_str(s):
    """Find out whether a string is a common DI branch name (NOT a version tag)."""
    return s in [ "master", "stable" ] or s.startswith("rel-")


def version_to_tag(version):
    """Get the git tag corresponding to a version number, .e.g. 2005.1.1 -> rel/2005.1.1"""
    if is_version_str(version):
        return "rel/{}".format(version)
    return version


def tag_to_version(s):
    """Get the version number from a release tag, e.g. rel/2005.1.1 -> 2005.1.1."""
    match = re.search("^rel\\/([0-9]+\\.[0-9]+\\.[0-9]+)$", s)
    if match:
        return match.group(1)
    return None


def get_proper_version(base_path, version):
    """Return a proper version number for the given path/version.
    If version_name is a proper version name, just return that.
    Otherwise, assume that base_path contains a github revision and get the version from cfg/VERSION.
    NB: This is not an accurate version number, since not every branch has an exact version number.
    It is rather a "minimum version number", which might contain any number of changes made after the
    last increase of the version number in cfg/VERSION. """
    if re.match(r"^[0-9.]+$", version):
        return version
    else:
        for path, subdirs, subfiles in os.walk(base_path):
            if path.endswith("/cfg") and "VERSION" in subfiles:
                return open(path + "/VERSION", 'r').read().rstrip()

    # Fail if it neither looks like a proper version number, nor has no cfg/VERSION file
    log.fatal("could not find proper version number for %s in %s", version, base_path)
    sys.exit(-1)


def version_kind(version):
    """Determines the kind of version:
    - "onprem" (e.g. 2.7.8)
    - "cloud" (e.g. 2004.1.2)
    """
    if re.match(r"^[0-9]{4}\..*", version):
        return "cloud"
    elif re.match(r"^[0-9]{1,2}\..*", version):
        return "onprem"
    return None


def version_leq(vstr1, vstr2):
    """Compare two version strings and return true if str1 <= str2.
    NB: returns None if two version strings are incomparable, i.e. one is an
    on-prem version (e.g. 2.7.4) and the other a cloud version (e.g. 2004.1.2).
    """

    # convert release tags to version numbers
    if tag_to_version(vstr1):
        vstr1 = tag_to_version(vstr1)
    if tag_to_version(vstr2):
        vstr2 = tag_to_version(vstr2)

    # check version format
    if not is_version_str(vstr1):
        raise RuntimeError("Unrecognized version format: " + vstr1)
    if not is_version_str(vstr2):
        raise RuntimeError("Unrecognized version format: " + vstr2)
    
    ver1 = [int(v) for v in vstr1.split(".")]
    ver2 = [int(v) for v in vstr2.split(".")]

    # take care not to compare short (e.g. 2.7.xy) with Takt (e.g. 2007.x.y) versions
    if ver1[0] <= 99 and ver2[0] <= 99:
        return ver1 <= ver2  # both primary version numbers are short -- okay
    if ver1[0] >= 1000 and ver2[0] >= 1000:
        return ver1 <= ver2  # both primary version numbers are Takt versions -- okay
    return None  # no meaningful comparison possible, return None


def get_releasepack_versions(branch):
    """Get all relevant releases for the given branch of _upgrade-validation_."""
    version_info = "/infrabox/context/deps/upgrade_multi_base_version.json"
    if not os.path.isfile(version_info):
        version_info = "https://github.wdf.sap.corp/raw/bdh/upgrade-validation/{}/deps/upgrade_multi_base_version.json".format(branch)
    log.info("Using base versions from %s", version_info)
    try:
        releasepack_json = read_json_from(version_info)
    except Exception as ex:
        log.error("Getting version info from %s failed: %s.", version_info, ex)
        sys.exit(2)
    versions = []
    for tag in ['BASE_BDH_VERSION', 'BASE_DIS_VERSION']:
        for rel in releasepack_json.get(tag, []):
            versions.append(rel['version'])
    return versions


def get_versions(component):
    """Get vflow-base versions for all upgrade-relevant releasepack versions."""
    version_list = set()
    for base_version in get_releasepack_versions():
        pom_xml = parse_xml(ARTIFACTORY_URL + base_version + "/SAPDataHub-" + base_version + ".pom")
        rel = pom_xml.find("./properties/hldep." + component + ".version").text
        vsolution = read_json_from(VSOLUTION_URL + rel + "/deps/vflow.dep")
        version_list.add(str(vsolution['VERSION']))
    return sorted(version_list)


# # TODO: pythonify (cf. get_versions() above)
def get_vsolution_version(vsolution_version, repo, component):
    log.debug("Retrieving %s version from repo %s", component, repo)
    vsolution_dep_url = "https://github.wdf.sap.corp/raw/{r}/rel/{v}/deps/{c}.dep".format(r=repo, v=vsolution_version, c=component)
    bare_version = read_json_from(vsolution_dep_url)['VERSION']
    return "rel/" + bare_version


def get_dep_version(pom_url, dep):
    """Get version of given dependency from a POM file (Maven XML) on Artifactory."""
    log.debug("Retrieving %s version from %s", dep, pom_url)
    xml = parse_xml(pom_url)
    return xml.find("properties/hldep." + dep + ".version").text


def get_dis_version(rversion, component):
    """Get version of given DI Embedded component. See version info at https://github.wdf.sap.corp/bdh/dis-release/blob/master/dis-versions.yaml"""
    version_info = "https://github.wdf.sap.corp/raw/bdh/dis-release/master/dis-versions.yaml"
    log.debug("Using base versions from %s", version_info)
    try:
        dis_versions_json = yaml.safe_load(read_from_url_or_file(version_info))
    except Exception as ex:
        log.error("Getting version info from %s failed: %s.", version_info, ex)
        sys.exit(2)
    if rversion not in dis_versions_json:
        log.error("Unknown DIS release version: %s", rversion)
        sys.exit(3)
    if component not in dis_versions_json[rversion]:
        log.error("Component not found in DIS release: %s, DIS release version %s", component, rversion)
        sys.exit(4)
    return dis_versions_json[rversion][component]


def get_newest_release():
    version_string = read_regex_from(ARTIFACTORY_URL + "maven-metadata.xml", r"<version>(.*)</version>")
    version_list = [v for v in version_string]
    return sorted(version_list)[-1]


def get_newest_milestone(artifact):
    version_string = read_regex_from(ARTIFACTORY_REL_URL + artifact + "/", r"<text>(.*)</text>")
    log.debug("getting newest milestones from %s: %s",
              ARTIFACTORY_REL_URL + artifact + "/", version_string)
    version_list = [v for v in version_string]
    return sorted(version_list)[-1]


def get_component_version(repo, branch):
    """Given a repository / component and a branch, return the component's version."""
    if is_version_str(branch):
        return branch
    version = tag_to_version(branch)
    if version:
        return version
    version = get_from_github(repo, "cfg/VERSION", branch, not_found_ok=False).strip()
    if version == "../VERSION":  # needed for velocity/axino
        version = get_from_github(repo, "VERSION", branch, not_found_ok=False).strip()
    return version


def parse_options(parser):
    """Parse command line options for use from shell."""
    parser.set_defaults()
    parser.add_argument('--component',
                        help="Component to get version for. One of {}.".format(COMPONENTS))
    parser.add_argument('--branch', help="Branch to get component versions for")
    parser.add_argument('--base-version', help="Base version to get component versions for")
    parser.add_argument('--log-level', default='INFO',
                        help="Level of logging. One of ERROR, WARNING, INFO, or DEBUG")

    # parse and check options
    options = parser.parse_args()
    if not options.component:
        print("#### [level=error] COMPONENT variable is not set, e.g. --component=VFLOW.")
        print("Supported components: {} (or the corresponding repository names).".format(COMPONENTS))
        sys.exit(-1)
    if not options.branch and not options.base_version:
        print("### [level=error] One of --branch or --base-version must be set.")
        sys.exit(-1)

    return options


def handle_component(component, rversion):
    """Get version for given component and release version."""
    pom_url = "https://int.repositories.cloud.sap/artifactory"
    if rversion.endswith("-ms"):
        pom_url += "/deploy-milestones/"
    else:
        pom_url += "/build-releases/"
    pom_url += "com/sap/datahub/SAPDataHub/{v}/SAPDataHub-{v}.pom".format(v=rversion)

    is_dis = "-dis." in rversion

    if component in [ "RELEASEPACK" ]:
        return rversion

    # Main vsolutions
    elif component in [ "VFLOW", "velocity/vflow" ]:
        dep_version = get_dis_version(rversion, "vsolution") if is_dis else get_dep_version(pom_url, "hl-vsolution") 
        return get_vsolution_version(dep_version, "velocity/vsolution", "vflow")
    elif component in [ "VFLOW_SUB_ABAP", "velocity/vflow-sub-abap" ]:
        dep_version = get_dis_version(rversion, "vsolution") if is_dis else get_dep_version(pom_url, "hl-vsolution")
        return get_vsolution_version(dep_version, "velocity/vsolution", "vflow-sub-abap")
    elif component in [ "AXINO", "velocity/axino" ]:
        dep_version = get_dis_version(rversion, "vsolution") if is_dis else get_dep_version(pom_url, "hl-vsolution")
        return get_vsolution_version(dep_version, "velocity/vsolution", "axino")

    # Machine learning
    elif component in [ "ML_API", "dsp/ml-api" ]:
        if is_dis:
            return None
        dep_version = get_dep_version(pom_url, "dsp-release")
        return get_vsolution_version(dep_version, "dsp-release", "dsp/dsp-release", "ml-api")
    elif component in [ "ML_DM_API", "dsp/ml-dm-api" ]:
        if is_dis:
            return None
        dep_version = get_dep_version(pom_url, "dsp-release")
        return get_vsolution_version(dep_version, "dsp/dsp-release", "ml-dm-api")
    elif component in [ "ML_TRACKING", "dsp/ml-tracking" ]:
        if is_dis:
            return None
        dep_version = get_dep_version(pom_url, "dsp-release")
        return get_vsolution_version(dep_version, "dsp/dsp-release", "ml-tracking")
    elif component in [ "DSP_GITSERVER", "dsp/dsp-gitserver" ]:
        if is_dis:
            return None
        dep_version = get_dep_version(pom_url, "dsp-release")
        return get_vsolution_version(dep_version, "dsp/dsp-release", "dsp-git-server")

    # Main components
    elif component in [ "APP_BASE", "bdh/datahub-app-base" ]:
        return get_dis_version(rversion, "datahub-app-base") if is_dis else get_dep_version(pom_url, "datahub-app-base")
    elif component in [ "APP_DATA", "bdh/datahub-app-data" ]:
        if is_dis:
            return None
        major_version = int(rversion.split('.')[0])
        if major_version == 2 or (major_version > 1900 and major_version < 2003):
            log.error("## The datahub-app-data version is not available in " + pom_url + ". Please request version of the APP_BASE.")
            return "0"
        else:
            return get_dep_version(pom_url, "datahub-app-data")
    elif component in [ "HANALITE" ]:
        if is_dis:
            return None
        return get_dep_version(pom_url, "hl-lib")
    elif component in [ "VSYSTEM", "velocity/vsystem" ]:
        return get_dis_version(rversion, "vsystem") if is_dis else get_dep_version(pom_url, "hl-vsystem")
    elif component in [ "STORAGEGATEWAY", "bigdataservices/storagegateway" ]:
        return get_dis_version(rversion, "storagegateway") if is_dis else get_dep_version(pom_url, "storagegateway")
    elif component in [ "FLOWAGENT", "bdh/datahub-flowagent" ]:
        return get_dis_version(rversion, "datahub-flowagent") if is_dis else get_dep_version(pom_url, "datahub-flowagent")
    elif component in [ "DQ_INTEGRATION", "bdh/datahub-dq-integration" ]:
        dep_version = get_dis_version(rversion, "datahub-flowagent") if is_dis else get_dep_version(pom_url, "datahub-flowagent")
        flowagent_tag = version_to_tag(dep_version)
        flowagent_pom_url = "https://github.wdf.sap.corp/raw/bdh/datahub-flowagent/" + flowagent_tag + "/build/parent/pom.xml"
        return get_dep_version(flowagent_pom_url, "datahub-dq-integration")
    elif component in [ "DIAGNOSTICS", "bdh/diagnostics" ]:
        return get_dis_version(rversion, "diagnostics") if is_dis else get_dep_version(pom_url, "diagnostics")
    elif component in [ "CODE_SERVER", "velocity/code-server" ]:
        if is_dis:
            return None
        return get_dep_version(pom_url, "code-server")
    elif component in [ "CCM", "orca/connection-service" ]:
        return get_dis_version(rversion, "connection-service") if is_dis else None
    elif component in ["FEDERATION", "bdh/federation"]:
        return get_dis_version(rversion, "federation-service") if is_dis else None
    elif component in ["RMS", "bdh/rms"]:
        return get_dis_version(rversion, "rms") if is_dis else None
    else:
        log.fatal("Unsupported component name: %s", component)
        sys.exit(3)


class VersionCollector():
    """Collects base and target versions for components based on repository metadata."""

    def __init__(self, repo, base_version, target_version, test_flag, test_entries, test_all, logger, repo_config="swagger_specs.json"):
        self.logger = logger

        # Load repository / specification metadata
        self.specs = json.load(open(repo_config))

        # Initialize list of test parameters. If the test_entries parameter (string) is set,
        # each entry is a string consisting of three parts separated by semicolon:
        # 1. Repository
        # 2. Test entry, e.g. a file inside the repository
        # 3. Base version
        # If test_entries is None or empty, the entries consist only of two entries
        # (the test entries are skipped).
        #
        # Component target versions and exceptions are stored in a separate map.

        self.tests = []
        self.repositories = []
        self.component_target_versions = {}
        self.fork = None

        logger.info(u'Collecting component versions \U0001F37A')

        # We allow custom base versions (specified in repository metadata) only if it
        # is not enforced by a command-line argument.
        self.allow_custom_base_versions = not base_version

        if repo:
            # CASE 1) ONE repository
            self.init_single_repo(repo, base_version, target_version, test_flag, test_entries)
        else:
            # CASE 2) ALL repositories
            self.init_all_repos(base_version, target_version, test_flag, test_entries, test_all)    
        return

    def init_single_repo(self, repo, base_version, target_version, test_flag, test_entries):
        """Initialize test cases for a single repository."""

        # Find repository in metadata
        repo_details = [r for r in self.specs["repositories"] if r["name"] == repo]

        # If the repository was not found, check if it is a fork
        if not repo_details:
            _, repo_short = repo.split("/")
            for r in self.specs["repositories"]:
                if r["name"].endswith("/" + repo_short):
                    self.logger.info("Repository '%s' is a fork of '%s'", repo, r["name"])
                    self.fork = repo
                    repo = r["name"]
                    repo_details = [ r ]
                    repo_details[0]["fork"] = self.fork
                    break

        # Check if the repository was found and is unique
        if len(repo_details) != 1:
            raise RuntimeError("Repository not found: " + repo)
        the_repo = repo_details[0]

        # Check if the test flag is set for this repository
        if the_repo.get(test_flag, True) == False:
            return

        # If the base version is not set explicitly, we need to get the releasepack base versions
        if not base_version:
            # We always get the base versions from the master branch of the upgrade-validation repository.
            # To ensure that the used base versions are not "too new", we later compare the version numbers
            # of the components.
            self.releasepack_base_versions = get_releasepack_versions("master")

        # Add tests for this repository (component) only.
        # Component target version is already given by the argument
        self.do_init_repo_tests(the_repo, base_version, target_version, test_entries)

    def init_all_repos(self, base_version, target_version, test_flag, test_entries, test_all):
        """Initialize test cases for all registered repositories."""

        # Base version now refers to the releasepack version
        if base_version:
            self.releasepack_base_versions = [base_version]
            base_version = None
        else:
            # See comment above regarding master branch
            self.releasepack_base_versions = get_releasepack_versions("master")

        # Add tests for all repos
        for r in self.specs["repositories"]:
            if (test_all or r.get(test_flag, True) == True) and (not test_entries or r.get(test_entries, False)):

                # Get component target version
                if is_branch_str(target_version):
                    tv = target_version
                elif is_version_str(target_version):
                    # Interpreting version as releasepack milestone -> get corresponding component version
                    tv = handle_component(r["name"], target_version)
                    if not tv:
                        self.logger.info("No component version found for '{}' in release {}".format(r["name"], target_version))
                    elif tag_to_version(tv):
                        tv = tag_to_version(tv)
                else:
                    raise RuntimeError("Target version is neither branch name nor version: " + target_version)

                # Add tests cases
                if tv:
                    self.do_init_repo_tests(r, base_version, tv, test_entries)

    def do_init_repo_tests(self, repo_details, base_version, target_version, test_entries):
        """Find out base and target version for a specific repository and add test case to self.tests"""

        # Get repository name
        if "name" not in repo_details:
            raise RuntimeError("Invalid repository specification: {}".format(repo_details))
        repo = repo_details["name"]

        # Add to list of checked repositories
        self.repositories.append(repo)

        # Get component base versions
        if self.allow_custom_base_versions and "baseVersions" in repo_details:
            component_base_versions = repo_details["baseVersions"]
        else:
            if base_version:
                component_base_versions = [base_version]
            else:
                component_base_versions = set()
                for rversion in self.releasepack_base_versions:
                    v = handle_component(repo, rversion)
                    if v:
                        component_base_versions.add(v)

                component_base_versions = sorted(component_base_versions)

        # The version could be git branches, tags or a commit ids.
        # We now get corresponding component versions the tag or from cfg/VERSION.
        r = repo_details.get("fork", repo)
        cfg_base_versions = [ get_component_version(r, v) for v in component_base_versions]
        cfg_target_version = get_component_version(r, target_version)

        # Now we need to compare the base versions to the target version.
        # We need to make sure the base version is predecessor of the target version.
        # If two versions are not comparable "version_leq()" will return "none".
        filtered_base_versions = [v for v in cfg_base_versions if version_leq(v, cfg_target_version) == True ]
        if not filtered_base_versions:
            msg = "Skipping tests because base versions are not predecessors of target version: {} -> {}"
            self.logger.warn(msg.format(cfg_base_versions, cfg_target_version))
            return

        self.logger.info(" * '%s': %s -> '%s'", repo, filtered_base_versions, target_version)

        # Generate tests based on specifications list
        if test_entries:
            if test_entries in repo_details:
                for entry in repo_details[test_entries]:
                    for version in filtered_base_versions:
                        self.tests.append("{};{};{}".format(repo, entry, version_to_tag(version)))
        else:
            for version in filtered_base_versions:
                self.tests.append("{};{}".format(repo, version_to_tag(version)))

        # Set target version
        self.component_target_versions[repo] = version_to_tag(target_version)
        return


if __name__ == '__main__':
    options = parse_options(argparse.ArgumentParser())
    log.basicConfig(level=options.log_level, format="%(levelname)-7s %(message)s")

    if options.base_version:
        base_releasepack_versions = [options.base_version]
    else:
        base_releasepack_versions = get_releasepack_versions(options.branch)

    versions = set()
    for releasepack_version in base_releasepack_versions:
        v = handle_component(options.component, releasepack_version)
        if v:
            versions.add(v)

    for version in sorted(versions):
        print(version)
