import re
import sys
import warnings

sys.path.append(sys.path[0] + "/../../")
from path import append_path, add_base_path, is_path_elem, is_definition_elem, TypeUsageTracker
from pylibs.openapi import convert_parameter_list_to_dict, find_schema_owner, find_type_owner, has_tag, is_deprecated, is_versioned, METHOD_TYPES, normalize_type


class Check():
    """Main OpenAPI/Swagger compatibility check logic."""

    def __init__(self, logger, config, diff):
        self.logger = logger
        self.config = config
        self.diff = diff
        self.file_path = None
        self.public_types = None


    def check_generic_entry(self, path, entry, kind, base, target):
        """Generic compatibility check for an entry. This consists of two steps:
        1. Check whether the entry has been illegally removed from a specification. If yes, create an error for this entry.
        2. Recursively continue the validation by calling the function "check_XXX" where XXX is given by the "kind" parameter.
        Issues in deprecated and private entries do not yield validation errors, but warnings.
        """
        new_path = append_path(path, entry)
        self.logger.debug(new_path)
        if entry not in base:
            return

        # Find out whether it was deprecated or private.
        # We need to call it here because to recursively tag paths as private.
        deprecated = is_deprecated(base[entry], check_children=True)
        if is_path_elem(new_path):
            # Paths (end-points):
            private = self.config.tag_private_path(new_path, base[entry])
        else:
            # Definitions, components etc.
            private = not self.public_types.has_path_usage(new_path)

        # Check whether the entry was removed
        if entry not in target:
            self.diff.removed_entry(path, entry, deprecated, private)
        else:
            # Otherwise continue comparison
            check = getattr(self, "check_" + kind)
            check(new_path, base[entry], target[entry])
        return


    def check_generic_dict(self, path, subkind, base, target):
        """Generic compatibility check for all entries (direct children) of a given specification.
        This simply calls the "check_generic_entry" function for all entries.
        """
        for entry in base:
            self.check_generic_entry(path, entry, subkind, base, target)

        # Check for added entries and deprecations
        for entry in target:
            if entry not in base:
                scope = self.config.get_scope(path, target[entry])
                if entry == "deprecated" and is_deprecated(target):
                    self.diff.deprecated(path, target.get("x-removal-version", None), scope)
                else:
                    new_path = append_path(path, entry)
                    self.diff.added_entry(path, entry, scope)
        return

    # ============================================== #
    # === Start of main Swagger validation logic === #
    # ============================================== #


    def check_swagger_main(self, path, base, target):
        """Check the root level of a Swagger specification."""

        self.public_types = TypeUsageTracker(path)

        add_base_path(base)
        add_base_path(target)

        # Check paths
        self.check_generic_entry(path, "paths", "path_list", base, target)

        # Check definitions, parameters, components etc.
        # We need to iterate it to reach a fix point in the type usage tracker
        types_changed = True
        while types_changed:
            self.public_types.changed = False
            self.check_swagger_definitions(path, base, target)
            types_changed = self.public_types.changed
        # One last time needed
        self.check_swagger_definitions(path, base, target)

        return


    def check_swagger_definitions(self, path, base, target):
        """Check the definitions, parameters and responses at the root level of a specification."""

        # Swagger 2 to OpenAPI 3 migration: /definitions become /components/schemas
        if "definitions" in base and "definitions" not in target and "components" in target and "schemas" in target["components"]:
            new_path = append_path(path, "definitions")
            self.check_generic_dict(new_path, "definition", base["definitions"], target["components"]["schemas"])
        else:
            self.check_generic_entry(path, "definitions", "definition_list", base, target)

        # Check components and top-level parameters if present
        self.check_generic_entry(path, "components", "component_list", base, target)
        self.check_generic_entry(path, "parameters", "root_parameter_or_response_list", base, target)
        self.check_generic_entry(path, "responses", "root_parameter_or_response_list", base, target)


    def check_path_list(self, path, base, target):
        """Check the /paths level of a Swagger specification."""
        self.check_generic_dict(path, "path", base, target)

        # Check for unversioned, public, new paths (not allowed)
        if not is_versioned(path):
            for p in target:
                full_path = append_path(path, p)
                if p not in base and not is_versioned(p):
                    for method in target[p]:
                        if not self.config.tag_private_path(full_path, target[p][method]):
                            self.diff.added_unversioned_path(full_path)


    def check_path(self, path, base, target):
        """Check a path, e.g., /paths/foo."""
        for method in METHOD_TYPES:
            self.check_generic_entry(path, method, "method", base, target)


    def check_method(self, path, base, target):
        """Check a method of a path, e.g. /paths/foo/get."""

        # We need to know later whether this was a customer API
        if has_tag(base, "customer"):
            self.config.set_scope(path, "customer")

        # Check parameter. In Swagger 2 to OpenAPI 3 migration: body parameter becomes requestBody
        if "parameters" in base and len(base["parameters"]) == 1 and "in" in base["parameters"][0] and "body" == base["parameters"][0]["in"] and "requestBody" in target:
            new_path = append_path(append_path(path, "parameters"), "body")
            self.check_parameter_or_response(new_path, base["parameters"][0], target["requestBody"])
        else:
            self.check_generic_entry(path, "parameters", "parameter_list", base, target)

        # Check request body (Open API 3)
        self.check_generic_entry(path, "requestBody", "parameter_or_response", base, target)

        # Check responses
        self.check_generic_entry(path, "responses", "response_list", base, target)

        # Check deprecation
        if not is_deprecated(base) and is_deprecated(target):
            scope = self.config.get_scope(path, base)
            self.diff.deprecated(path, target.get("x-removal-version", None), scope)


    def check_parameter_list(self, path, base, target):
        """Check parameters of a path, e.g., /paths/foo/get/parameters."""
        base_params = convert_parameter_list_to_dict(base)
        target_params = convert_parameter_list_to_dict(target)

        # Swagger 2 to OpenAPI 3 migration: body parameter becomes requestBody
        if "body" in base_params and "body" not in target_params:
            base_params.pop("body")
        self.check_generic_dict(path, "parameter_or_response", base_params, target_params)

        # Check for required new parameters (not allowed)
        for param in target_params:
            if param not in base_params and "required" in target_params[param] and target_params[param]["required"] == True:
                self.diff.added_required_parameter(append_path(path, param))


    def check_response_list(self, path, base, target):
        """Check responses of a path, e.g., /paths/foo/get/responses."""

        # Check only for compatibility of common HTTP success status codes
        for status in [200, 201, 202]:
            self.check_generic_entry(path, status, "parameter_or_response", base, target)
            self.check_generic_entry(path, str(status), "parameter_or_response", base, target)


    def check_parameter_or_response(self, path, base, target):
        """Check a parameter or response of a path, e.g., /paths/foo/get/parameters/bar."""
        self.check_typed_element(path, base, find_type_owner(target))
        self.check_generic_entry(path, "schema", "schema", base, find_schema_owner(target))
        self.check_generic_entry(path, "content", "content", base, target)

        # Check whether the parameter changed from optional to required
        if "required" in target and target["required"] == True and ("required" not in base or base["required"] == False):
            if is_path_elem(path):
                private = self.config.tag_private_path(path, base)
            else:
                private = not self.public_types.has_path_usage(path)
            self.diff.changed_optional_parameter_to_required(path, "private" if private else "public")

        # Check whether the parameter kind changed
        if "in" in target and "in" in base and target["in"] != base["in"]:
            self.diff.changed_parameter_kind(path, base["in"], target["in"])


    def check_schema(self, path, base, target):
        """Check a schema of an object, e.g., /paths/foo/get/parameters/bar/schema."""

        # Allow refactoring: introduction of combiners (oneOf, anyOf, allOf).
        # If a combiner is used in the target but not in the base version,
        # we assume the old type info is moved into the first entry of the
        # combiner.
        for c in ["oneOf", "anyOf", "allOf"]:
            if c in target and target[c] and c not in base:
                target = target[c][0]
                break

        # Check type and items
        self.check_typed_element(path, base, target)
        self.check_generic_entry(path, "items", "items", base, target)

        # TODO: the content of (already existing) combiners is currently not checked


    def check_content(self, path, base, target):
        """Check a content of an object, e.g., /paths/foo/get/responses/200/content."""
        self.check_generic_dict(path, "content_entry", base, target)


    def check_content_entry(self, path, base, target):
        """Check a content of an object, e.g., /paths/foo/get/responses/200/content/application/json."""
        self.check_generic_entry(path, "schema", "schema", base, target)


    def check_items(self, path, base, target):
        """Check a items of an object, e.g., /paths/foo/get/parameters/bar/schema/items."""
        self.check_typed_element(path, base, target)


    def track_type_usage(self, path, type):
        """Track types that are used as parameters or responses in public endpoints."""
        if not is_path_elem(path) and not is_definition_elem(path):
            return
        if not type.startswith("#"):
            return
        if self.config.tag_private_path(path, type):
            return
        referencing_kinds = self.public_types.add_type_usage(path, type)
        if referencing_kinds:
            self.logger.debug("Tracking public usage of {} in {}".format(type, referencing_kinds))
        return


    def check_type_or_ref(self, path, base, target):
        """Check whether a type or ref of an object has changed, e.g., /paths/foo/get/parameters/bar/type."""

        # Check whether the type reference changed
        if normalize_type(base) != normalize_type(target):
            if is_path_elem(path):
                # Type is used inside a path.
                scope = self.config.get_scope(path, base)
            else:
                # Type is used outside of a path, e.g. a definition.
                # Find out whether this object is used as a parameter or response type.
                scope = "public" if self.public_types.has_path_usage(path) else "private"

            self.diff.changed_type(path, base, target, scope)

        # Track types that are used as parameters, responses etc. in public endpoints.
        self.track_type_usage(path, base)


    def check_typed_element(self, path, base, target):
        """Check an element that has either a 'type' or a '$ref' property. This is usually a schema, a property or an item."""

        # Allow refinement:  'type: object' -> '$ref: ...'
        if "type" in base and "$ref" not in base and "type" not in target and "$ref" in target:
            if base["type"] == "object":
                scope = self.config.get_scope(path, base)
                self.diff.refined_type(path, base["type"], target["$ref"], scope)
            else:
                self.check_type_or_ref(path, base["type"], target["$ref"])
        else:
            self.check_generic_entry(path, "type", "type_or_ref", base, target)
            self.check_generic_entry(path, "$ref", "type_or_ref", base, target)


    def check_definition_list(self, path, base, target):
        """Check the /definitions level of a Swagger specification."""
        self.check_generic_dict(path, "definition", base, target)


    def check_definition(self, path, base, target):
        """Check a definition, e.g., /definitions/foo."""
        self.check_generic_entry(path, "type", "type_or_ref", base, target)
        self.check_generic_entry(path, "properties", "property_list", base, target)

        # Check list of reqired properties
        base_required = set(base.get("required") if "required" in base else [])
        target_required = set(target.get("required") if "required" in target else [])
        new_required = target_required - base_required
        if new_required:
            used_in = self.public_types.get_type_usage(path)
            if "parameters" in used_in or "requestBody" in used_in:
                for prop in new_required:
                    self.diff.added_required_parameter(append_path(path, prop))


    def check_property_list(self, path, base, target):
        """Check properties list of a definition, e.g., /definitions/foo/properties."""
        self.check_generic_dict(path, "property", base, target)


    def check_property(self, path, base, target):
        """Check a property, e.g., /definitions/foo/properties/bar."""
        self.check_typed_element(path, base, target)
        self.check_generic_entry(path, "items", "items", base, target)
        return


    def check_component_list(self, path, base, target):
        """Check the /components level of a Swagger specification."""
        self.check_generic_entry(path, "schemas", "definition_list", base, target)
        self.check_generic_entry(path, "parameters", "root_parameter_or_response_list", base, target)
        self.check_generic_entry(path, "responses", "root_parameter_or_response_list", base, target)


    def check_root_parameter_or_response_list(self, path, base, target):
        """Check parameter or response definitions at the root level of a Swagger specification."""
        self.check_generic_dict(path, "parameter_or_response", base, target)
