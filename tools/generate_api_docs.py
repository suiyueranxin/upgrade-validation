#!env python3

import csv
import json
import os
import re
import shutil
import sys
import time
import logging as log
import yaml

SCRIPT_DIR = sys.path[0]
sys.path.append(SCRIPT_DIR + "/../")
from pylibs.openapi import merge_specs
from pylibs.fileops import get_from_github, get_from_github_or_local, download_repo_from_github, read_from_url_or_file


GLOBALTITLE = "SAP Data Intelligence Service APIs"
GROUPS = ["definitions", "components", "parameters", "responses" ]
PARAM_DEF_FILE = os.path.join("parameters_definitions.yaml")

# use local bootprint, if available. Otherwise, use a docker container.
bootprint_cmd = "bootprint openapi {in_dir}/{in_file} {in_dir}/{out_dir} > /dev/null" # for local bootprint
if os.system("bootprint -h > /dev/null 2> /dev/null") != 0:
    print("no local bootprint found, using docker container")
    bootprint_cmd = "docker run --rm -it \
    -v $PWD/{in_dir}:/repos -v $PWD/{in_dir}/{out_dir}:/bp-out \
    -u $(id -u $USER):$(id -g $USER) \
    bayviewtechnologies/bootprint-openapi \
    bootprint openapi repos/{in_file} /bp-out > /dev/null" # using docker image

# some global variables
branch = ""
outdir = ""

####################################
### Check command-line arguments ###
####################################
def parse_args():
    global branch, outdir
    if len(sys.argv) != 3:
        log.info("Generate API documentation for SAP Data Intelligence Services")
        log.info("usage: " + __file__ + " <branch> <outdir>")
        exit(1)

    branch = sys.argv[1]
    outdir = sys.argv[2]

################################################
### Fetch Swagger specifications from GitHub ###
################################################

def fetch_swagger_specs():
    print("## Fetching Swagger specifications")
    swagger_specs = json.loads(open(SCRIPT_DIR + "/../tests/api/swagger_specs.json").read())
    repos = swagger_specs['repositories']
    if not repos:
        log.error("No repositories found!")
        exit(1)

    swaggerFiles = []
    for repo in repos:
        repo_name = repo['name']
        paths = repo['swaggerFiles']
        if not paths:
            log.info("No files found for %s, ignoring.", repo_name)
            continue
        for path in paths:
            if "://" in path:
                # download from url
                fullpath = os.path.join(repo_name, path[path.rfind("/")+1:])
                file_content = read_from_url_or_file(path)
            else:
                # download from github. don't cache files, as these might be overwritten by merge_swagger_specs()
                fullpath = os.path.join(repo_name, path)
                file_content = get_from_github_or_local(repo_name, path, branch)
            if file_content:
                dirpath = os.path.splitext(fullpath)[0]
                targetdir = os.path.join(outdir, dirpath)
                targetfile = os.path.join(targetdir, "swagger.yaml")
                targetfile = os.path.join(outdir, fullpath)
                if not os.path.exists(os.path.dirname(targetfile)):
                    os.makedirs(targetdir)
                # will overwrite existing files
                with open(targetfile, "w", encoding="UTF-8") as f:
                    f.write(file_content)
                    f.close
                swaggerFiles.append(targetfile)
            else:
                log.warning("Error fetching file %s. No documentation will be generated for this specification!", targetfile)
    return [repos, swaggerFiles]


#################################
### Fetch Schemas from GitHub ###
#################################

def copy_schema_files():
    print("## Fetching Schemas")
    schema_dir = os.path.join(outdir, "datahub-app-data-" + branch)
    spec_dir = os.path.join(outdir, "bdh/datahub-app-data", "src/apps/dh-app-metadata/spec")

    download_repo_from_github("bdh/datahub-app-data", branch, remove_archive=True, outdir=schema_dir)
    # Copy xml schemas referenced from the app-data documentation (no extra formatting)
    schema_dir = os.path.join(schema_dir, "src/apps/dh-app-metadata/spec/schemas")
    for spec in os.scandir(spec_dir):
        if not spec.name.endswith(".yaml"): continue
        spec_path = os.path.join(spec_dir, spec.name).replace(".yaml", "/schemas")
        log.debug("copying %s ===> %s", schema_dir, spec_path)
        ##shutil.copytree(schema_dir, spec_path)
        ## TODO: use copytree instead of system call
        if not os.path.isdir(spec_path):
            os.makedirs(spec_path)
        os.system("cp " + schema_dir + "/* " + spec_path)


