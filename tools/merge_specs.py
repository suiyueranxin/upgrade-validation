#!/usr/bin/python3

import argparse
import os
import sys
import yaml

sys.path.append(sys.path[0] + "/../")
from pylibs.openapi import merge_specs

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Merge two OpenAPI/Swagger specifications")
    parser.add_argument("base", help="base file to be used for merging")
    parser.add_argument("ext", help="extension file")
    parser.add_argument("-g", help="specification groups (comma-separated)", nargs="?", metavar="groups")
    args = parser.parse_args()
    groups = [ "paths", "definitions", "components", "parameters", "responses" ]
    ignore_redundant_keys = False
    if args.g:
        groups = args.g.split(",")
    base = yaml.safe_load(open(args.base).read())
    ext = yaml.safe_load(open(args.ext).read())
    merge_specs(base, ext, groups, ignore_redundant_keys)
    print(yaml.dump(base, default_flow_style=False, sort_keys=False))
