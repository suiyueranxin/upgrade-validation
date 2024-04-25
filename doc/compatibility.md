# Upgrade Compatibility for SAP Data Intelligence

This page summarizes **compatibility, deprecation and versioning requirements** for SAP Data Intelligence, including:

1. [Pipeline Operators and Docker Images](#pipeline-operators-and-docker-images)
1. [VSystem Client](#vsystem-client)
1. [Open API](#open-api)

## Pipeline Operators and Docker Images

The operator deprecation process is described [here](https://github.wdf.sap.corp/velocity/vflow/blob/master/src/repo/deprecation/README.md).

Operator compatibility tests can be found here: [tests/vflow](/tests/vflow). They run in the push validation of the vflow repository. Limitation: operators in other repositories are currently not tested.

The new operator versioning concept is internally documented [here](https://github.wdf.sap.corp/velocity/vflow/blob/master/doc/internal/operator_versioning.md).

The deprecation period for operators is one on-premise release cycle.

Operator deprecations are highlighted in the pipeline modeler. In the customer-facing documentation, they are moved to the
[Deprecated Operators](https://help.sap.com/viewer/97fce0b6d93e490fadec7e7021e9016e/Cloud/en-US/dd8043ab671842a9852914c97630748f.html) section.

## VSystem Client

The compatibility requirements for the `vctl` command-line tool are documented [here](https://github.wdf.sap.corp/velocity/vsystem/blob/master/doc/contributing/guidelines/vctl-style-guide.md#compatibility-requirements).

## Open API

The compatibility requirements for REST APIs are defined [here](open-api.md).
