#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
import logging as log

from common import dig, get_all_operators, extract_operator_id
from fix import fixed


def get_settings_json(base_path, settings_path):
    # first, check if the settings.json can be found under general/ui
    general_path = os.path.join(base_path, "general/ui")
    if os.path.isdir(general_path):
        for f in os.scandir(general_path):
            if f.name.endswith("settings.json"):
                return os.path.join(general_path, f.name)
    # if not, use the value from the solutions.json
    if settings_path:
        return os.path.join(base_path, settings_path)
    return base_path


def get_deprecations(base_path, operators, settings_path):
    """
    Check all operators for being deprecated, as outlined in [1].
    Returns a dictionary, with a list of deprecated operators for each criterion in [1].
    NB: For the purpose of this script, BETA operators are treated like deprecated ones, in
    the sense that they may be removed from one version to the next.
    [1] https://github.wdf.sap.corp/velocity/vflow/blob/master/src/repo/deprecation/README.md
    """
    deprecated = {}

    # 1. deprecated operators should have extra/upgradeTo set in their operator.json.
    # TODO: _no_ operator currently has that, so the sanity check at function's end fails.
    log.debug("deprecation scan: operator should have extra.upgradeTo set in operator.json")
    # deprecated['op:upgradeTo'] = [op['!path'] for op in operators if dig(op, 'extra/upgradeTo')]

    # 2. the operator's name/description should be prepended by "[OLD]" (or "[BETA]")
    log.debug("deprecation scan: title in operator.json should be prepended by [OLD] (or [BETA])")
    # 'BETA' operators are treated like deprecated.
    deprecated['op:description'] = [op['!path'] for op in operators
                                    if re.match(r'^\[(OLD|BETA)\]', str(dig(op, 'description')))]

    # 3. the operator's name should be prepended by "[OLD]" in the documentation.
    log.debug("deprecation scan: title in README should be prepended by [OLD] (or [BETA])")
    log.debug("deprecation scan:   scanning general/docu/README.md")
    deprecated['docu/README'] = []
    for path, subdirs, subfiles in os.walk(base_path + "general/docu/"):
        for name in subfiles:
            if name == "README.md":
                with open(path + "/" + name, encoding='UTF-8') as f:
                    if re.match(r'^\[(OLD|BETA)\] ', f.read()):
                        op_id = extract_operator_id(path)
                        deprecated['docu/README'].append(op_id)

    # 3.b. documentation might also be in the operator's directory.
    log.debug("deprecation scan:   scanning operator-specific README.md files")
    deprecated['op/README'] = []
    for op in operators:
        filename = base_path + "operators/" + op['!path'].replace('.', '/') + '/README.md'
        if os.path.isfile(filename):
            f = open(filename, 'r')
            if re.match(r'^\[(OLD|BETA)\] ', f.readline()):
                deprecated['op/README'].append(op['!path'])
            f.close()

    # 4. the operator should be put in the "Deprecated Operators" category.
    # also treat operators in BETA-marked groups as deprecated
    if settings_path:
        log.debug("deprecation scan: operator should be in 'Deprecated Operators' category in settings.json")
        deprecated['ui/settings/category'] = []
        settings_json = get_settings_json(base_path, settings_path)
        if os.path.isfile(settings_json):
            log.info("using deprecation info in %s", settings_json)
            with open(settings_json) as f:
                j = json.load(f)
                for cat in j['operatorCategories']:
                    if cat['name'] == "Deprecated Operators" or cat['name'].endswith("(beta)"):
                        deprecated['ui/settings/category'].extend(cat['entities'])
        else:
            if "dq-integration" not in base_path:
                log.fatal("no settings.json found at %s in %s", settings_path, base_path)
                sys.exit(-1)

    # output the set of all deprecated operators
    deprecated_ops = {dep for _, deps in deprecated.items() for dep in deps}
    log.debug("operators marked as deprecated: %s", deprecated_ops)

    return deprecated


