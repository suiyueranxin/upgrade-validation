import argparse
import os
import sys
import logging as log
import json
import csv
import time
import re
import shutil

sys.path.append(sys.path[0] + "/../../")
sys.path.append(sys.path[0] + "/../../tests/vflow")
from pylibs.fileops import download_repo_from_github
import pylibs.versioning as versioning
from tests.vflow.common import get_all_operators
from tests.vflow.deprecation import get_deprecations

GLOBALTITLE = "SAP Data Intelligence -- Operator List"


def parse_options(parser):
    """Parse command line options."""
    parser.set_defaults()
    parser.add_argument("version", help="Version to document, in the form of a git refspec.")
    #parser.add_argument("csv") # csv generation deactivated for now
    parser.add_argument("html")
    parser.add_argument('--log-level', default='INFO',
                        help="Level of logging. One of ERROR, WARNING, INFO, or DEBUG")
    return parser.parse_args()


def generate_csv(repo, operators, csv_file, deprecations):
    """Generate a CSV file with operator metadata."""
    writer = csv.writer(csv_file)
    writer.writerow(["repo", "path", "name", "owner", "status", "removal-date"])
    for op in operators:
        name = str(op.get('description'))
        status = "deprecated" if op.get('!path') in deprecations else "active"
        owner = op.get('responsible')
        removal_date = op.get('x-removal-date')
        writer.writerow([repo, op.get('!path'), name, owner, status, removal_date])


def get_solutions():
    with open("../../tests/vflow/solutions.json") as f:
        solutions = json.load(f)['solutions']
    return solutions


def gen_html_header(branch):
    return """<!DOCTYPE html>
    <html>
    <head>
      <link rel="stylesheet" href="main.css">
      <meta charset="UTF-8">
      <title>{title}</title>
    </head>
    <body>
    <div style="margin-left:15px">
      <h1>{title}</h1>
      <h4>Branch: {branch}, Date: {date}, INTERNAL USE ONLY</h4>
    </div>
    """.format(title=GLOBALTITLE,
               branch=branch,
               date=time.strftime("%Y-%m-%d"))


def gen_html_table(repo, operators, operator_dir):
    content = '<h2 id="{r}">{r}</h2>\n'.format(r=repo)
    content += '<table>\n<tr><th>Path</th><th>Name</th><th>Owner</th><th>Status</th></tr>\n'
    for op in operators:
        path = op.get('!path')
        name = str(op.get('description'))
        status = "active"
        if path in deprecations:
            status = "deprecated"
        elif op.get("versionStatus"):
            status = op['versionStatus'].lower()

        owner = op.get('responsible')
        # TODO: we don't (yet) have removal dates for operators. Would be nifty.
        removal_date = op.get('x-removal-date')

        gh_link = "https://github.wdf.sap.corp/" + repo
        if ".operators.com.sap" in path or ".operators.invisible" in path: # special case for subengines
            gh_link += operator_dir.replace("repos/"+repo, "/blob/master") + "subengines/"
        else:
            gh_link += operator_dir.replace("repos/"+repo, "/blob/master") + "operators/"
        gh_link += path.replace(".", "/")

        content += '<tr>'
        content += '<td><a href="{}">{}</a></td><td>{}</td>'.format(gh_link, path, name)
        if owner != None: # get human-readable name for owner
            owner_name = " ".join(owner.split("@")[0].split(".")).title()
            if not owner_name.upper().startswith("DL-"):  # if it's not a DL:
                owner_name = re.sub(r"[0-9]*$", "", owner_name)  # remove any numbers at name's end
            content += '<td><a href="mailto:{}">{}</a></td>'.format(owner, owner_name)
        else:
            content += '<td>{}</td>'.format(owner)
        if status == "deprecated" and removal_date:
            # TODO: once we have actual removal dates, we can color-code this further:
            #       e.g. removal date far away / due very soon / overdue
            content += '<td class="state_{s}">{s}, removal: {d}</td>'.format(s=status, d=removal_date)
        else:
            content += '<td class="state_{s}">{s}</td>'.format(s=status)
        content += '</tr>\n'
    content += '</table>\n'
    return content



def find_vflow_dir(base_path, candidates):
    """Find the directory containing operators, given a base path and a list of candidates."""
    for path in candidates:
        full_path = base_path + "/" + path + "/"
        if os.path.isdir(full_path):
            return full_path
    raise Exception("could not find vflow operator directory in " + base_path)


# generate HTML file with operator metadata
if __name__ == '__main__':
    options = parse_options(argparse.ArgumentParser())
    log.basicConfig(level=options.log_level, format="%(levelname)-7s %(message)s")

    header_t = gen_html_header(options.version)

    navi_t = '<h2>Repositories</h2>\n<ul>\n'
    tables_t = ''
    for solution in get_solutions():
        repo = solution['repository']

        if not solution.get('generate_docs'):
            log.info("skipping solution %s", repo)
            continue

        version = options.version
        if versioning.is_version_str(version):
            version = versioning.handle_component(repo, version)
        log.info("checking out %s, branch %s", repo, version)

        solution_dir = os.path.join("repos", repo)
        download_repo_from_github(repo, version, outdir=solution_dir)
        operator_dir = find_vflow_dir(solution_dir, solution['operator-dirs'])
        operators = get_all_operators(operator_dir)
        deprecations = get_deprecations(operator_dir, operators, solution.get("settings-path"))
        deprecations = [x for k in deprecations for x in deprecations[k]]

        # open csv file and fill with data -- deactivated for now
        ## generate_csv(repo, operators, options.csv, deprecations)

        navi_t += '<li><a href="#{r}">{r}</a></li>'.format(r=repo)
        tables_t += gen_html_table(repo, operators, operator_dir)
    navi_t += '</ul>\n'
    content = header_t + navi_t + tables_t + '</body>\n</html>\n'

    if not os.path.exists(options.html):
        os.makedirs(options.html)
    with open(os.path.join(options.html, "index.html"), "w", encoding="UTF-8") as f:
        f.write(content)
    shutil.copyfile("main.css", os.path.join(options.html, "main.css"))
