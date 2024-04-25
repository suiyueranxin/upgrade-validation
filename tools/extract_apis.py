#!/usr/bin/python3

import argparse
import os
import sys
import yaml

sys.path.append(sys.path[0] + "/../")
from pylibs.openapi import collect_definition_refs, export_csv, has_tag, matches_tags, METHOD_TYPES, filter_paths, purge_unused_definitions

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extract API endpoints from an OpenAPI/Swagger specification")
    parser.add_argument("spec", help="OpenAPI/Swagger specification file")
    parser.add_argument("-t", nargs="?", dest="tags", help="comma-separated list of tags to match (use 'deprecated' to extract deprecated paths)")
    parser.add_argument("-o", nargs="?", dest="format", default="yaml", help="output format (yaml, csv)")
    args = parser.parse_args()
    format = args.format.lower()
    spec = yaml.safe_load(open(args.spec).read())

    # extract based on tags
    if args.tags:
        tags = args.tags.split(",")
        filter_paths(spec, tags)
        purge_unused_definitions(spec)

    # print result
    if format == "csv":
        result = export_csv(spec)
    elif format == "yaml":
        result = yaml.dump(spec, default_flow_style=False, sort_keys=False)
    else:
        raise ValueError("unsupported format: " + format)
    print(result)
