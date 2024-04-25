#!/usr/bin/python3

import argparse
import csv
import datetime
import io
import logging as log
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.append(sys.path[0] + "/../../")
from pylibs.fileops import get_from_github
from pylibs.logstream import LogStream

def copy_dockerfile(component, dockerfile, version, out):
    search = "../compare-dockerfile/components/" + component + "-" + version
    found = False
    for suffix in ["", "-linuxx86_64"]:
        if os.path.isdir(search + suffix):
            full_dockerfile = os.path.join(search + suffix, dockerfile)
            if not os.path.isfile(full_dockerfile):
                log.error("File not found: %s", full_dockerfile)
                break
            log.info("Copying %s", full_dockerfile)
            target_file = out + "/" + component + "/" + version + "/" + dockerfile
            target_dir = os.path.dirname(target_file)
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)
            shutil.copy(full_dockerfile, target_file)
            found = True
    if not found:
        raise RuntimeError("Error copying " + dockerfile + " from " + search + "*")
    return


def create_empty_dockerfile(component, dockerfile, version, out):
    target_file = out + "/" + component + "/" + version + "/" + dockerfile
    target_dir = os.path.dirname(target_file)
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)
    with open(target_file,"w") as f:
        f.write("")
    return


def make_openapi_diff_csv(args):
    # run api compatibility test to generate diff as csv
    # TODO: execute directly in python
    test_dir = "../../tests/api"
    if not os.path.isdir(test_dir):
        raise RuntimeError("API test directory not found: " + test_dir)
    with tempfile.TemporaryDirectory() as api_temp:
        api_diff = os.path.join(api_temp, "api-diff.csv")
        cmd = ["python3", "swagger_test.py", "--base=" + args.base, "--target=" + args.target, "-c", api_diff]
        log.info("Running API compatibility tests: {}".format(cmd))
        if subprocess.call(cmd, cwd=test_dir) != 0:
            log.warning("error while executing api tests")
        shutil.copy(api_diff, os.path.join(args.out, "api-diff.csv"))


def make_docker_diff_csv(args):
    # compare dockerfiles
    # TODO: execute directly in python
    docker_compare_dir = "../compare-dockerfile"
    if not os.path.isdir(docker_compare_dir):
        raise RuntimeError("dockerfile test directory not found: " + docker_compare_dir)
    with tempfile.TemporaryDirectory() as docker_compare_temp:
        docker_results = os.path.join(docker_compare_temp, "docker-diff.csv")
        log.info("Running Dockerfile comparison")
        if subprocess.call(["python3", "compare-dockerfiles.py", "--base", args.base, "--target", args.target, "--csv", docker_results], cwd=docker_compare_dir) != 0:
            log.error("error comparing dockerfiles")
            sys.exit(1)
        shutil.copy(docker_results, os.path.join(args.out, "docker-diff.csv"))


def make_diff(base, target, out):
    log.info("Creating diff %s", out)
    diff_cmd = "diff -b -u " + base + " " + target + "; exit 0"
    diff = subprocess.check_output(diff_cmd, shell=True, universal_newlines=True)
    with open(out, "w") as f:
        f.write(diff)
    diff2html_cmd = "python diff2html.py -i " + out
    diff2html = subprocess.check_output(diff2html_cmd, shell=True, universal_newlines=True)
    with open(out + ".html", "w") as f:
        f.write(diff2html)
    return


def make_openapi_diff_html(args):
    openapi = io.StringIO()
    last_repo = ""
    last_yaml = ""
    with open(os.path.join(args.out, "api-diff.csv"),"r") as f:
        csv_reader = csv.reader(f, delimiter=",")
        for row in csv_reader:
            repo = row[0]
            base_tag = row[1]
            base_version = base_tag.replace("rel/","")
            target_tag = row[2]
            target_version = target_tag.replace("rel/","")
            action = row[3]
            scope = row[4]
            path = row[5]
            reason = row[6]
            yaml_index = path.find(".yaml")
            yaml = path[:yaml_index+5]
            full_yaml_base = repo + "/" + base_tag + "/" + yaml
            full_yaml_target = repo + "/" + target_tag + "/" + yaml
            full_yaml_diff = repo  + "/rel/" + base_version + ".." + target_version + "/" + yaml
            if yaml != last_yaml:
                for y in [full_yaml_base,full_yaml_target, full_yaml_diff]:
                    dir = os.path.join(args.out,os.path.dirname(y))
                    if not os.path.isdir(dir):
                        os.makedirs(dir)
                with open(os.path.join(args.out,full_yaml_base),"w") as f:
                    f.write(get_from_github(repo, yaml, base_tag, False))
                if action != "removed-spec":
                    with open(os.path.join(args.out,full_yaml_target),"w") as f:
                        f.write(get_from_github(repo, yaml, target_tag, False))
                make_diff(os.path.join(args.out,full_yaml_base), os.path.join(args.out,full_yaml_target), os.path.join(args.out,full_yaml_diff))
                last_yaml = yaml
            if repo != last_repo:
                if last_repo:
                    openapi.write("</table>\n")
                openapi.write("<h2>" + repo + " " + base_version + " &rarr; " + target_version + "</h2>\n")
                openapi.write("<table>\n")
                openapi.write("<tr><th>Action</th><th>Scope</th><th>Path</th><th>Reason</th></tr>\n")
                last_repo=repo
            line = '<tr><td width="10%"><span class="{a}">{b}</span></td><td width="5%"><span class="{s}">{s}</span></td><td><a href="{d}.html">{p}</a></td><td width="20%">{r}</td></tr>\n'
            openapi.write(line.format(a=action, b=action.replace("-"," "), s=scope, d=full_yaml_diff, p=path, r=reason ))
    openapi.write("</table>\n")
    return openapi.getvalue()


