#!/usr/bin/python3

import sys
import os
import re
import logging as log
import json
import yaml

sys.path.append(sys.path[0] + "/../../")
from pylibs.fileops import get_from_github_or_local, download_repo_from_github, read_from_url_or_file


# Minimum length (counted in "/" characters) for an API endpoint to be considered specific
MIN_ENDPOINT_LENGTH = 2

FILE_WHITELIST = re.compile(".*\.(go|cpp|py|java|js|ts)$")

# List of API endpoints with very generic names (as regular expressions).
# These should be excluded from the heuristics of detecting use of an API.
# TODO: load from dep-blacklist.yaml
FILE_BLACKLIST = re.compile(".*(test|/\.yarn/).*")

# origin of this list: In repo hanalite-releasepack, execute:
#   grep -o '\(https://github.wdf[^()]*\)' CHANGELOG_master.md | cut -d/ -f1-5 | sort | uniq
CODE_REPOSITORIES=[
    "bdh/datahub-app-base",
    "bdh/datahub-app-data",
    "bdh/datahub-dq-integration",
    "bdh/datahub-flowagent",
    "bdh/datahub-hana",
    "bdh/diagnostics",
    "bigdataservices/storagegateway",
    "dsp/dsp-release",
    "velocity/datahub-operator",
    "velocity/data-tools-ui",
    "velocity/docker-base",
    "velocity/docker-base-sles",
    "velocity/hl-license-manager",
    "velocity/security-operator",
    "velocity/uaa",
    "velocity/ui-components",
    "velocity/vflow",
    "velocity/vflow-sub-abap",
    "velocity/vora-tools",
    "velocity/vsolution",
    "velocity/vsystem",
    "velocity/vsystem-ui",
    "dsp/ml-api",
    "dsp/ml-dm-api",
    "dsp/ml-tracking-server",
]


def load_yaml(filename=None, string=None):
    """Load yaml from a string or file, using the fast C-based loader if possible.
    If a non-null string is present, use that. Otherwise, try loading & parsing the file.
    """
    # determine parser to use. If possible, use the much faster c-based loader.
    yaml_loader = yaml.CSafeLoader if "CSafeLoader" in yaml.__dict__ else yaml.SafeLoader
    if not string:
        string = open(filename).read()
    try:
        result = yaml.load(string, Loader=yaml_loader)
        return result
    except yaml.scanner.ScannerError:
        log.fatal("could not parse YAML from %s", filename)
        sys.exit(-1)


def load_swagger_specs():
    """Load Swagger specification test metadata from swager_specs.json and return it as dict."""
    return json.load(open("../../tests/api/swagger_specs.json"))


def get_swagger_files():
    """Get flat list of Swagger specificaton paths to be tested. A path consists of the repository name followed by the file path."""
    repos = {}
    specs = load_swagger_specs()
    for r in specs["repositories"]:
        files = []
        for f in r["swaggerFiles"]:
            files.append("{}/{}".format(r["name"], f))
        repos[r["name"]] = files
    return repos


def is_significant(endpoint):
    """Returns true iff the endpoint is specific enough to identify an API"""
    global INCONCLUSIVE
    # If the endpoint URL is too short, it's usually not very specific
    if endpoint.count("/") < MIN_ENDPOINT_LENGTH:
        return False

    # Make sure it's not in the list of inconclusive expressions (see above)
    for expr in INCONCLUSIVE:
        if re.compile(expr).match(endpoint):
            log.debug("inconclusive endpoint %s removed, matches %s", endpoint, expr)
            return False

    return True


def to_regex(swagger_path):
    return re.compile(re.sub(r'{([^{}]*)}', '.+', swagger_path))


def get_api_endpoints(base_path):
    endpoints = {}
    for path, subdirs, subfiles in os.walk(base_path):
        if "swagger.yaml" in subfiles:
            filename = os.path.join(path, "swagger.yaml")
            swag = load_yaml(filename=filename)['paths']
            endpoints.update(swag)
    return endpoints


def extract_all_op_ids(name, swagger):
    all_methods = {}
    for method in swagger.keys():
        if method in ["get", "post", "put", "delete", "patch"]:
            op_id = swagger[method].get('operationId')
            if not op_id:
                continue
            caller = swagger[method].get('tags')
            camelCase_degree = len(re.split(r"[A-Z._]", op_id)) - 1
            if len(op_id) > 6 and camelCase_degree >= 2:
                # If the opId is long and complicated enough, search for '.opId('
                all_methods[(name, method.upper())] = re.compile("\\." + op_id + "\(")
            elif caller:
                # If it is too short, but has a caller tag, search for 'tag.opId('
                all_methods[(name, method.upper())] = re.compile(caller[0] + "\\." + op_id + "\(")
            else:
                # Otherwise, the opId is not suited for identification. Skip it.
                log.debug("ignoring inconclusive .ts operationId %s for endpoint %s", op_id, name)
    return all_methods


