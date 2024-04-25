#!/usr/bin/python3

import json
import logging as log
import os
import sys

sys.path.append(sys.path[0] + "/../../")
from pylibs.fileops import download_repo_from_github

if __name__ == '__main__':
    log.basicConfig(level="INFO", format="%(levelname)-7s %(message)s")
    branch = "master"
    specs = json.load(open("swagger_specs.json"))
    files = {}
    dirs = {}
    for repo in specs["repositories"]:
        if not repo["swaggerFiles"] or len(repo["swaggerFiles"]) == 0:
            continue
        repo_path = download_repo_from_github(repo["name"], branch)
        for spec_file in repo["swaggerFiles"]:
            spec_dir = os.path.dirname(spec_file)
            files[os.path.join(repo["name"], spec_file)] = os.path.join(repo_path, spec_file)
            dirs[os.path.join(repo["name"], spec_dir)] = os.path.join(repo_path, spec_dir)

    log.info("Checking existence of registered specifications in branch '%s'", branch)
    for spec_file in files:
        if not os.path.isfile(files[spec_file]):
            log.warning("Specification not found: %s", spec_file)

    log.info("Searching for new specifications in branch '%s'", branch)
    for spec_dir in dirs:
        for dirpath, _, file_names in os.walk(dirs[spec_dir]):
            repo_dirpath = dirpath[dirpath.find(spec_dir):]
            for f in file_names:
                spec_file = os.path.join(repo_dirpath, f)
                if spec_file.endswith(".yaml") and spec_file not in files:
                    log.warning("New specification found: %s", spec_file)
