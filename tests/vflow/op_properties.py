import logging as log
import re
import sys
from deprecation import get_beta_operators
from common import dig, get_operators, get_all_operators
from fix import fixed

sys.path.append(sys.path[0] + "/../../")
from pylibs.diff import diff_tree

# Some keys are not crucial and can be changed without any problems.
MUTABLE_KEYS=["description", "title"]

def get_properties(root_dir):
    """Return the properties of all operators."""
    properties = {}
    operators = get_all_operators(root_dir, "operator.json")
    config_schemas = get_all_operators(root_dir, "configSchema.json")
    schemas = get_operators(root_dir + "types/", "schema.json")

    # Every operator has its properties stored in a type schema.
    # The schema itself is stored either in 'types/!op_path/schema.json'
    # or 'operators/!op_path/configSchema'.
    # Which schema to use is (normally) defined in operator.json, either in key
    # 'config/$type' or key 'component'; if neither are present, we fall back on
    # the path of the operator itself (e.g. 'com.sap.some.operator').

    for op in operators:
        op_path = op['!path']
        # determine the type for this operator
        op_type = dig(op, "config/$type")
        op_where = "schema"
        if op_type is not None and re.match(r"https?://sap.com/", op_type):
            try:
                op_type, op_where = re.search(r"(com\..*)\.([^.]*)\.json", op_type).groups()
            except:
                log.fatal("operator name %s does not match pattern", op_type)
                sys.exit(-1)
            if not op_type.startswith("com.sap."):
                log.warning("operator type name not starting with com.sap: %s", op_type)
        else:
            op_type = dig(op, "component")
            if not op_type:
                op_type = op_path
        log.debug("operator %s has type %s defined in %s", op_path, op_type, op_where)
        # Now that we know where to look, get the JSON object with the properties.
        if op_where == "configSchema":
            obj = next((o for o in config_schemas if o['!path'] == op_type), None)
        elif op_where == "schema":
            obj = next((o for o in schemas if o['!path'] == op_type), None)
        else:
            log.fatal("invalid schema %s type for operator %s", op_type, op_path)
            sys.exit(-1)
        if not obj:
            log.warning("could not find type schema for operator %s, type %s", op_path, op_type)
        # Finally, extract the properties from the object.
        properties[op_path] = dig(obj, 'properties')

    if not properties:
        log.fatal("Sanity check failed: Property list empty.")
        sys.exit(-1)
    return properties


def is_compatible_enum_change(key, values_old, values_new):
    # TODO: discuss with vflow team which changes are (not) okay. Maybe also add warning if something changes in a compatible way(?).
    if key == "enum":
        for value in values_old:
            if value not in values_new:
                return False
        return True
    if key == "sap_vflow_constraints":
        if isinstance(values_old, dict) and isinstance(values_old, dict) and "ui_visibility" in values_old and "ui_visibility" in values_new:
            ov = dict(values_old)
            nv = dict(values_new)
            del ov["ui_visibility"]
            del nv["ui_visibility"]
            return ov == nv
    return False


def check_property(op, pname, prop_old, prop_new, options):
    """Performs checks for the property named pname in operator op."""
    error_count = 0
    # New properties can be added in the new version
    if prop_old is None:
        return error_count
    # Old properties may NOT be removed in the new version
    if prop_new is None:
        if not fixed("prop-del", op, pname):
            log.error("Operator %s: deleted property %s", op, pname)
            error_count += 1
            if options.verbose:
                log.error("   old property was %s", prop_old)
        return error_count
    # Check all keys within the property
    for key in prop_old:
        # keys may not be removed
        if prop_new.get(key) is None:
            if not (key in MUTABLE_KEYS or fixed("pkey-del", op, pname, key)):
                log.error("Operator %s: Property %s removed key %s", op, pname, key)
                error_count += 1
                if options.verbose:
                    log.error("   old value was %s", prop_old)
        # keys may not be changed
        elif prop_new[key] != prop_old[key]:
            if not (key in MUTABLE_KEYS or fixed("pkey-chg", op, pname, key) or is_compatible_enum_change(key, prop_old[key], prop_new[key])):
                diff = diff_tree(prop_old[key], prop_new[key], [key])
                log.error("Operator %s: Property %s changed key %s\ndiff: %s", op, pname, key, [str(d) for d in diff])
                error_count += 1
                if options.verbose:
                    log.error("   changed from %s to %s", prop_old[key], prop_new[key])

    return error_count


def check_properties(dir_old, dir_new, options, settings_path):
    """Check if an operator has changed properties"""
    error_count = 0
    operators_old = get_properties(dir_old)
    operators_new = get_properties(dir_new)
    beta_operators = get_beta_operators(dir_old, settings_path)
    # only check operators present in both versions which are were not beta in the old version
    operator_keys = operators_old.keys() & operators_new.keys() - beta_operators

    log.info("checking properties of %s operators", len(operator_keys))

    for op in operator_keys:
        props_old = operators_old[op]
        props_new = operators_new[op]
        if props_old is None or props_new is None:
            if props_new != None:
                log.warning("Operator %s had no properties in old version", op)
            if props_old != None:
                log.error("Operator %s has all properties deleted in new version", op)
                error_count += 1
            continue

        properties = props_old.keys() | props_new.keys()  # union of all properties
        for pname in properties:
            error_count += check_property(op, pname, props_old.get(pname), props_new.get(pname), options)

    return error_count