####################################
### Merge Swagger specifications ###
####################################

def merge_swagger_specs():
    print("## Merging Swagger specifications")


    for module in ["metadata", "preparation"]:
        ignore_redundant_keys = False
        spec_dir = "{}/bdh/datahub-app-data/src/apps/dh-app-{}/spec/".format(outdir, module)
        if module == "metadata":
            ignore_redundant_keys = True

            # Specs in metadata may reference definitions / parameters from other files.
            # Merge all into one file to make sure all referenced defs/params are available when checking
            for spec_file in os.scandir(spec_dir):
                spec = os.path.join(spec_dir, spec_file.name)
                if not spec.endswith(".yaml") or spec.endswith("swagger.yaml"):
                    # only treat .yaml files, with the exception of swagger.yaml
                    continue
                spec_yaml = yaml.safe_load(open(spec).read())
                if not (os.path.isfile(PARAM_DEF_FILE)):
                    open(PARAM_DEF_FILE, "w").write(yaml.dump(spec_yaml))

                groups_para_def = ["definitions","parameters"]
                log.debug("merging parameter and definitions. current file is  %s", spec_file.name)
                try:
                    para_def_yaml = yaml.safe_load(open(PARAM_DEF_FILE).read())
                    merged_para_def_yaml = merge_specs(para_def_yaml, spec_yaml, groups_para_def, ignore_redundant_keys)
                    open(PARAM_DEF_FILE, "w").write(yaml.dump(merged_para_def_yaml))
                except RuntimeError as ex:
                    log.error("error merging files: %s", ex)
                    log.error("  - %s", PARAM_DEF_FILE)
                    log.error("  - %s", spec)
                    sys.exit(1)

            swagger = os.path.join(spec_dir, "swagger.yaml")
            swagger_yaml = yaml.safe_load(open(swagger).read())
            para_def_yaml = yaml.safe_load(open(PARAM_DEF_FILE).read())
            swagger_merged_yaml = merge_specs(para_def_yaml, swagger_yaml, GROUPS, ignore_redundant_keys)
            open(spec_dir+"swagger.yaml", "w").write(yaml.dump(swagger_merged_yaml))

        for spec_file in os.scandir(spec_dir):
            spec = os.path.join(spec_dir, spec_file.name)
            if not spec.endswith(".yaml") or spec.endswith("swagger.yaml"):
                # only treat .yaml files, with the exception of swagger.yaml
                continue
            base = spec

            ext = os.path.join(os.path.dirname(spec), "swagger.yaml")
            log.info("merging %s", base)
            try:
                base_yaml = yaml.safe_load(open(base).read())
                ext_yaml = yaml.safe_load(open(ext).read())
                merged_yaml = merge_specs(base_yaml, ext_yaml, GROUPS, ignore_redundant_keys)
                open("merged.yaml", "w").write(yaml.dump(merged_yaml))
            except RuntimeError as ex:
                log.error("error merging files: %s", ex)
                log.error("  - %s", base)
                log.error("  - %s", ext)
                sys.exit(1)
            os.rename("merged.yaml", base)



################################
### Calculating dependencies ###
################################

def calc_deps():
    print("## Calculating dependencies")
    old_pwd = os.path.realpath(os.curdir)
    os.chdir("api-dependencies")
    ## TODO: import script instead of calling
    os.system("python3 dependencies.py")
    os.chdir(old_pwd)

################################
### Extracting API summaries ###
################################

def extract_api_summaries(swaggerFiles):
    """Extracts summaries for customer and deprecated API endpoints into respective CSV files."""
    print("## Extracting API summaries")
    for spec in swaggerFiles:
        log.debug("Extracting API summary from %s", spec)
        for tag in ["customer", "deprecated"]:
            ## TODO: import script instead of calling
            os.system("python3 extract_apis.py -t {t} -o csv {s} > {s}.{t}.csv".format(t=tag, s=spec))


def add_used_by_documentation(swaggerFiles):
    """Run API endpoint usage script (cf. add_usage.py)."""
    print("## Adding used-by documentation")
    for targetfile in swaggerFiles:
        repo = "/".join(targetfile.split("/")[1:3])
        log.debug("Extracting used-by info from %s", targetfile)
        ## TODO: import script instead of calling it
        os.system("python3 add_usage.py {} {} api-dependencies/dependencies.csv > tmp.yaml".format(repo, targetfile))
        os.rename("tmp.yaml", targetfile)


