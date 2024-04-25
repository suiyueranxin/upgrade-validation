#!/usr/bin/python3

import argparse
import logging
import os
import re
import sys
import warnings
import yaml

import pytest
from check import Check
from config import Config
from diff import Diff
from path import append_path

sys.path.append(sys.path[0] + "/../../")
from pylibs.openapi import is_deprecated_spec
from pylibs.fileops import get_from_github

logger = logging.getLogger(__name__)


def warn(m):
    """User-friendly printing of warnings"""
    m = "\n" + m
    warnings.warn(m)
    return


if __name__ == '__main__':

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Swagger/OpenAPI compatibility tests for SAP Data Intelligence.")

    parser.add_argument("--repo", nargs="?", metavar="repo",
        help="repository name of the DI component, e.g. 'velocity/vsystem'. If not set, test all registered repositories.")

    parser.add_argument("--base", nargs="?", metavar="base",
        help="base version of the DI component or releasepack, e.g. '2006.1.8'. If --repo is set, it refers to the component version, otherwise to the releasepack version.")

    parser.add_argument("--target", nargs="?", metavar="target",
        help="target version or branch of the DI component or releasepack, e.g. 'master'. If --repo is set, it refers to the component version, otherwise to the releasepack version.")

    parser.add_argument("-a", action="store_true", dest="test_all",
        help="force testing of all specifications")

    parser.add_argument("-l", nargs="?", default="INFO", metavar="level",
        help="log level, e.g. 'debug'")

    parser.add_argument("-x", nargs="?", metavar="xml",
        help="path for xml test report")

    parser.add_argument("-c", nargs="?", metavar="csv", dest="csv",
        help="path for csv change report")

    pytest.args = parser.parse_args()

    # Set log level (default INFO)
    logging.basicConfig(level=pytest.args.l.upper(), format="%(levelname)-7s %(message)s")

    # Default target version is master branch
    if not pytest.args.target:
        pytest.args.target = "master"

    # Initialize configuration
    pytest.args.config = Config(pytest.args.repo, pytest.args.base, pytest.args.target, pytest.args.test_all, logger)

    # Log parameter info
    if pytest.args.repo:
        repo_msg = "repository '{}'".format(pytest.args.repo)
    elif pytest.args.test_all:
        repo_msg = "all repositories"
    else:
        repo_msg = "default repositories"
    base_msg = "base version '{}'".format(pytest.args.base) if pytest.args.base else "all base versions"
    logger.info("Starting compatibility tests for %s, %s, target version '%s'", repo_msg, base_msg, pytest.args.target)

    # Run pytest
    main_args = ["-s", "-v"]
    pytest.diffs = {}
    if pytest.args.x:
        main_args.extend(["--color=yes", "--junitxml={}".format(pytest.args.x), "-o", "junit_family=xunit2", "-o", "junit_suite_name=test_api"])
    main_args.append(os.path.abspath(__file__))
    exit_code = pytest.main(args=main_args)

    # Save change report as CSV file if requested
    if pytest.args.csv:
        logger.info("Generating CSV change report %s", pytest.args.csv)
        with open(pytest.args.csv, "w", newline="") as csv_file:
            for test, diff in sorted(pytest.diffs.items()):
                repo, _, base_version = test.split(";")
                target_version = pytest.args.config.component_target_versions[repo]
                diff.dump_csv(csv_file, repo, base_version, target_version, pytest.args.config.exceptions)

    # Finish test execution
    sys.exit(exit_code)


def pytest_generate_tests(metafunc):
    """Generate separate test for every Swagger/OpenAPI file. Instantiates test_api function for all Swagger/OpenAPI files."""
    if "test" in metafunc.fixturenames:
        metafunc.parametrize("test", pytest.args.config.tests)


