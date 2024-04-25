import json
import os
import re
import sys
import yaml

sys.path.append(sys.path[0] + "/../../")
from path import append_path
from pylibs.openapi import has_tag, is_spec, METHOD_TYPES
from pylibs.versioning import VersionCollector


class Config():
    """Encapsulates configuration of the API tests"""

    # Supported scopes in order of increasing priority.
    scope_priorities = ["private", "public", "customer"]

    def __init__(self, repo, base_version, target_version, test_all, logger):
        self.logger = logger
        self.tests = []
        self.component_target_versions = {}
        self.exceptions = {}
        self.path_scopes = {}
        self.fork = None

        # Check if we just want to run the dummy test
        if repo == "dummy":
            self.init_dummy_test()
            return

        # Collect component versions
        collector = VersionCollector(repo, base_version, target_version, "checkSwagger", "swaggerFiles", test_all, logger)
        self.tests = collector.tests
        self.component_target_versions = collector.component_target_versions
        self.fork = collector.fork

        #  Also add dummy tests if we are checking multiple repositories
        if len(collector.repositories) > 1:
            self.init_dummy_test()

        # Load exceptions definitions
        exceptions_yaml = yaml.safe_load(open("exceptions.yaml"))
        for r in exceptions_yaml["repositories"]:
            if r in collector.repositories and "exceptions" in exceptions_yaml["repositories"][r]:
                for e in exceptions_yaml["repositories"][r]["exceptions"]:
                    for p in e["paths"]:
                        self.exceptions[p] = e["reason"] if "reason" in e else True

    def init_dummy_test(self):
        self.tests.append("dummy;dummy;0")
        self.component_target_versions["dummy"] = "1"
        return

    def set_scope(self, path, scope):
        self.path_scopes[path] = scope

    def get_prefix_scope(self, path):
        for p in self.path_scopes:
            if path.startswith(p):
                return self.path_scopes[p]
        return None

    def tag_private_path(self, path, elem):
        """Find out whether an element is part of a private API. See the README for details."""
        # If the path is a child of a known private path, it is also private.
        if self.get_prefix_scope(path) == "private":
            return True
        # TODO: move this config into a json file
        if path.startswith("velocity/vsystem/open-api/scheduler-internal.yaml"):
            self.set_scope(path, "private")
            return True
        if path.startswith("velocity/vsystem/open-api/vrep-private-api.yaml"):
            self.set_scope(path, "private")
            return True
        if path.startswith("velocity/axino/docs/api/spec.yaml") and has_tag(elem, "private"):
            self.set_scope(path, "private")
            return True
        if path.startswith("bigdataservices/storagegateway/doc/api-spec/storagegateway-swagger.yaml") and (has_tag(elem, "private") or has_tag(elem, "internal")):
            self.set_scope(path, "private")
            return True
        if path.startswith("bdh/datahub-app-base/src/apps/dh-app-connection") and has_tag(elem, "private") and not has_tag(elem, "metadata"):
            self.set_scope(path, "private")
            return True
        if path.startswith("bdh/datahub-app-data/src/apps/dh-app-metadata"):
            if has_tag(elem, "private"):
                self.set_scope(path, "private")
                return True
            # If all children are private, the parent is also private
            if isinstance(elem, dict) and len(elem) > 0:
                for entry in elem:
                    if not has_tag(elem[entry], "private"):
                        return False
                self.set_scope(path, "private")
                return True
        return False

    def has_non_private_paths(self, path, spec):
        """Find out whether a specification contains any non-private paths (endpoints)."""
        if "paths" in spec:
            for p in spec["paths"]:
                for method in METHOD_TYPES:
                    new_path = append_path(append_path(append_path(path, "paths"), p), method)
                    if method in spec["paths"][p] and not self.tag_private_path(new_path, spec["paths"][p][method]):
                        return True
        return False

    def has_customer_paths(self, path, spec):
        """Find out whether a specification contains any customer paths (endpoints)."""
        if "paths" in spec:
            for p in spec["paths"]:
                if has_tag(spec["paths"][p], "customer"):
                    return True
                for method in METHOD_TYPES:
                    if method in spec["paths"][p] and has_tag(spec["paths"][p][method], "customer"):
                        return True
        return False

    def get_scope(self, path, elem):
        # We distiguish between entire specs and elements within specs.
        if is_spec(elem):
            if self.has_customer_paths(path, elem):
                return "customer"
            elif self.has_non_private_paths(path, elem):
                return "public"
            else:
                return "private"
        else:
            if self.get_prefix_scope(path) == "customer" or has_tag(elem, "customer"):
                return "customer"
            elif self.tag_private_path(path, elem):
                return "private"
            else:
                return "public"

    def get_max_scope(self, s, t):
        for scope in reversed(self.scope_priorities):
            if s == scope or t == scope:
                return scope
        return s