def add_spec_links(swaggerFiles):
    """Add externalDocs field to the spec to provide a link to the specification source file"""
    print("## Adding specification links")
    for targetfile in swaggerFiles:
        spec = yaml.safe_load(open(targetfile).read())
        if "externalDocs" not in spec:
            log.debug("Adding specification link as externalDocs to %s", targetfile)
            docs = {}
            docs["description"] = "Specification"
            docs["url"] = os.path.basename(targetfile)
            spec["externalDocs"] = docs
            with open(targetfile, 'w') as f:
                yaml.dump(spec, f)


def get_diagnostics_component_version(component):
    """Determine component version, using information in bdh/diagnostics/foss.json."""
    foss_components = json.loads(get_from_github("bdh/diagnostics", "foss.json", branch, False))['components']
    versions = [c['version'] for c in foss_components if c['name'] == component.lower()]
    if len(versions) != 1:
        log.error("Expected one(!) version number for %s, but got %d", component, len(versions))
        sys.exit(1)
    version = ".".join(versions[0].split(".")[0:2])  # keep only major.minor version
    log.info("%s version: %s", component.title(), version)
    return version


def infer_title(repo, targetfile):
    """Infer the title for a given API file."""
    title = yaml.safe_load(open(targetfile).read()).get("info").get("title")
    if repo == "bdh/datahub-app-base":
        title = title.replace("'", "").replace("@sap/dh-app-", "")
        title = re.sub(r" api$", "", title, flags=re.IGNORECASE)
        title = "AppBase " + title.title() + " API"
    elif repo == "bdh/datahub-app-data":
        filetitle = os.path.basename(targetfile).title().replace(".Yaml", "")
        if title == "@sap/dh-app-metadata":
            title = "Metadata " + filetitle
        elif title == "@sap/dh-app-preparation":
            title = "Preparation " + filetitle
        else:
            title = "File" + filetitle
    elif repo == "bdh/datahub-flowagent":
        title = "Flowagent"
    elif repo == "bdh/rms":
        title = "Replication Management Service"
    elif repo == "bigdataservices/storagegateway":
        title = "Storagegateway"
    else:
        pass
    title = title.replace(" API", "")
    return title


def generate_api_html(targetfile):
    """Generate HTML file for a given API file."""
    print("generating API for {}".format(targetfile))
    targetdir = os.path.dirname(targetfile)
    tmp_dir = "bootprint-tmp"
    tmp_fulldir = os.path.join(outdir, tmp_dir)
    if not os.path.exists(tmp_fulldir):
        os.mkdir(tmp_fulldir)
    ## TODO: can we use a python lib instead of bootprint?
    os.system(bootprint_cmd.format(in_dir=outdir, in_file=targetfile[len(outdir)+1:], out_dir=tmp_dir))
    if not os.path.isfile(tmp_fulldir + "/index.html"):
        log.fatal("Error generating documentation for %s", targetfile)
        sys.exit(1)
    else:
        shutil.move(tmp_fulldir + "/index.html", targetfile + ".bp.html")
        # Also copy bootprint's CSS file
        shutil.copy(tmp_fulldir + "/main.css", os.path.join(targetdir, "main.css"))
    #shutil.copyfile("api-diff/main.css", os.path.join(targetdir, "main.css"))
    return targetdir


def write_api_html(swaggerFiles):
    """Generate HTML files for each API file in swaggerFiles."""
    for targetfile in swaggerFiles:
        generate_api_html(targetfile)


def write_nav_html(swaggerFiles, repos):
    print("## Generating API documentation")

    content = '<div class="container">\n'

    firstlink = ""
    lastrepotitle = ""

    for targetfile in swaggerFiles:
        repo = "/".join(targetfile.split("/")[1:3])

        # Print component title in navigation
        repotitle = [r['title'] for r in repos if r['name'] == repo][0]
        if not repotitle:
            log.error("Missing title!")
            exit(1)
        if not lastrepotitle:
            content += "<h4>" + repotitle + "</h4>\n"
            content += "<ul>\n"
        elif repotitle != lastrepotitle:
            if lastrepotitle == "Core Services":
                content += '  <li><a href="https://prometheus.io/docs/prometheus/' + \
                           get_diagnostics_component_version('prometheus') + \
                           '/querying/api" target="_blank">Prometheus</a></li>\n'
                content += '  <li><a href="https://www.elastic.co/guide/en/elasticsearch/reference/' + \
                           get_diagnostics_component_version('elasticsearch') + \
                           '/rest-apis.html" target="_blank">Elasticsearch</a></li>\n'
            content += "</ul>\n<h4>{}</h4>\n<ul>\n".format(repotitle)
        lastrepotitle = repotitle


        # add link to navigation
        title = infer_title(repo, targetfile)
        linkfile = targetfile.replace(outdir+"/", "") + ".bp.html"
        if os.path.isfile(targetfile):
            content += '  <li><a href="{}" target="main">{}</a></li>\n'.format(linkfile, title)
        else:
            content += '  <li><a href="{}" target="main">BROKEN {}</a></li>\n'.format(linkfile, title)
            #content += '  <li>{}</li>'.format(title)
        if not firstlink:
            firstlink = linkfile

    content += """</ul>
    <h4><i>Summaries</i></h4>
     <ul>
      <li><a href="customer.html" target="main">Customer APIs</a></li>
      <li><a href="deprecated.html" target="main">Deprecated APIs</a></li>
     </ul>
    <br><br><br>
    </div>"""
    write_html("nav.html", content, title=GLOBALTITLE)
    return firstlink

