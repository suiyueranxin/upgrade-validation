#!/usr/bin/python3

import argparse
import csv
import logging as log
import os
import re
import subprocess
import sys
import time
import requests

sys.path.append(sys.path[0] + "/../../")
from pylibs.fileops import parse_xml, read_json_from, unpack_file
from pylibs.logstream import LogStream


# List of components within a release to check for Dockerfiles
COMPONENTS = ['vrelease_delivery_di',
              'datahub-app-base-vsolution',
              'datahub-app-base-vsolution-bundle',
              'datahub-app-data-vsolution',
              'flowagent-vsolution']


class Diff:
    __change_kinds__ = ["changed-type", "changed-entry", "added-entry", "removed-entry", "added-file", "removed-file"]
    def __init__(self, kind, path, entry_old, entry_new):
        self.kind = kind
        self.path = path
        self.entry_old = entry_old
        self.entry_new = entry_new
    def __str__(self):
        return self.kind + ":" + "/".join([str(k) for k in self.path]) + " from " + self.entry_old + " to " + self.entry_new


def download_release_file(component, release_version):
    """Download the given component for the given release version from Artifactory."""
    build_type = "milestones" if release_version.endswith("-ms") else "releases"
    POM_BASE = "https://int.repositories.cloud.sap/artifactory/build-" + build_type + "/com/sap/datahub/SAPDataHub/"
    try:
        pom_xml = parse_xml(POM_BASE + release_version + "/SAPDataHub-" + release_version + ".pom")
    except:
        log.fatal("version not found: %s", release_version)
        return ""

    ## print("find", component, "in", [x.text for x in pom_xml.findall("dependencies/dependency/artifactId")])
    dep = pom_xml.find("dependencies/dependency[artifactId='" + component + "']")
    if dep is None:
        return (None, None)

    version = dep.find("version").text
    if version.startswith("${"):
        version = pom_xml.find("properties/" + version[2:-1]).text
    filename = component + "-" + version
    filename += "-" + dep.find("classifier").text if dep.find("classifier") is not None else ""
    filename += "." + dep.find("type").text if dep.find("type") is not None else ".zip"
    url = "https://int.repositories.cloud.sap/artifactory/build-" + build_type + "/"
    url += dep.find("groupId").text.replace(".", "/") + "/"
    url += component + "/"
    url += version + "/" + filename

    if not os.path.exists("components/"):
        os.mkdir("components/")
    filename_out = "components/" + filename
    if not os.path.exists(filename_out):
        log.info("downloading %s", url)
        dbg = LogStream(log.debug)
        if subprocess.call(["curl", "-Lfk", url, "-o", filename_out, "--retry", str(12)], stderr=dbg) != 0:
            log.fatal("cannot download package from %s", url)
            sys.exit(-1)
    return (filename_out, version)


def find_dockerfiles_in(component_path):
    """Find all Dockerfiles (with accompanying Tags.json) in the given path."""
    dockerfiles = []
    prefix_len = len(component_path) + 1
    for path, subdirs, subfiles in os.walk(component_path):
        if "Dockerfile" in subfiles and "Tags.json" in subfiles:
            dockerfiles.append(path[prefix_len:] + "/")
    return dockerfiles


def diff_docker(path, base_dir, target_dir):
    """Find all differences between a Dockerfile in versions $base and $target.
    Includes the metadata in the accompanying Tags.json."""
    base_path = base_dir + "/" + path
    target_path = target_dir + "/" + path
    if not os.path.isfile(base_path + "Dockerfile") and os.path.isfile(target_path + "Dockerfile"):
        return [Diff("added-file", path, {}, {})]
    if os.path.isfile(base_path + "Dockerfile") and not os.path.isfile(target_path + "Dockerfile"):
        return [Diff("removed-file", path, {}, {})]


    log.debug("comparing %s, versions %s and %s", path,
              base_dir[base_dir.find("-")+1:], target_dir[target_dir.find("-")+1:])
    base_docker = parse_dockerfile(open(base_path + "Dockerfile", 'r').read())
    target_docker = parse_dockerfile(open(target_path + "Dockerfile", 'r').read())
    diff = diff_tree(base_docker, target_docker)

    base_meta = read_json_from(base_path + "Tags.json")
    target_meta = read_json_from(target_path + "Tags.json")
    diff += diff_tree(base_meta, target_meta, ["Tags"])

    # set kind to "deprecated" if the "deprecated" tag is added
    for d in [d for d in diff if d.kind == "added-entry" and "deprecated" in d.path]:
        d.kind = "deprecated"

    return diff


