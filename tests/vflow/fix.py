#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
When the deprecation tool detects change (i.e. deletion/change of ports or properties), it returns
with an error. This means it would always fail for a given version pair, blocking the build cycle.
This script looks for a JSON file that lists operators considered fixed.
The `fixed.json` file consists of a single root element named "fixes", containing an array of fixes.
The fixes in this array look as follows:
    {
        "kind": one of the CHANGE_TYPES listed below,
        "operator": the name of the operator, e.g. "com.sap.vora.voraLoader",
        "key": the key belonging to the change, i.e. the name of the ioport/property,
        "subkey": the subkey of the change; only valid for `kind==pkey-chg`,
        "version": version where this API change was introduced,
        "reason": the reason why this does not constitute a proper API change
    }

Of all these fields, the "reason" field is the most important.
"""

import json
import logging as log
import sys

sys.path.append(sys.path[0] + "/../../")
from pylibs.versioning import version_leq


CHANGE_TYPES = ["op-del",    # remove an operator without deprecation
                "port-del",  # remove a port from an operator
                "port-chg",  # change the properties of an operator
                "prop-del",  # remove a property from an operator
                "pkey-del",  # remove a key from a property
                "pkey-chg"]  # change a key within a property

fixes = []

def load_fixes(filename, old_version, new_version):
    """Load all relevant fixes between old_version and new_version."""
    global fixes
    with open(filename) as f:
        all_fixes = json.load(f)['fixes']

    # check correctness of fixes in file
    invalid = [f for f in all_fixes
               if CHANGE_TYPES.count(f['kind']) == 0
               or f.get('operator') is None
               or f.get('key') is None
               or f.get('version') is None
               or f.get('reason') is None or f['reason'] == ""]

    if invalid:
        log.fatal("invalid fixes in %s: %s", filename, invalid)
        sys.exit(-1)

    # keep only fixes that are within valid version range
    # Note that version_leq might return `None` for incomparable versions
    #fixes = [fix for fix in all_fixes
    #         if  version_leq(old_version, fix['version'])
    #         and version_leq(fix['version'], new_version)]

    # warning: due to issues with the version check, we currently use all fixes
    fixes = all_fixes

    log.info("loaded %d/%d fixes between versions %s and %s",
             len(fixes), len(all_fixes), old_version, new_version)
    for f in fixes:
        log.debug(" - %s", f)

    return fixes



def fixed(kind, operator, key, subkey=""):
    """Check if the given API change has is a false positive / fixed."""
    global fixes
    if CHANGE_TYPES.count(kind) == 0:
        log.fatal("unknown fix kind %s", kind)
        sys.exit(-1)

    relevant_fixes = [f for f in fixes
                      if  f['kind'] == kind
                      and f['operator'] == operator]

    if not relevant_fixes:
        return False

    # differentiate between the kinds
    if kind == "op-del":
        log.warning("operator %s: ignoring deletion of un-deprecated operator", operator)
        return True
    if kind == "port-del" or kind == "prop-del" or kind == "port-chg":
        fix = [f for f in relevant_fixes if f['key'] == key]
        if fix:
            k1 = "deletion" if kind.endswith("del") else "change"
            k2 = "port" if kind.startswith("port") else "property"
            log.warning("operator %s: ignoring %s of %s «%s»: %s",
                        operator, k1, k2, key, fix[0]['reason'])
            return True
        else:
            return False
    if kind == "pkey-del" or kind == "pkey-chg":
        fix = [f for f in relevant_fixes if f['key'] == key and f['subkey'] == subkey]
        if fix:
            k1 = "deletion" if kind.endswith("del") else "change"
            log.warning("operator %s: ignoring %s of property «%s»'s subkey «%s»: %s",
                        operator, k1, key, subkey, fix[0]['reason'])
            return True
    return False
