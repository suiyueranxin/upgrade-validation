#!/usr/bin/python3

import argparse
import logging as log
import sys
import yaml

sys.path.append(sys.path[0] + "/../")
from pylibs.fileops import get_from_github
from pylibs.openapi import extract_base_path, merge_specs, merge_selected_objects, filter_paths, purge_unused_definitions, rename_tag, retain_tags, remove_field
from pylibs.versioning import handle_component, tag_to_version, version_to_tag


def get_component_version(component, ms_version):
    version = handle_component(component, ms_version)
    if tag_to_version(version):
        version = tag_to_version(version)
    log.info("Using version {} of {}".format(version, component))
    return version


def fetch_spec(repo, path, version):
    log.info("Fetching {}/{}".format(repo, path))
    text = get_from_github(repo, path, version_to_tag(version), False)
    return yaml.safe_load(text)


def add_servers(spec, name, path):
    # The list of live landscapes is taken from here: https://github.wdf.sap.corp/pages/bdh/dhaas-operator/landscapes/
    landscapes = [ "dhaas-live", "di-us-east", "di-xas", "di-xat", "di-xmj", "di-xm8" ]
    spec["host"] = "hostname"
    server = {}
    server["url"] = "https://vsystem.ingress.{Cloud Instance}.{Landscape}.k8s-hana.ondemand.com/" + path
    server["description"] = name + " endpoint in an SAP Data Intelligence Cloud instance."
    templates = {}
    templates["Cloud Instance"] = { "description": "The name of the SAP Data Intelligence Cloud instance." }
    templates["Landscape"] = { "description": "The landscape where the SAP Data Intelligence Cloud instance is running.", "enum": [ l + ".shoot.live" for l in landscapes ] }
    server["templates"] = templates
    spec["x-servers"] = [ server ]
    return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate SAP Data Intelligence content for the SAP API Business Hub")
    parser.add_argument("version", help="milestone version to be used")
    args = parser.parse_args()
    log.basicConfig(level="INFO", format="%(levelname)-7s %(message)s")

    # Get component versions
    vflow_version = get_component_version("velocity/vflow", args.version)
    vsystem_version = get_component_version("velocity/vsystem", args.version)
    storagegateway_version = get_component_version("bigdataservices/storagegateway", args.version)
    metadata_version = get_component_version("bdh/datahub-app-data", args.version)
    diagnostics_version = get_component_version("bdh/diagnostics", args.version)

    # Fetch specifications
    vflow_spec = fetch_spec("velocity/vflow", "src/stdlib/swagger.yaml", vflow_version)
    vsystem_spec = fetch_spec("velocity/vsystem", "open-api/login-public.yaml", vsystem_version)
    storagegateway_spec = fetch_spec("bigdataservices/storagegateway", "doc/api-spec/storagegateway-swagger.yaml", storagegateway_version)
    metadata_browsing_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/publicBrowsing.yaml", metadata_version)
    metadata_connection_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/publicConnection.yaml", metadata_version)
    metadata_dataset_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/publicDataset.yaml", metadata_version)
    metadata_lineage_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/publicLineage.yaml", metadata_version)
    metadata_rules_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/publicRules.yaml", metadata_version)
    metadata_scheduler_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/publicScheduler.yaml", metadata_version)
    metadata_tagging_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/publicTagging.yaml", metadata_version)
    metadata_swagger_spec = fetch_spec("bdh/datahub-app-data", "src/apps/dh-app-metadata/spec/swagger.yaml", metadata_version)
    diagnostics_spec = fetch_spec("bdh/diagnostics", "src/open-api/monitoring-query.yaml", diagnostics_version)

    # Merge specifications
    log.info("Merging specifications")
    groups = [ "paths", "definitions", "components", "parameters", "responses" ]
    ignore_redundant_keys = False
    metadata_spec = metadata_browsing_spec

    merge_specs(metadata_spec, metadata_connection_spec, groups, ignore_redundant_keys)
    merge_specs(metadata_spec, metadata_dataset_spec, groups, ignore_redundant_keys)
    merge_specs(metadata_spec, metadata_lineage_spec, groups, ignore_redundant_keys)
    merge_specs(metadata_spec, metadata_rules_spec, groups, ignore_redundant_keys)
    merge_specs(metadata_spec, metadata_scheduler_spec, groups, ignore_redundant_keys)
    merge_specs(metadata_spec, metadata_tagging_spec, groups, ignore_redundant_keys)

    merge_selected_objects(metadata_spec, metadata_swagger_spec, "parameters", [ "top", "skip", "count" ])
    merge_selected_objects(metadata_spec, metadata_swagger_spec, "definitions", [ "annotation", "AnnotationOrigin", "AnnotationType",
        "descriptions", "ErrorResponse", "errorCauses", "errorCause", "errorException",
        "property", "connectionId", "glossaryId", "isoDate", "Operators", "ScoreRange", "TermStatus",
        "SelectOption", "selectOptionElements", "uuid", "taskStatus" ])
    # TODO: "PublicTermsByGlossaryId" is missing in swagger.yaml

    # Remove non-customer paths
    log.info("Removing non-customer paths")
    filter_paths(vflow_spec, ["customer"])
    filter_paths(vsystem_spec, ["customer"])
    filter_paths(storagegateway_spec, ["customer"])
    filter_paths(metadata_spec, ["customer"])
    # TODO: enable when tags are available
    # filter_paths(diagnostics_spec, ["customer"])

    # Remove unused definitions
    log.info("Removing unused definitions")
    purge_unused_definitions(vflow_spec)
    purge_unused_definitions(vsystem_spec)
    purge_unused_definitions(storagegateway_spec)
    purge_unused_definitions(metadata_spec)

    # Remove internal fields
    log.info("Removing internal fields")
    remove_field(metadata_spec, "x-di-policy")
    remove_field(metadata_spec, "x-swagger-router-controller")

    # Extract base path
    log.info("Extracting base path")
    extract_base_path(metadata_spec, "/api/v1")

    # Clean up tags
    rename_tag(vflow_spec, "repo", "Repository")
    rename_tag(vflow_spec, "rt", "Runtime")
    rename_tag(vflow_spec, "sys", "System")
    retain_tags(vflow_spec, ["Repository", "Runtime", "System"])
    retain_tags(vsystem_spec, [])
    retain_tags(storagegateway_spec, [])
    rename_tag(metadata_spec, "browse", "Browse")
    rename_tag(metadata_spec, "catalog", "Catalog")
    rename_tag(metadata_spec, "connection", "Connection")
    rename_tag(metadata_spec, "dataset", "Dataset")
    rename_tag(metadata_spec, "import", "Import")
    rename_tag(metadata_spec, "export", "Export")
    rename_tag(metadata_spec, "lineage", "Lineage")
    rename_tag(metadata_spec, "rules", "Rules")
    rename_tag(metadata_spec, "scheduler", "Scheduler")
    rename_tag(metadata_spec, "tagging", "Tagging")
    retain_tags(metadata_spec, ["Browse", "Catalog", "Connection", "Dataset", "Import", "Export", "Rules", "Scheduler", "Tagging"])

    # Add server definitions
    # add_servers(vflow_spec, "Pipeline Engine", "app/pipeline-modeler/service")
    # add_servers(vsystem_spec, "System Management", "")
    # add_servers(storagegateway_spec, "Storage Gateway", "")
    # add_servers(metadata_spec, "Metadata Management", "app/datahub-app-data")
    # add_servers(diagnostics_spec, "Monitoring Query", "app/diagnostics-gateway/monitoring/query/api/v1")

    # Save specifications
    for p in [("vflow",vflow_spec),("vsystem",vsystem_spec),("storagegateway",storagegateway_spec),("metadata",metadata_spec),("monitoring_query",diagnostics_spec) ]:
        name = p[0] + ".yaml"
        log.info("Saving {}".format(name))
        with open(name, "w") as f:
            f.write(yaml.dump(p[1], default_flow_style=False, sort_keys=False))