def get_beta_operators(base_path, settings_path):
    """Returns all a set with (the names of) all operators with beta status."""

    operators = get_all_operators(base_path)

    # Marked as BETA in operator.json
    beta_operators = set([op['!path'] for op in operators
                          if re.match(r'^\[BETA\]', str(dig(op, 'description')))])

    # Marked as BETA in general or operator-specific documentation
    for op in operators:
        for place in ["general/docu/", "operators/"]:
            filename = base_path + place + op['!path'].replace('.', '/') + '/README.md'
            if os.path.isfile(filename):
                f = open(filename, 'r')
                if re.match(r'^\[BETA\] ', f.readline()):
                    beta_operators.add(op['!path'])
                f.close()
    # Operator category marked as BETA
    settings_json = get_settings_json(base_path, settings_path)
    if os.path.isfile(settings_json):
        with open(settings_json) as f:
            j = json.load(f)
            for cat in j['operatorCategories']:
                if cat['name'].endswith("(beta)"):
                    beta_operators.union(set(cat['entities']))
    else:
        if "dq-integration" not in base_path:
            log.fatal("no settings.json found at %s", settings_path)
            sys.exit(-1)

    log.debug("ignoring beta operators: %s", beta_operators)

    return beta_operators


def set_of_all_operators_in(map_of_lists):
    """Takes a map of lists and returns the set union of all list members."""
    return set.union(*[set(l) for l in map_of_lists.values()])


def check_deprecation(dir_new, options, settings_path):
    """Check if deprecated operators are properly marked in the new version."""

    ops_new = get_all_operators(dir_new)

    deprecated_new = get_deprecations(dir_new, ops_new, settings_path)
    conditions_for_deprecation = deprecated_new.keys()

    all_deprecated_new = set_of_all_operators_in(deprecated_new)
    log.info("checking consistency of %d deprecated operators", len(all_deprecated_new))
    warning_count = {}
    has_warning = False

    for op in all_deprecated_new:  # iterate through all deprecated operators
        for cond in conditions_for_deprecation:  # and through all reasons for deprecation
            if not op in deprecated_new[cond]:
                # warn if this operator does not satisfy condition
                warning_count[cond] = warning_count[cond] + 1 if cond in warning_count else 1
                has_warning = True
                if options.warn_depr:
                    log.warning("%s is marked deprecated, but does not satisfy condition %s", op, cond)

    if has_warning:
        log.warning("missing fields for deprecated operators: %s", warning_count)
        if not options.warn_depr:
            log.warning("  ^ re-run with --Wdeprecation for details. ^")
            log.warning("  see https://github.wdf.sap.corp/velocity/vflow/blob/master/src/repo/deprecation/README.md for operator deprecation guidelines")

    # check_deprecation only outputs warnings, thus errors == 0
    return 0


def check_operator_removal(dir_old, dir_new, settings_json, operator_blacklist=[]):
    """
    Check if every removed operator (i.e. which is in the old version, but not in the new)
    has been marked as either deprecated or beta before removal.
    """
    ops_old = get_all_operators(dir_old)
    ops_new = get_all_operators(dir_new)
    log.info("checking removal for %s operators", len(ops_old))

    all_old = [op['!path'] for op in ops_old]
    all_new = [op['!path'] for op in ops_new]

    # get all operators which were removed from the old version
    removed = set(all_old) - set(all_new)
    # get all operators removed from the old version without being deprecated
    deprecated_old = get_deprecations(dir_old, ops_old, settings_json)
    removed_without_deprecation = removed - set_of_all_operators_in(deprecated_old)

    # TODO: also reflect the time between the two versions.
    error_count = 0
    for op in removed_without_deprecation:
        # check if any blacklist pattern matches the operator
        if True in [(pattern in op) for pattern in operator_blacklist]:
            log.warning("ignoring blacklisted operator %s", op)
            continue
        if not fixed("op-del", op, ""):
            log.error("Operator %s was removed without deprecating it first.", op)
            error_count += 1

    return error_count