def make_docker_diff_html(args):
    dockerfiles = io.StringIO()
    last_component = ""
    last_file = ""
    with open(os.path.join(args.out, "docker-diff.csv"),"r") as f:
        csv_reader = csv.reader(f, delimiter=",")
        next(csv_reader)
        for row in csv_reader:
            component = row[0]
            base_version = row[1]
            target_version = row[2]
            kind = row[3]
            dockerfile = row[4]
            treepath = row[5]
            from_ = row[6]
            to_ = row[7]
            if component != last_component:
                if last_component:
                    dockerfiles.write("</table>\n")
                dockerfiles.write("<h2>" + component + " " + base_version + " &rarr; " + target_version + "</h2>\n")
                dockerfiles.write("<table>\n")
                dockerfiles.write("<tr><th>Action</th><th>File</th><th>Entry</th><th>From</th><th>To</th></tr>\n")
                last_component = component
            if dockerfile.startswith("vflow/dockerfiles/"):
                dockerfile = "content/files/" + dockerfile
            if treepath.startswith("Tags/"):
                dockerfile = dockerfile + "Tags.json"
            else:
                dockerfile = dockerfile + "Dockerfile"
            file_short = dockerfile.replace("content/files/vflow/dockerfiles/","")
            file_base = component + "/" + base_version + "/" + dockerfile
            file_target = component + "/" + target_version + "/" + dockerfile
            file_diff = component + "/" + base_version + ".." + target_version + "/" + dockerfile
            if dockerfile != last_file:
                # copy or create base version
                if kind == "added-file":
                    create_empty_dockerfile(component, dockerfile, base_version, args.out)
                else:
                    copy_dockerfile(component, dockerfile, base_version, args.out)
                # copy or create target version
                if kind == "removed-file":
                    create_empty_dockerfile(component, dockerfile, target_version, args.out)
                else:
                    copy_dockerfile(component, dockerfile, target_version, args.out)
                target_dir = os.path.join(args.out, os.path.dirname(file_diff))
                if not os.path.isdir(target_dir):
                    os.makedirs(target_dir)
                make_diff(os.path.join(args.out, file_base), os.path.join(args.out, file_target), os.path.join(args.out, file_diff))
                last_file = dockerfile
            line = '<tr><td width="10%"><span class="{k}">{l}</span></td><td width="25%"><a href="{d}.html">{s}</a></td><td width="10%"><tt>{t}</tt></td><td><tt>{f}</tt></td><td><tt>{o}</tt></td></tr>\n'
            dockerfiles.write(line.format(k=kind, l=kind.replace("-", " "), d=file_diff, s=file_short, t=treepath, f=from_, o=to_))
    dockerfiles.write("</table>\n")
    return dockerfiles.getvalue()


if __name__ == '__main__':

    # parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate API difference for SAP Data Intelligence")
    parser.add_argument("base", help="base version of SAP Data Intelligence, e.g. 2006.1.8")
    parser.add_argument("target", help="target version of SAP Data Intelligence, e.g. 2007.8.3")
    parser.add_argument("out", help="output folder")
    args = parser.parse_args()
    
    # set log level
    log.basicConfig(level="INFO", format="%(levelname)-7s %(message)s")

    # create output directory
    if not os.path.isdir(args.out):
        os.makedirs(args.out)

    # compute diffs as csv
    make_openapi_diff_csv(args)
    make_docker_diff_csv(args)

    # generate html from template
    openapi = make_openapi_diff_html(args)
    dockerfiles = make_docker_diff_html(args)
    with open("diff-template.html", "r") as template:
        html = template.read()
        html = html.replace("%base", args.base)
        html = html.replace("%target", args.target)
        html = html.replace("%openapi", openapi)
        html = html.replace("%dockerfiles", dockerfiles)
        with open(os.path.join(args.out, "index.html"), "w") as result:
            result.write(html)

    # copy stylesheet
    shutil.copy("main.css", os.path.join(args.out, "main.css"))
