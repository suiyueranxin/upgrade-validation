import csv
import io
import re

# Method types for operations.
# See https://swagger.io/docs/specification/paths-and-operations/
METHOD_TYPES = ["get", "post", "put", "patch", "delete", "head", "options", "trace"]


def is_spec(spec):
    """Returns true if the given object is (the root level of) a Swagger or OpenAPI specification."""
    return isinstance(spec, dict) and ("swagger" in spec or "openapi" in spec)


def filter_paths(spec, tags):
    """Remove methods and paths that are NOT matching given tags."""
    if not "paths" in spec:
        return
    paths = list(spec["paths"].keys())
    for path in paths:
        for method in METHOD_TYPES:
            if method in spec["paths"][path] and not matches_tags(spec["paths"][path][method], tags) and not matches_tags(spec["paths"][path], tags):
                del spec["paths"][path][method]
#                print("Removing method " + method + " from " + path)
        has_methods_after_remove = False
        for method in METHOD_TYPES:
            if method in spec["paths"][path]:
                has_methods_after_remove = True
                break
        if not has_methods_after_remove:
#            print("Removing path " + path)
            del spec["paths"][path]
    return


def rename_tag(spec, old_tag, new_tag):
    """Rename a tag in a specification."""
    if "tags" in spec:
        for tag in spec["tags"]:
            if tag["name"] == old_tag:
                tag["name"] = new_tag
    for path in spec["paths"]:
        for method in METHOD_TYPES:
            if method in spec["paths"][path]:
                if "tags" in spec["paths"][path][method]:
                    spec["paths"][path][method]["tags"] = [new_tag if tag == old_tag else tag for tag in spec["paths"][path][method]["tags"]]
    return


def retain_tags(spec, tags):
    """Remove all tags that are not included in the argument list."""
    if "tags" in spec:
        spec["tags"] = [t for t in spec["tags"] if t["name"] in tags]
    for path in spec["paths"]:
        for method in METHOD_TYPES:
            if method in spec["paths"][path]:
                if "tags" in spec["paths"][path][method]:
                    spec["paths"][path][method]["tags"] = [t for t in spec["paths"][path][method]["tags"] if t in tags]
    return


def get_description(method):
    if "description" in method:
        return method["description"]
    if "summary" in method:
        return method["summary"]
    return ""


def has_tag(elem, tag):
    """Find out whether a specification element has a given tag."""
    if isinstance(elem, dict):
        if tag == "deprecated":
            return "deprecated" in elem and elem["deprecated"]
        elif "tags" in elem:
            for t in elem["tags"]:
                if t.lower() == tag.lower():
                    return True
    return False


def matches_tags(elem, tags):
    """Find out whether a specification element matches a list of tags."""
    for tag in tags:
        if not has_tag(elem, tag):
            return False
    return True


def is_deprecated(elem, check_children=False):
    """Find out whether an element is a deprecated."""
    if not isinstance(elem, dict):
        return False
    if "deprecated" in elem and elem["deprecated"]:
        return True
    if check_children:
        num_children = 0
        num_deprecated = 0
        for method in METHOD_TYPES:
            if method in elem:
                num_children += 1
                if is_deprecated(elem[method], False):
                    num_deprecated += 1
        return num_children > 0 and num_deprecated == num_children
    return False


def is_deprecated_spec(spec):
    """Find out whether an entire specification is a deprecated."""
    if is_deprecated(spec):
        return True
    if "paths" in spec:
        for path in spec["paths"]:
            if not is_deprecated(spec["paths"][path]):
                for method in spec["paths"][path]:
                    if not is_deprecated(spec["paths"][path][method]):
                        return False
        return True
    return False


def is_versioned(p):
    """Check if a given OpenAPI path (operation URL) is versioned, i.e., contains 'v1', 'v2' etc. in its path."""
    entries = p.split("/")
    for e in entries:
        if re.search("^v([0-9]+)$", e):
            return True
    return False


def find_schema_owner(elem):
    """Find the object holding the 'schema' property in a parameter or response object."""
    if "schema" in elem:
        return elem
    if "content" in elem and "application/json" in elem["content"]:
        return elem["content"]["application/json"]
    # As fall-back we return the element itself
    return elem