def get_typescript_endpoints(repo):
    endpoints = get_api_endpoints("repos/" + repo)
    op_ids = {}
    for endpoint in endpoints:
        op_ids.update(extract_all_op_ids(endpoint, endpoints[endpoint]))
    return op_ids


def xdotify_name(name):
    """Make a name usable as an xdot node identifier."""
    return name.replace('/', '_').replace('-', '_')


def write_xdot(dependencies, filename):
    """Write the dependency graph into an xdot file."""
    log.info("Generating dependency graph in %s", filename)
    xdot = open(filename, 'w')
    xdot.write("digraph {\n")
    xdot.write("  node [shape=polygon, sides=6, style=filled, fillcolor=yellow]\n")

    nodes = set()
    edges = {}
    # gather nodes, group together parallel edges
    for dep in dependencies:
        nodes.add(dep.target_repo)
        nodes.add(dep.source_api)
        edge_key = dep.source_api + "-->" + dep.target_repo
        if edges.get(edge_key):
            edges[edge_key] = [dep.target_repo, dep.source_api, edges[edge_key][2]+1]
        else:
            edges[edge_key] = [dep.target_repo, dep.source_api, 1]

    for node in nodes:
        xdot.write('  {} [label="{}"]\n'.format(xdotify_name(node), node))
    for _, dep in edges.items():
        xdot.write('  {src} -> {tgt} [label="({num})"]\n'.format(
            src=xdotify_name(dep[0]),
            tgt=xdotify_name(dep[1]),
            num=dep[2]))

    xdot.write("}\n")
    xdot.close()


class Dependency:
    def __init__(self,
                 source_api, source_endpoint, source_regex,
                 target_repo, target_file, target_lines):
        self.source_api = source_api
        self.source_endpoint = source_endpoint
        self.source_regex = source_regex
        self.target_repo = target_repo
        self.target_file = target_file
        self.target_file_lines = target_lines

    def as_xdot(self):
        return '  {} [label="{}"]'.format(xdotify_name(self.source_api),
                                          xdotify_name(self.target_repo))

    def csv_header():
        return "repo,file,line_numbers,uses_api,uses_endpoint,uses_regex\n"

    def as_csv(self):
        # multiple lines are separated by ":" to avoid confusion with the CSV separator
        lines = ":".join([str(x) for x in self.target_file_lines])
        return ",".join([self.target_repo,
                         self.target_file,
                         lines,
                         self.source_api,
                         self.source_endpoint,
                         self.source_regex])


def write_csv(dependencies, filename):
    log.info("Writing list of %d dependencies to %s", len(dependencies), filename)
    csv = open(filename, 'w')
    csv.write(Dependency.csv_header())
    for dep in dependencies:
        csv.write(dep.as_csv() + "\n")
    csv.close()


def download_all_repositories(version):
    for repo in CODE_REPOSITORIES:
        download_repo_from_github(repo, version)


def get_all_endpoints(repositories):
    """Compile a list of all significant endpoints from all repositories. An
    endpoint is considered significant if it reliably detects use of an API, i.e. it is
    (a) unique to its API, i.e. no other API uses the same endpoint, and
    (b) is sufficiently long (in terms of how many '/' characters it contains), and
    (c) does not have a too common name (e.g. '/version', '/healthcheck'). """
    endpoints = {}
    ts_endpoints = {}
    for repo, files in repositories:
        endpoints[repo] = []
        log.debug("collecting endpoints from %s", repo)
        ts_endpoints[repo] = get_typescript_endpoints(repo)

        for swagger_file in files:
            # load endpoints and filter them for significance (see docstring)
            file_in_repo = swagger_file[len(repo):]
            if "://" in file_in_repo:
                file_in_repo = file_in_repo[1:]
                text = read_from_url_or_file(file_in_repo)
            else:
                text = get_from_github_or_local(repo, file_in_repo, "master")
            if not text:
                log.warning("File %s not found in repository %s", file_in_repo, repo)
                continue
            # Load the swagger file
            swag = load_yaml(string=text, filename=repo + "/" + file_in_repo)
            endpoints[repo] += filter(is_significant, swag['paths'].keys())

    endpoints = deduplicate_endpoints(endpoints)

    # convert to regex dict
    for repo in endpoints:
        endpoints[repo] = {ep:to_regex(ep) for ep in endpoints[repo]}

    return [endpoints, ts_endpoints]