def write_tag_html(swaggerFiles):
    for tag in ["customer", "deprecated"]:
        print("Writing list of {} endpoints".format(tag))
        title = tag.title() + " APIs"
        rem = "<th>Removal Version</th>" if tag == "deprecated" else ""
        content = """<div class="container">
        <h1>{cap} APIs</h1>
        <table class="table table-bordered table-condensed swagger--summary">
        <tr><th>API</th><th>Operation</th><th>Summary</th>{rem}</tr>
        """.format(cap=tag.title(), rem=rem)
        # update summaries
        for targetfile in swaggerFiles:
            repo = "/".join(targetfile.split("/")[1:3])
            with open(targetfile + "." + tag + ".csv") as csvfile:
                for line in csv.reader(csvfile):
                    if not line or len(line) != 4:
                        continue
                    path, method, summary, removal = line
                    if path:
                        m = method.upper()
                        ref = "operation-" + re.sub(r"[\/\{\}\?=]", "-", path) + "-" + method
                        path = path.replace("{", "{{").replace("}", "}}")  # defuse curly braces for _.format_
                        summary = summary.replace("{", "{{").replace("}", "}}")
                        if tag == "deprecated":
                            rem = "<td>" + removal + "</td>"
                        link = targetfile.replace(outdir+"/", "") + ".bp.html"
                        content += """<tr><td>{repo}</td><td class="swagger--summary-path">
                        <a href="{link}#{ref}" target="main">{method} {path}</a>
                        </td><td>{summary}</td>{rem}</tr>\n""".format(
                            repo=repo, link=link, ref=ref, method=m, path=path, summary=summary, rem=rem)
        content += "</table>\n<br><br><br>\n</div>"
        write_html(tag + ".html", content, title=title)

def write_header_html():
    gendate = time.strftime("%Y-%m-%d")
    write_html("header.html", """<div style="margin-left:15px">
    <h1>{title}</h1>
    <h4>Branch: {branch}, Date: {date}, INTERNAL USE ONLY</h4>
    </div>
    """, title=GLOBALTITLE, branch=branch, date=gendate)


def write_index_html(firstlink):
    with open(outdir + "/index.html", "w", encoding="UTF-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="main.css">
  <meta charset="UTF-8">
  <title>{title}</title>
  <frameset rows="100,*">
    <frame src="header.html" name="nav">
    <frameset cols="25%,*">
      <frame src="nav.html" name="nav">
      <frame src="{link}" name="main">
    </frameset>
  </frameset>
</head>
<body>
</body>
</html>""".format(title=GLOBALTITLE, link=firstlink))
    shutil.copyfile(outdir + "/bootprint-tmp/main.css", os.path.join(outdir, "main.css"))


def write_html(filename, content, **kwargs):
    full_name = os.path.join(outdir, filename)
    text = """\
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="main.css">
  <meta charset="UTF-8">
  <title>{title}</title>
</head>
<body>""" + content + """</body>
</html>
"""
    with open(full_name, "w", encoding="UTF-8") as f:
        f.write(text.format(**kwargs))

def main():
    log.basicConfig(level=log.INFO, format="%(levelname)-7s %(message)s")
    parse_args()
    repos, swaggerFiles = fetch_swagger_specs()
    copy_schema_files()
    merge_swagger_specs()
    calc_deps()
    extract_api_summaries(swaggerFiles)
    add_used_by_documentation(swaggerFiles)
    add_spec_links(swaggerFiles)
    firstlink = write_nav_html(swaggerFiles, repos)
    write_api_html(swaggerFiles)
    write_tag_html(swaggerFiles)
    write_header_html()
    write_index_html(firstlink)

main()