def find_type_owner(elem):
    """Find the object holding the 'type' property in a parameter or response object."""
    if "type" in elem:
        return elem
    if "schema" in elem and "type" in elem["schema"]:
        return elem["schema"]
    # As fall-back we return the element itself.
    return elem


def normalize_type(type):
    """Normalize a reference to a type. We ignore prefix paths and case to allow simple refactorings."""
    for ch in ["$", "/"]:
        start = type.rfind(ch)
        if start >= 0:
            return type[start + 1:].lower()
    return type.lower()


def convert_parameter_list_to_dict(parameter_list):
    """Convert a list of OpenAPI parameter/response objects into a dictionary.
    If it is a named parameter, its name is used as a key in the dictionary.
    Otherwise the parameter's index is used as key.
    """
    if isinstance(parameter_list, dict):
        return parameter_list
    parameter_dict = {}
    index = 1
    for param in parameter_list:
        if "name" in param:
            parameter_dict[param["name"]] = param
        else:
            parameter_dict[index] = param
            index += 1
    return parameter_dict

def merge_specs(base, ext, groups, ignore_redundant_key):
    """ Merge two OpenAPI specifications."""
    for group in groups:
        if group in ext:
            if group not in base:
                base[group] = {}
            for key in ext[group]:
                if key in base[group]:
                    if not ignore_redundant_key:
                        raise RuntimeError("Key '{}' in group '{}' exists in both specifications".format(key, group))
                        sys.exit(1)
                    else:
                        if base[group][key] != ext[group][key]:
                            raise RuntimeError("ignored key collision '{}' in group '{}' has different values in both specifications".format(key, group))
                            sys.exit(1)
                base[group][key] = ext[group][key]
    return base


def merge_selected_objects(target, source, group, elements):
    """Merge selected elements from one specification into another."""
    if group not in target:
        target[group] = {}
    for elem in elements:
        target[group][elem] = source[group][elem]


def collect_definition_refs(entity):
    """Collect all references to definitions recursively contained in an entity."""
    result = set()
    prefixes = [ "#/definitions/", "#/parameters/" ]
    if isinstance(entity, dict):
        for x in entity:
            result.update(collect_definition_refs(entity[x]))
    elif isinstance(entity, list):
        for x in entity:
            result.update(collect_definition_refs(x))
    elif isinstance(entity, str):
        for prefix in prefixes:
            if entity.startswith(prefix):
                result.add(entity[len(prefix):])
    return result


def purge_definitions(spec, used_types):
    """Remove a given set of definitions from a specification."""
    purged = []
    for kind in [ "definitions", "parameters" ]:
        if not kind in spec:
            continue
        definitions = list(spec[kind].keys())
        for d in definitions:
            if not d in used_types:
                del spec[kind][d]
                purged.append(d)
#                print("Removing unused definition " + d)
    return purged


def purge_unused_definitions(spec):
    """Remove unused definitions from a specification."""
    used = collect_definition_refs(spec)
    purged = [ "x" ]
    while purged:
        purged = purge_definitions(spec, used)
        used = collect_definition_refs(spec)


def remove_field(spec, field):
    """Remove all occurrences of a field in specification (recursive)."""
    if isinstance(spec, dict):
        if field in spec:
            del spec[field]
        for x in spec:
            remove_field(spec[x], field)
    return


def extract_base_path(spec, base_path):
    """Removes the base_path prefix from all paths and set it as basePath"""
    paths = list(spec["paths"].keys())
    for p in paths:
        if p.startswith(base_path):
            new_path = p[len(base_path):]
            spec["paths"][new_path] = spec["paths"][p]
            del spec["paths"][p]
    spec["basePath"] = base_path
    return


def export_csv(spec):
    """Export summary of a specification as csv."""
    output = io.StringIO()
    writer = csv.writer(output)
    if "paths" in spec:
        for path in spec["paths"]:
            for method in METHOD_TYPES:
                if method in spec["paths"][path]:
                    o = spec["paths"][path][method]
                    s = o.get("summary", "")
                    r = o.get("x-removal-version", "")
                    writer.writerow([path, method, s, r ])
    return output.getvalue()
