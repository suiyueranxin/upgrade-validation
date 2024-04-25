import re
import sys

sys.path.append(sys.path[0] + "/../../")
from pylibs.openapi import METHOD_TYPES


def append_path(path, entry):
    """Append an entry to a test path. Used to format paths pointing to entries in OpenAPI files."""
    if path.endswith("/") and str(entry).startswith("/"):
        return "{}{}".format(path, entry[1:])
    if path.endswith("/") or str(entry).startswith("/"):
        return "{}{}".format(path, entry)
    return "{}/{}".format(path, entry)


def get_path_type(path, entry):
    """Returns the type of a specification entry."""
    if path.endswith("/paths"):
        return "operation"
    elif path.endswith("/parameters"):
        return "parameter"
    elif path.endswith("/responses"):
        return "response"
    elif path.endswith("/properties"):
        return "property"
    elif path.endswith("/definitions"):
        return "definition"
    elif "/paths/" in path and entry in METHOD_TYPES:
        return "method"
    else:
        return "entry"


def is_path_elem(path, elem = None):
    """Find out whether a path represents a Swagger endpoint (path) or a child element, e.g. 'parameters', 'responses' or 'requestBody'."""
    if elem:
        return re.search("^.+/paths/.+/" + elem + "/.*$", path) != None
    else:
        return re.search("^.+/paths/.+$", path) != None


def is_definition_elem(path):
    """Find out whether a path represents a Swagger definition or a child element."""
    return re.search("^.+/definitions/.+$", path) != None


def add_base_path(spec):
    """If a specification includes a basePath definition, this function adds the base path as prefix to all paths"""
    if "basePath" not in spec or "paths" not in spec:
        return
    base = spec["basePath"]
    paths = list(spec["paths"].keys())
    for p in paths:
        spec["paths"][append_path(base, p)] = spec["paths"][p]
        del spec["paths"][p]
    return


class TypeUsageTracker():
    """
    Tracks local types that are used in specification objects, e.g.:
    #/definitions/Foo -> set('parameters')
    #/definitions/Bar -> set('parameters','responses')
    """

    path_facets = ["parameters", "responses", "requestBody"]

    def __init__(self, base_path):
        self.base_path = base_path
        self.type_usages = {}
        self.changed = False

    def add_type_usage(self, path, type):
        """Register the usage of a given type."""
        used_kinds = self.type_usages.get(type, set())
        for kind in self.path_facets:
            if is_path_elem(path, kind):
                used_kinds.add(kind)
            if is_definition_elem(path):
                used_kinds.add("definitions")
        used_kinds.update(self.get_type_usage(path))
        if len(used_kinds) > len(self.type_usages.get(type, set())):
            self.changed = True
        if used_kinds:
            self.type_usages[type] = used_kinds
        return used_kinds

    def get_type_usage(self, path):
        """Returns a set of object kinds using a type."""
        local_path = "#" + path[len(self.base_path):]
        result = set()
        for type, kinds in self.type_usages.items():
            if local_path.startswith(type):
                result.update(kinds)
        return result

    def has_path_usage(self, path):
        return len(self.get_type_usage(path).intersection(set(self.path_facets))) != 0