def test_api(test):
    """Main Python test case. It tests the compatibility of a Swagger/OpenAPI file by comparing a base with a target version."""

    # Extract details from test parameters and configuration
    repo, path, base_version = test.split(";")
    file = repo + "/" + path
    fork = pytest.args.config.fork
    target_version = pytest.args.config.component_target_versions[repo]

    # Check if this is the dummy check
    if repo == "dummy":
        run_dummy_checks()
        return

    # Check if fork should be used (single repo test)
    github_repo = fork if fork else repo

    logger.debug("\nTesting repository '%s', base version '%s', target version '%s'", repo, base_version, target_version)

    # Register diff for this test
    pytest.diffs[test] = Diff()

    # Load base version
    base_text = get_from_github(github_repo, path, base_version, True)
    if not base_text:
        get_from_github(github_repo, "README.md", base_version, False)
        warn("Skipped API check because specification is not part of base version")
        return
    base = yaml.safe_load(base_text)
    base_scope = pytest.args.config.get_scope(file, base)

    # Load target version
    target_text = get_from_github(github_repo, path, target_version, True)
    if not target_text:
        get_from_github(github_repo, "README.md", target_version, False)
        private = pytest.args.config.tag_private_path(append_path(repo, path), {})
        fail = not private and not is_deprecated_spec(base) and path not in pytest.args.config.exceptions
        pytest.diffs[test].removed_spec(file, base_scope, fail)
        report_errors_and_warnings(repo, pytest.diffs[test])
        return

    target = yaml.safe_load(target_text)
    target_scope = pytest.args.config.get_scope(file, target)

    changed = base_text != target_text
    scope = pytest.args.config.get_max_scope(base_scope, target_scope)
    pytest.diffs[test].changed_spec(file, changed, scope)

    # Run all checks
    run_checks(repo, file, base, target, pytest.diffs[test])

    # Report errors and warnings
    report_errors_and_warnings(repo, pytest.diffs[test])

    return


def validate_dummy_results(kind, result):
    expected_result = open("dummy/{}.txt".format(kind)).readlines()
    expected_result = {it.strip() for it in expected_result}
    found_result = {"%s: %s" % (msg, path) for (path, msg) in result.items()}
    missing_items = expected_result - found_result
    unexpected_items = found_result - expected_result
    for bucket in [["Missing", missing_items], ["Unexpected", unexpected_items]]:
        if bucket[1]:
            formatted = "\n - ".join(["%s" % (it) for (it) in bucket[1]])
            pytest.fail("{} {} in dummy test:\n - {}".format(bucket[0], kind, formatted))


def run_dummy_checks():
    """Run compatibility checks for dummy specification. It tests whether this tests works as expected."""
    base_text = open("dummy/base.yaml").read()
    target_text = open("dummy/target.yaml").read()
    base = yaml.safe_load(base_text)
    target = yaml.safe_load(target_text)
    diff = Diff()
    check = Check(logger, pytest.args.config, diff)
    check.check_swagger_main("dummy", base, target)
    validate_dummy_results("errors", diff.errors)
    validate_dummy_results("warnings", diff.warnings)


def run_checks(repo, file, base, target, diff):
    """Run compatibility checks for given base and target specifications. Collects validation errors and fails the test if needed."""
    check = Check(logger, pytest.args.config, diff)
    check.check_swagger_main(file, base, target)


def report_errors_and_warnings(repo, diff):

    # Extract errors and warnings from diff
    errors = diff.errors
    warns = diff.warnings

    # Turn errors that are exceptions into warnings
    if errors:
        for e, v in pytest.args.config.exceptions.items():
            full_path = "{}/{}".format(repo, e)
            if full_path in errors:
                warns[e] = v if isinstance(v, str) else errors[full_path]
                if warns[e].endswith("."):
                    warns[e] = warns[e][:-1]
                errors.pop(full_path, None)

    # Report warnings
    if warns:
        formatted_warnings = "\n - ".join(["%s: %s" % (msg, path) for (path, msg) in warns.items()])
        warn("{} warnings found:\n - {}".format(len(warns), formatted_warnings))

    # Report errors
    if errors:
        formatted_errors = "\n - ".join(["%s: %s" % (msg, path) for (path, msg) in errors.items()])
        m = "{} incompatible API changes found:\n - {}\nSee https://github.wdf.sap.corp/bdh/upgrade-validation/tree/master/tests/api for more info.".format(len(errors), formatted_errors)
        pytest.fail(m)
