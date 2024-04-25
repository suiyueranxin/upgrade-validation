# API Tools

## add\_usage.py

```
usage: add_usage.py [-h] repo spec deps

Add usage documentation to OpenAPI/Swagger specifications

positional arguments:
  repo        Repository containing specification
  spec        OpenAPI/Swagger specification file
  deps        CSV files with dependencies

optional arguments:
  -h, --help  show this help message and exit
```

## extract\_apis.py

```
usage: extract_apis.py [-h] [-t [TAGS]] [-o [FORMAT]] spec

Extract API endpoints from an OpenAPI/Swagger specification

positional arguments:
  spec         OpenAPI/Swagger specification file

optional arguments:
  -h, --help   show this help message and exit
  -t [TAGS]    comma-separated list of tags to match (use 'deprecated' to
               extract deprecated paths)
  -o [FORMAT]  output format (yaml, csv)
```


## generate\_api\_docs.py

```
INFO    Generate API documentation for SAP Data Intelligence Services
INFO    usage: generate_api_docs.py <branch> <outdir>
```

## merge\_specs.py

```
usage: merge_specs.py [-h] [-g [groups]] base ext

Merge two OpenAPI/Swagger specifications

positional arguments:
  base         base file to be used for merging
  ext          extension file

optional arguments:
  -h, --help   show this help message and exit
  -g [groups]  specification groups (comma-separated)
```
