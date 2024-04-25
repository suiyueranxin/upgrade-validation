import json
import logging as log
import os
import re
import sys


def dig(tree, path):
    """Navigate in a tree-shaped dict to the element given by path.
    The path is either a list of keys for each layer of the tree,
    or string of keys, separated by '/'."""

    if isinstance(path, list):
        pass # a list is what we actually expect
    elif isinstance(path, str):
        path = path.split("/")
    else:
        raise Exception("path should be list or '/'-separated string, but is " + str(type(path)))

    for key in path:
        if isinstance(tree, dict) and key in tree:
            tree = tree[key]
        else:
            return None
    return tree


def extract_operator_id(path):
    """Return the identifier "(com.sap.some.name)" for a given path."""
    return path[path.find("/com/sap/") + 1:].replace('/', '.')


def get_operators(base_path, filename="operator.json"):
    """Collect all operator.json objects in base_path and return them in a common dict."""
    operators = []
    for path, subdirs, subfiles in os.walk(base_path):
        for name in subfiles:
            if name == filename:
                with open(path + "/" + name) as f:
                    j = json.load(f)
                # Many components don't have a proper component ID. Use the file path instead.
                j['!path'] = extract_operator_id(path)
                # TODO: warn of component ID / path mismatch.
                # Currently switched off, as it generates too many warnings.
                if extract_operator_id(path) != dig(j, 'component'):
                    True
                    # log.warning("name conflict for operator {} residing in {}"
                    #            .format(dig(j, 'component'), extract_operator_id(path)))
                operators.append(j)

    log.debug("collected %s operators from %s", len(operators), base_path)
    for op in operators:
        log.debug("  %s: %s", op['!path'], op['description'] if 'description' in op else '?')
    return operators


def get_all_operators(base_path, filename="operator.json"):
    """Collect all operator.json objects from all "operators" directories in a base_path and return them in a list."""
    operators = []
    for path, subdirs, subfiles in os.walk(base_path):
        if "operators" in subdirs:
            operators.extend(get_operators(os.path.join(path, "operators"), filename))
    return operators
