import csv
import sys
import logging as log

from path import append_path, get_path_type
from pylibs.logstream import LogStream


class Diff():
    """Encapsulates diff between API versions, error and warning messages."""

    result_kinds = ["added-entry", "added-definition", "added-operation", "added-method", "added-parameter", "added-property", "added-response",
                    "deprecated", "changed-type", "refined-type",
                    "removed-entry" , "removed-definition", "removed-operation", "removed-method", "removed-parameter",
                    "removed-response", "removed-property", "removed-spec",
                    "changed-spec", "unchanged-spec"]

    def __init__(self):
        self.result = {}
        for kind in self.result_kinds:
            self.result[kind] = []
        self.errors = {}
        self.warnings = {}
        self.scopes = {}

    #########################
    ### Utility functions ###
    #########################

    def dump_csv(self, csv_file, repo, base_version, target_version, exceptions):
        csv_writer = csv.writer(csv_file)
        for kind in self.result_kinds:
            for entry in self.result[kind]:
                e = entry.replace(repo + "/", "")
                s = self.scopes[entry] if entry in self.scopes else ""
                x = ""
                if e in exceptions and isinstance(exceptions[e], str):
                    x = exceptions[e]
                csv_writer.writerow([repo, base_version, target_version, kind, s, e, x])

    def error(self, path, msg):
        self.warnings.pop(path, None)
        self.errors[path] = msg
        
    def warn(self, path, msg):
        if path not in self.errors:
            self.warnings[path] = msg

    ######################
    ### Diff modifiers ###
    ######################

    def add_path(self, path, entry):
        """add a new path to the difference list given by @entry, if it doesn't already exist"""
        if path not in self.result[entry]:
            self.result[entry].append(path)
#        if path in self.result[entry]:
#            log.warning("Change at the Path: " + path + " was already included and therefore not added multiple times")  

    def removed_spec(self, path, scope, fail):
        self.add_path(path, "removed-spec")
        self.scopes[path] = scope
        if fail:
            self.error(path, "specification removed without prior deprecation")
        else:
            self.warn(path, "specification removed")

    def removed_entry(self, base_path, entry, deprecated, private):
        new_path = append_path(base_path, entry)
        type = get_path_type(base_path, entry)
        entry = "removed-" + type
        self.add_path(new_path, entry)
        if private:
            self.warn(new_path, "private/unused {} removed".format(type))
            self.scopes[new_path] = "private"
        elif deprecated:
            self.warn(new_path, "deprecated {} removed".format(type))
            self.scopes[new_path] = "public"  # TODO: could be also "customer"
        else:
            self.error(new_path, "{} removed without prior deprecation".format(type))
            self.scopes[new_path] = "public"  # TODO: could be also "customer"

    def added_entry(self, base_path, entry, scope):
        new_path = append_path(base_path, entry)
        type = get_path_type(base_path, entry)
        entry = "added-"+type 
        self.add_path(new_path, entry)
        self.scopes[new_path] = scope

    def added_unversioned_path(self, path):
        self.error(path, "new path must be versioned")

    def added_required_parameter(self, path):
        self.error(path, "new parameter must be optional")

    def changed_optional_parameter_to_required(self, path, scope):
        self.scopes[path] = scope
        if scope == "private":
            self.warn(path, "formerly optional parameter changed to required")
        else:
            self.error(path, "formerly optional parameter changed to required")

    def changed_parameter_kind(self, path, base, target):
        self.error(path, "parameter changed from '{}' to '{}'".format(base, target))

    def changed_type(self, path, base, target, scope):
        self.add_path(path, "changed-type")
        self.scopes[path] = scope
        msg = "type changed from '{}' to '{}'".format(base, target)
        if scope == "private":
            self.warn(path, msg)
        else:
            self.error(path, msg)

    def refined_type(self, path, base, target, scope):
        self.add_path(path, "refined-type")
        self.warn(path, "type refined from '{}' to '{}'".format(base, target))
        self.scopes[path] = scope

    def deprecated(self, path, removal_version, scope):
        self.add_path(path, "deprecated")
        self.scopes[path] = scope
        if not removal_version:
            self.error(path, "missing deprecation field 'x-removal-version'")
        elif not isinstance(removal_version, str):
            self.error(path, "invalid format of deprecation field 'x-removal-version' (must be string)")

    def changed_spec(self, path, changed, scope):
        if changed:
            self.add_path(path, "changed-spec")
        else:
            self.add_path(path, "unchanged-spec")
        self.scopes[path] = scope
