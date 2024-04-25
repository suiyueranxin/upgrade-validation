#!/usr/bin/python3

import argparse
import csv
import os
import re
import sys
import yaml

sys.path.append(sys.path[0] + "/../")
from pylibs.openapi import get_description, is_deprecated


def generate_used_by_doc(files, is_deprecated):
    doc = ""
    if files:
        doc += "\n<span style=\"font-weight:bold;color:#555\">USED BY</span>\n"
        for f in files:
            match = re.search("^([^/]+/[^/]+)/(.+)$", f)
            repo = match.group(1)

            if len(match.group(2).split(":")) == 2:
                path = match.group(2).replace(":", "#L")
                doc += "- <a href=\"https://github.wdf.sap.corp/{}/blob/master/{}\" target=\"_blank\">{}</a>\n".format(repo,path,f)

            if len(match.group(2).split(":")) > 2:
                path =match.group(2).split(":")[0]
                first_line =match.group(2).split(":")[1]
                doc += "- <a href=\"https://github.wdf.sap.corp/{}/blob/master/#L{}\" target=\"_blank\">{}</a>\n".format(
                    repo, path+"#L"+first_line, path+":"+first_line)
                for line in match.group(2).split(":")[2:]:
                    doc += " <a href=\"https://github.wdf.sap.corp/{}/blob/master/#L{}\" target=\"_blank\">{}</a>\n".format(
                        repo, path+"#L"+line,line)

    if is_deprecated:
        doc += "\n<span style=\"font-weight:bold;color:#555\">DEPRECATION</span>\n"
        doc += "\nThis endpoint is **deprecated** and should not be used anymore.\n"
    return doc


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Add usage documentation to OpenAPI/Swagger specifications")
    parser.add_argument("repo", help="Repository containing specification")
    parser.add_argument("spec", help="OpenAPI/Swagger specification file")
    parser.add_argument("deps", help="CSV files with dependencies")
    args = parser.parse_args()
    spec = yaml.safe_load(open(args.spec).read())
    paths_used_by = {}
    if "paths" in spec:
        for path in spec["paths"]:
            paths_used_by[path + ":ALL"] = []
            for method in spec["paths"][path]:
                paths_used_by[path + ":" + method.upper()] = []
    if not paths_used_by:
        print("No paths found in spec!")
        sys.exit(1)

    # Collect dependencies
    deps_file = open(args.deps)
    deps_reader = csv.reader(deps_file, delimiter=",")
    headers = next(deps_reader, None)
    num_matches = 0
    for row in deps_reader:
        src_repo = row[0]
        src_file = row[1]
        lines_arr = row[2]
        uses_api = row[3]
        uses_endpoint = row[4]
        uses_regex = row[5]
        line_num = ":" + lines_arr
        if ":" not in uses_endpoint:
            uses_endpoint += ":ALL"
        entry = "{}/{}{}".format(src_repo, src_file, line_num)
        if args.repo != uses_api:
            continue
        for path in paths_used_by:
            if uses_endpoint == path and not entry in paths_used_by[path]:
                paths_used_by[path].append(entry)
                num_matches += 1

    # Update descriptions
    for path in spec["paths"]:
        files_all = paths_used_by[path + ":ALL"]
        for method in spec["paths"][path]:
            if not isinstance(spec["paths"][path][method], dict):
                continue
            description = get_description(spec["paths"][path][method])
            files = files_all
            path_method = path + ":" + method.upper()
            if path_method in paths_used_by:
                files.extend(paths_used_by[path_method])
            used_by = generate_used_by_doc(files, is_deprecated(spec["paths"][path][method]))
            description += "\n" + used_by
            spec["paths"][path][method]["description"] = description

    # Print the result
    print(yaml.dump(spec))
