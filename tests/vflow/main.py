#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import io
import json
import logging as log
import os
import re
import sys
import pytest

sys.path.append(sys.path[0] + "/../../")
from pylibs.fileops import check_dirs, download_repo_from_github, download_from_artifactory
from pylibs.versioning import get_proper_version, tag_to_version, version_kind, VersionCollector
from fix import load_fixes
from deprecation import check_deprecation, check_operator_removal
from op_ioports import check_ioports
from op_properties import check_properties

README_URL = "https://github.wdf.sap.corp/bdh/upgrade-validation/blob/master/tests/vflow/README.md"


def parse_options(parser):
    """Parse command line options."""
    parser.set_defaults()
    parser.add_argument('--solution', dest='solution',
                        help="Solution to test. Available solutions are defined in solutions.json")
    parser.add_argument('--old-version', dest='old_version',
                        help="Version to upgrade from. Either a milestone version number or a git refspec.")
    parser.add_argument('--new-version', dest='new_version', default="master",
                        help="Version to upgrade to. Either a milestone version number or a git refspec.")
    parser.add_argument('--log-level', dest='log_level', default='INFO',
                        help="Level of logging. One of ERROR, WARNING, INFO, or DEBUG")
    parser.add_argument('--Wdeprecation', action='store_true', dest='warn_depr',
                        help="Warn of missing fields for deprecated operators")
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help="Verbose output for property changes")
    parser.add_argument("-x", nargs="?", dest="xml",
                        help="path for xml test report")
    return parser.parse_args()


def prepare_vflow_files(version, prefix, solution):
    """Download files for the given version and unpack them in a directory prefixed by prefix."""
    outdir = prefix + version
    if os.path.isdir(outdir):  # do nothing if it's already there
        return outdir

    if re.match(r"^[0-9.]+$", version):
        okay = download_from_artifactory(solution['group'], solution['artifact'], version, outdir)
        if not okay:
            download_repo_from_github(solution['repository'], "rel/" + version, outdir=outdir)
    else:
        download_repo_from_github(solution['repository'], version, outdir=outdir)

    return outdir


def find_vflow_dir(base_path, candidates):
    """Find the directory containing operators, given a base path and a list of candidates."""
    for path in candidates:
        full_path = base_path + "/" + path + "/"
        if os.path.isdir(full_path) and os.path.isdir(full_path + "/operators"):
            return full_path
    raise Exception("could not find vflow operator directory in " + base_path)


if __name__ == '__main__':
    options = parse_options(argparse.ArgumentParser())
    log.basicConfig(level=options.log_level,
                    format="%(levelname)-7s %(message)s")
    rootlog = log.getLogger()
    errlog = log.StreamHandler(io.StringIO())
    errlog.setLevel(log.ERROR)
    errlog.setFormatter(log.Formatter("%(levelname)-7s: %(message)s"))
    rootlog.addHandler(errlog)
    pytest.options = options
    pytest.errlog = errlog

    # load solution metadata
    pytest.solutions = None
    with open("../vflow/solutions.json") as f:
        pytest.solutions = [sol for sol in json.load(f)['solutions'] if sol.get('check_operators') == True]
    if not pytest.solutions:
        log.fatal("solutions metadata not found")
        sys.exit(-1)

    # collect version info and create test cases
    collector = VersionCollector(options.solution, options.old_version, options.new_version,
                                 "checkOperators", None, False, rootlog, repo_config="../api/swagger_specs.json")
    pytest.tests = collector.tests
    pytest.component_target_versions = collector.component_target_versions

    # run pytest
    main_args = ['--color=yes', '-s', '-v', os.path.abspath(__file__)]
    if options.xml:
        main_args.extend(["--junitxml={}".format(options.xml),
                          "-o", "junit_family=xunit2", "-o", "junit_suite_name=test_operators"])
    log.info("See %s for test documentation.", README_URL)
    exit_code = pytest.main(args=main_args)
    sys.exit(exit_code)


def pytest_generate_tests(metafunc):
    """Instantiate test_operators for solution and old version number."""
    if "test" in metafunc.fixturenames:
        metafunc.parametrize('test', pytest.tests)


def test_operators(test):
    # TODO: generate individual tests for each operator

    # get solution name and versions from test arguments
    solution_name, old_version = test.split(";")
    new_version = pytest.component_target_versions[solution_name]

    # find solutions metadata
    solution = next((s for s in pytest.solutions if s['repository'] == solution_name or s['artifact'] == solution_name), None)
    if not solution:
        pytest.fail("Solution not found: %s", solution_name)
    solution['name'] = solution["repository"].split('/')[1]

    # convert tags to version numbers
    if tag_to_version(old_version):
        old_version = tag_to_version(old_version)
    if tag_to_version(new_version):
        new_version = tag_to_version(new_version)

    log.info("comparing %s %s with %s", solution['name'], old_version, new_version)

    prefix = solution['name'] + "-"
    dir_old = find_vflow_dir(prepare_vflow_files(old_version, prefix, solution), solution['operator-dirs'])
    dir_new = find_vflow_dir(prepare_vflow_files(new_version, prefix, solution), solution['operator-dirs'])
    check_dirs([dir_old, dir_new])

    # For branches, these version numbers are not accurate. (see docstring of
    # get_proper_version). Still, they are needed for determining the relevance of fixes.
    old_version_number = get_proper_version(prefix + old_version, old_version)
    new_version_number = get_proper_version(prefix + new_version, new_version)

    if version_kind(old_version_number) == "onprem" and version_kind(new_version_number) != "onprem":
        new_version_number = "99.99.999"
    if version_kind(old_version_number) == "cloud" and version_kind(new_version_number) != "cloud":
        new_version_number = "9999.99.999"

    load_fixes("../vflow/fixed.json", old_version_number, new_version_number)

    options = pytest.options
    settings_path = solution.get('settings-path')
    error_count = 0

    operator_blacklist = solution.get('operator-blacklist') or []
    error_count += check_operator_removal(dir_old, dir_new, settings_path, operator_blacklist)
    error_count += check_ioports(dir_old, dir_new, settings_path)
    error_count += check_properties(dir_old, dir_new, options, settings_path)
    error_count += check_deprecation(dir_new, options, settings_path)

    # This assert puts the actual error messages into the pytest XML output.
    assert pytest.errlog.stream.getvalue() == ''
    assert error_count == 0  # this should never trigger, just in case