def parse_dockerfile(text):
    """Parse a Dockerfile into a dict and perform basic sanity checks."""
    # single instructions should appear at most once in a Dockerfile, multi instructions many times.
    SINGLE_INSTRUCTIONS = ["FROM", "MAINTAINER", "CMD", "ENTRYPOINT", "USER", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK", "SHELL"]
    MULTI_INSTRUCTIONS = ["RUN", "LABEL", "EXPOSE", "ENV", "ADD", "COPY", "VOLUME", "WORKDIR", "ARG"]
    dockerfile = {}

    # pre-parse
    text2 = ""
    for line in text.split("\n"):
        if re.match("^ *#", line) or re.match(r"^ *$", line):
            # ignore comments and empty lines
            continue
        elif re.search(r"\\ *$", line):
            # merge lines ending with backslash
            text2 += line[0:-2] + " \\n"
        else:
            text2 += line+"\n"
    text2 = text2[0:-1] # chomp trailing newline

    # actual parsing of instructions
    for line in text2.split("\n"):
        instruction, _, args = line.partition(" ")
        if instruction in SINGLE_INSTRUCTIONS:
            if instruction in dockerfile:
                log.warning("Multiple definition of %s: %s vs %s",
                            instruction, dockerfile[instruction], args)
                if instruction == "FROM":
                    log.warning("Multiple FROMs are deprecated, see %s",
                                "https://github.com/moby/moby/issues/13026")
            dockerfile[instruction] = args
        elif instruction in MULTI_INSTRUCTIONS:
            if not instruction in dockerfile:
                dockerfile[instruction] = []
            dockerfile[instruction].append(args)
        else:
            dockerfile[instruction] = args
            log.warning("Unknown Dockerfile instruction %s", instruction)
        if instruction == "MAINTAINER":
            log.warning("MAINTAINER is deprecated, use 'LABEL maintainer=a@b.c' instead (see %s)",
                        "https://docs.docker.com/engine/reference/builder/#maintainer-deprecated")

    return dockerfile


def diff_tree(tree1, tree2, path=[]):
    """Calculate the difference between two tree-shaped dicts."""
    diff = []
    if type(tree1) != type(tree2):
        diff.append(Diff("changed-type", path, tree1, tree2))
        return diff
    if isinstance(tree1, dict):
        for k in set(tree1.keys()) | set(tree2.keys()):
            if not k in tree1:  # key in tree2 but not in tree1 ==> inserted in tree2
                diff.append(Diff("added-entry", path + [k], None, tree2[k]))
            elif not k in tree2:  # key in tree1 but not in tree2 ==> deleted from tree2
                diff.append(Diff("removed-entry", path + [k], tree1[k], None))
            else:
                diff += diff_tree(tree1[k], tree2[k], path + [k])
    elif isinstance(tree1, list):
        for i in range(0, min(len(tree1), len(tree2))):
            diff += diff_tree(tree1[i], tree2[i], path + [i])
        if len(tree1) < len(tree2):
            diff.append(Diff("added-entry", path, None, tree2[len(tree1):]))
        elif len(tree1) > len(tree2):
            diff.append(Diff("removed-entry", path, tree1[len(tree2):], None))
    else:
        if tree1 != tree2:
            diff.append(Diff("changed-entry", path, tree1, tree2))
    return diff


def parse_options(parser):
    """Parse command line options."""
    parser.set_defaults()
    parser.add_argument('--csv', required=True,
                        help="Path of CSV file to write to.")
    parser.add_argument('--base', required=True,
                        help="Version to upgrade from. Either a milestone version number or a git refspec.")
    parser.add_argument('--target', required=True,
                        help="Version to upgrade to. Either a milestone version number or a git refspec.")
    parser.add_argument('--log-level', default='INFO',
                        help="Level of logging. One of ERROR, WARNING, INFO, or DEBUG")
    return parser.parse_args()


def generate_csv(csv_writer, component, rversion_base, rversion_targ):
    """Generate a CSV file listing all the differences in Dockerfiles between two release versions."""

    global diff_counter

    outfile_base, cversion_base = download_release_file(component, rversion_base)
    if outfile_base is None:
        log.warning("artifact Id %s not found in release %s", component, rversion_base)
        return None
    outfile_targ, cversion_targ = download_release_file(component, rversion_targ)
    if outfile_targ is None:
        log.warning("artifact Id %s not found in release %s", component, rversion_targ)
        return None

    outdir_base = unpack_file(outfile_base, ".", make_subdir=True)
    outdir_targ = unpack_file(outfile_targ, ".", make_subdir=True)

    dockerfiles = find_dockerfiles_in(outdir_base)
    dockerfiles += [d for d in find_dockerfiles_in(outdir_targ) if d not in dockerfiles]

    if not dockerfiles:
        log.warning("no dockerfiles in %s", component)

    for dockerfile in dockerfiles:
        diff = diff_docker(dockerfile, outdir_base, outdir_targ)
        if diff:
            log.info("Differences found in %s: %s", component, dockerfile)
        for d in diff:
            # csv_writer will escape any ',' in the entries
            if isinstance(d.path, list):
                path_str = "/".join([str(k) for k in d.path])
            else:
                path_str = d.path
            prefix_len = len("content/files/")
            csv_writer.writerow([component, cversion_base, cversion_targ,
                                 d.kind, dockerfile[prefix_len:], path_str,
                                 d.entry_old, d.entry_new])
            diff_counter += 1


diff_counter = 0
if __name__ == '__main__':
    options = parse_options(argparse.ArgumentParser())
    log.basicConfig(level=options.log_level, format="%(levelname)-7s %(message)s")

    csv_writer = csv.writer(open(options.csv, "w"))
    csv_writer.writerow(["component", "base", "target", "kind", "file", "treepath", "from", "to"])

    for comp in COMPONENTS:
        generate_csv(csv_writer, comp, options.base, options.target)
    log.info("Found %d differences. Saving report in %s", diff_counter, options.csv)