def deduplicate_endpoints(endpoints):
    """Remove any entry present in more than one list within endpoints.
    This is similar to deduplication, but instead of removing all but one
    instance of duplicate entries, _all_ entries are removed.
    NB: This should NOT be called on lists of compiled regular expressions,
    as the "in" and comparison operators behave strangely in this case,
    leading to non-deterministic behaviour.
    """
    for repo, eps in endpoints.items():
        # need to use eps.copy() because elements may be deleted from eps during iteration. Also,
        # duplicates might affect more than 2 repos, and all items have to be checked for all repos.
        eps_copy = eps.copy()
        for other_repo, other_eps in endpoints.items():
            if repo == other_repo:
                continue
            for ep in eps_copy:
                if ep in other_eps:
                    log.debug("removing duplicate endpoint %s from %s and %s", ep, repo, other_repo)
                    # using while loops here because remove(ep) only removes ep's first occurrence
                    while ep in eps:
                        eps.remove(ep)
                    while ep in other_eps:
                        other_eps.remove(ep)

    for repo, eps in endpoints.items():
        log.debug("- endpoints considered for %s: %s", repo, [e for e in eps])

    return endpoints



def occurrences_in_string_simple(text, regex):
    """Return [0] if regex is in text, empty list otherwise.
    Much faster than occurrences_in_string.
    """
    if regex.search(text):
        return [0]
    return []

def occurrences_in_string(text, regex):
    """Return a list of all line numbers in $text where $regex matches."""
    occurrences = []
    for idx, line in enumerate(text.splitlines()):
        if regex.search(line):
            if not ("import " in line):
                occurrences.append(idx + 1)
    return occurrences


INCONCLUSIVE = load_yaml(filename="ep-blacklist.yaml")['inconclusive']
if __name__ == '__main__':
    log.basicConfig(level="INFO",
                    format="%(levelname)-7s %(message)s")

    download_all_repositories("master")
    endpoints, ts_endpoints = get_all_endpoints(get_swagger_files().items())
    dependencies = []

    for repo in CODE_REPOSITORIES:
        log.info("searching repository %s for API use", repo)
        prefix_path = "repos/" + repo
        prefix_len = len(prefix_path) + 1
        for path, _, subfiles in os.walk(prefix_path):
            # exclude golang libraries from being checked
            if "/vendor/" in path or "test" in path:
                continue
            for filename in subfiles:
                filename = os.path.join(path, filename)
                path_in_repo = filename[prefix_len:]
                if FILE_WHITELIST.match(filename) and not FILE_BLACKLIST.match(filename):
                    text = open(filename, 'r').read()
                    for api in endpoints:
                        # do not look for used endpoints in the repo that defines the API
                        if repo == api:
                            continue
                        for endpoint, regex in endpoints[api].items():
                            lines = occurrences_in_string(text, regex)
                            if lines:
                                dep = Dependency(api, endpoint, regex.pattern,
                                                 repo, path_in_repo, lines)
                                dependencies.append(dep)
                                log.debug("%s uses %s endpoint %s in %s, lines %s",
                                          repo, api, endpoint, path_in_repo, lines)

                    if filename.endswith(".ts"):
                        for api, ts_eps in ts_endpoints.items():
                            for (endpoint,method), regex in ts_eps.items():
                                lines = occurrences_in_string(text, regex)
                                if lines:
                                    dep = Dependency(api, endpoint+":"+method, regex.pattern,
                                                     repo, path_in_repo, lines)
                                    dependencies.append(dep)
                                    log.debug("%s uses %s endpoint %s in %s, lines %s",
                                              repo, api, regex.pattern, path_in_repo, lines)

    # sanity check for non-existent paths
    for dep in dependencies:
        filename = os.path.join("repos", dep.target_repo, dep.target_file)
        if not os.path.isfile(filename):
            log.fatal("file %s not found", filename)
            sys.exit(-1)

    log.info("Found %d uses of API endpoints.", len(dependencies))
    write_xdot(dependencies, "dependencies.xdot")
    write_csv(dependencies, "dependencies.csv")
