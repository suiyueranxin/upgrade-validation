# Swagger/OpenAPI Compatibility and Versioning Test

This folder contains tests for preventing incompatible API changes and enforcing versioning constraints for services in SAP Data Intelligence. It currently supports checks for APIs defined using Swagger/OpenAPI only. The tests are performed by fetching a base and a target version of the API specifications from the corporate GitHub and doing a semantical comparison of the two versions. Base versions are maintained centrally in [upgrade_multi_base_version.json](../../deps/upgrade_multi_base_version.json).

The repositories and specification files to be tested are defined in [swagger_specs.json](swagger_specs.json). A list of Swagger/OpenAPI files for the main components can be generated using the [find_specs.py](find_specs.py) script. However, not all specifications are included because some of them are private or describe the API of another service. Currently the following repositories are included:

| Tested Repositories                                                                          |
|----------------------------------------------------------------------------------------------|
| [bdh/datahub-app-base](https://github.wdf.sap.corp/bdh/datahub-app-base)                     |
| [bdh/datahub-app-data](https://github.wdf.sap.corp/bdh/datahub-app-data)                     |
| [bdh/datahub-flowagent](https://github.wdf.sap.corp/bdh/datahub-flowagent)                   |
| [bigdataservices/storagegateway](https://github.wdf.sap.corp/bigdataservices/storagegateway) |
| [velocity/axino](https://github.wdf.sap.corp/velocity/axino)                                 |
| [velocity/vflow](https://github.wdf.sap.corp/velocity/vflow)                                 |
| [velocity/vsystem](https://github.wdf.sap.corp/velocity/vsystem)                             |

## Running the Test

The test is located at [swagger_test.py](swagger_test.py) and is implemented in Python 3. The command-line arguments are as follows:

```
usage: swagger_test.py [-h] [--repo [repo]] [--base [base]] [--target [target]] [-a] [-p] [-l [level]] [-x [xml]] [-c [csv]]

Swagger/OpenAPI compatibility tests for SAP Data Intelligence.

optional arguments:
  -h, --help         show this help message and exit
  --repo [repo]      repository name of the DI component, e.g. 'velocity/vsystem'. If not set, test all registered repositories.
  --base [base]      base version of the DI component or releasepack, e.g. '2006.1.8'. If --repo is set, it refers to the component version, otherwise to the releasepack version.
  --target [target]  target version or branch of the DI component or releasepack, e.g. 'master'. If --repo is set, it refers to the component version, otherwise to the releasepack version.
  -a                 force testing of all specifications
  -p                 force testing of private endpoints
  -l [level]         log level, e.g. 'debug'
  -x [xml]           path for xml test report
  -c [csv]           path for csv change report
```

For example, to run compatibility checks for VSystem comparing version 2002.1.10 with the current head of the master branch, you would execute the following command:

```bash
python3 swagger_test.py velocity/vsystem 2002.1.10 master
```

You can also use commit IDs, other branches or version numbers as target.

## Test Automation

The API compatibility check can be executed as part pull request checks of components. The test detects automatically which component it is executed for. To include it, the repository has to be registered in the test configuration (please contact us) and the test needs to be registered in the component's infrabox definition:

```json
{
  "name": "check-api-compatibility",
  "type": "docker-image",
  "image": "docker.wdf.sap.corp:51055/com.sap.datahub.linuxx86_64/upgrade-validation:2010.0.2",
  "environment": {
    "UPGRADE_VALIDATION_GITHUB_TOKEN": {
      "$secret": "UPGRADE_VALIDATION_GITHUB_TOKEN"
    }
  },
  "resources": {
    "limits": {
      "memory": 1024,
      "cpu": 1
    }
  }
}
```

See the [VERSION](../../cfg/VERSION) file for the latest version of the docker image.

## Checked Constraints

The main part of the test consists of checking whether entries in the base version of the API have been removed, renamed or changed in an incompatibly way. In addition, it checks whether new APIs are versioned. This applies to `paths`, their methods, parameter and responses. Analogously, `definitions` and `components` and their properties are checked. Types are not allowed to be changed. New parameters can be added if they are optional. New paths can be added if they are versioned. Paths can be removed only if they have been deprecated first. The deprecation period is at least 2 on-premise release cycles. Deprecation is done by setting `depecated: true`.

Consider the following example of a specification:

```yaml
swagger: '2.0'
paths:
  /api/v1/foo/:
    get:
      parameters:
        - name: id
          in: query
          type: string
      responses:
        '200':
          schema:
            $ref: '#/definitions/Foo'
    put:
      deprecated: true
      parameters:
        - name: id
          in: query
          type: string
      responses:
        '200':
          description: OK
```

The following changes w.r.t. a base version of the API are **not** allowed:

* removing or renaming the `/api/v1/foo/` path
* removing the GET operation of `/api/v1/foo/`
* removing or renaming the `id` parameter
* changing the `type` of the `id` parameter
* changing the response schema, e.g., from `#/definitions/Foo` to `#/definitions/Bar`
* adding a new required parameter
* adding a new unversioned path, e.g., `/api/bar`

However, the following changes **are** allowed:

* adding a new versioned path `/api/v2/foo/` (and tagging `/api/v1/foo/` as deprecated)
* adding optional parameters or responses to an operation
* removing the PUT operation of `/api/v1/foo/` (because it is already tagged as deprecated)

In case of false positives or already existing breaking changes, a list of exceptions is maintained in [swagger_specs.json](swagger_specs.json). The compatibility checks are ommitted for private APIs.

## Contact

For issues or requests regarding this test, please contact the [DL Data Intelligence API Management](mailto:DL_5ED8CCF14687A4027D3F8D0F@global.corp.sap).
