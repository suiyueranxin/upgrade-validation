# Open APIs of Data Intelligence

This page contains general information and links to resources about the Open APIs of the SAP Data Intelligence (DI) product family. Furthermore, it defines minimal cross-component guidelines and requirements for DI API development.

Content:

1. [Products](#products)
1. [API Scopes](#api-scopes)
1. [API References](#api-references)
1. [OneDev Process](#onedev-process)
1. [Related Documents](#related-documents)
1. [Contact](#contact)

## Products

The following products are in the scope of the API management topics defined in this document. For more information to these products, check out the [Delivery Program](https://wiki.wdf.sap.corp/wiki/display/Odin/Delivery+Program).

| Product |
|:--------|
| [SAP Data Intelligence Cloud](https://help.sap.com/viewer/product/SAP_DATA_INTELLIGENCE/Cloud/en-US) |
| [SAP Data Intelligence](https://help.sap.com/viewer/product/SAP_DATA_INTELLIGENCE_ON-PREMISE/latest/en-US) (on-premise edition) |
| *"DI Embedded"* ([SAP Data Warehouse Cloud](https://help.sap.com/viewer/product/SAP_DATA_WAREHOUSE_CLOUD/cloud/en-US) integration) |

## API Scopes

We consider here the REST APIs of Data Intelligence components, which are usually defined in terms of [Open API](https://swagger.io/docs/specification/about/) specifications. We distinguish between three scope levels of API endpoints:

| Scope      | Usage | Specification Tag |
|:----------:|-------|-------------------|
| *default*   | Cross-component usage in [supported products](#products). | Default. No additional tag needed. |
| *private*  | Strictly used only in the owning component.               | Must include the `private` tag.    |
| *customer* | Customer-facing APIs exposed externally via API Hub.      | Must include the `customer` tag.   |

**Note:** For private APIs, you need to ensure that during execution, all parts of the owning component are running in the exact same version. For example, if a component includes a client and a server application that interact via a private API, you need to make sure that the client and server versions match at all times of their lifecycle. If this is not guaranteed, the APIs must be treated as cross-component APIs (default scope). This is required because there are no compatibility guarantees for different versions of private APIs.

## API References

The APIs are defined by means of specifications. From these specifications, human-readable references are generated as API documentation. There are currently two API references available:

| Reference | Usage | Products | Scopes |
|:---------:|:-----:|:--------:|:------:|
| [Internal API Reference](https://api.datahub.only.sap/master) | SAP-internal | All | All |
| [SAP API Business Hub](https://api.sap.com/package/SAPDataIntelligenceCloud) | SAP-external | SAP Data Intelligence Cloud | Customer APIs |
| [SAP API Business Hub](https://api.sap.com/package/SAPDataIntelligence) | SAP-external | SAP Data Intelligence (on-premise) | Customer APIs |

In addition, there is an [Internal API Diff](https://api.datahub.only.sap/diff/) website that is used to collect API differences between multiple DI versions.

## OneDev Process

The [OneDev Process](https://wiki.wdf.sap.corp/wiki/display/hanalytics/OneDevProcess+DM) of our target products requires compliance with a set of basic rules to ensure stable cross-component API usage and an aligned lifecycle management. There is no central API design across components. The component owners are responsible for designing and maintaining their APIs, and ensuring compliance with the general rules outlined below. These rules are aligned with the [global SAP guidelines and policies for API development](#related-documents).

**Note:** The requirements below apply also to API development that is not tracked by the OneDev process.

### Overview

The following requirements apply to non-private APIs:

| Requirement | Summary     |
|:-----------:|-------------|
| [Compatibility](#compatibility) | No incompatible changes to existing APIs. |
| [Versioning](#versioning)       | Consistent usage of API versioning. |
| [Deprecation](#deprecation)     | Follow process and checklist for deprecation. |
| [Decommision](#decommission)    | Removal only after deprecation and transition phase. |
| [Documentation](#documentation) | Up-to-date specifications and references.

There are no requirements for private APIs, except that their usage is restricted to their owning component.

The details of the requirements can be found below. The following badges indicate the phase of the OneDev process when the requirements should be checked:

| Badge | OneDev Phase |
|:-----:|--------------|
| ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) | Definition of Ready (Elaboration Review) |
| ![OneDev: Definition of Done](https://img.shields.io/badge/OneDev-done-green.svg)  | Definition of Done (Release Review)      |

An automated compatibility and versioning check that can be executed as push barrier in component repositories can be found [here](/tests/api).

### Compatibility

- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) No incompatible changes to non-private APIs. You can find examples of compatible and incompatible changes, as well as an automatic compatibility check [here](/tests/api). If in doubt, please reach out to us.
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) If you need to make incompatible changes, plan to create a new version of the existing API. The old version should stay unmodified and may be deprecated.
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) For changes to customer APIs, please contact us.
- During the initial development phase, incompatible changes are allowed.

### Versioning

- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) All new non-private APIs must be versioned.
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) Existing (unversioned) APIs remain as they are. They are considered as `v1`. (No incompatible changes!)
- Private APIs need not to be versioned, but it is recommended.
- Versioning is done by including `v1`, `v2` etc. in the API paths, e.g. `/api/v1/foo`. Use whole number versions only.
- Versioning may be done at different levels: components, functional groups or operations. Be consistent within your component.

### Deprecation

- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) Find users of affected APIs:
    - Check usage links in the [Internal API Reference](https://api.datahub.only.sap/master).
    - Fulltext search in GitHub for orgs: `bdh`, `velocity`, `bigdataservices`, `BigDataDevOps`, `dsp`, `orca`. Also check scripts and tests!
    - Document the list of dependencies in the [API Deprecations wiki page](https://wiki.wdf.sap.corp/wiki/display/hanalytics/API+Deprecations+DM).
    - Create Jira backlog items in the respective components for removing/updating the dependencies.
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) Plan timeline for deprecation and removal:
    - Usually 6 months deprecation for APIs in default scope.
    - 12 months deprecation for customer APIs (24 months lifetime including deprecation).
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) Clarify if there is a replacement or if the API should be decommissioned.
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) For deprecation of customer APIs, please contact us.
- ![OneDev: Definition of Done](https://img.shields.io/badge/OneDev-done-green.svg) Document non-trivial migration steps to new API versions.
- ![OneDev: Definition of Done](https://img.shields.io/badge/OneDev-done-green.svg) Announce deprecation and ask users to migrate:
    - Send announcement to [#di-apis](https://sap-data-intelligence.slack.com/archives/C019NMA3SF8) channel on Slack.
    - Send announcement to [DL VSystem Stakeholders](mailto:DL_5D4C39B3AE559C02973C1D0B@global.corp.sap) (for VSystem and related components).
    - Contact affected users directly and make them aware that they need to take action.
- ![OneDev: Definition of Done](https://img.shields.io/badge/OneDev-done-green.svg) Add deprecation metadata to API specification:
    - Add `deprecated: true` to the deprecated entity (e.g. an operation).
    - Add `x-removal-version: ...` to the deprecated entity to indicate the version when the removal is planned. This refers to the major version number of the owning component, e.g. `'2010'`. Format it as a string by adding quotes.
    - Add a short deprecation note to the `description` field of the deprecated entity.
    - If the entire specification gets deprecated, add it to all operations.

Here an example of a deprecated operation:

```yaml
paths:
  /api/v1/data:
    get:
      summary: Get the data
      description: Get the data from all customers and clients. This endpoint is deprecated
        and will be removed in version 2010 of this component. Please use /api/v2/data instead.
      deprecated: true
      x-removal-version: '2010'
```

### Decommission (Removal)

- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) Removal of non-private APIs is allowed only after a deprecation and transition phase.
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) For decommission of customer APIs, please contact us.
- ![OneDev: Definition of Done](https://img.shields.io/badge/OneDev-done-green.svg) All consuming components, scripts, tests must have removed the dependency. This is tracked on the following wiki page: [API Deprecations DM](https://wiki.wdf.sap.corp/wiki/display/hanalytics/API+Deprecations+DM).

### Documentation

- ![OneDev: Definition of Done](https://img.shields.io/badge/OneDev-done-green.svg) Keep your specifications up to date and ensure they reflect your implementation.
- ![OneDev: Definition of Done](https://img.shields.io/badge/OneDev-done-green.svg) To add new specifications, please contact us to include it in the internal API reference.
- ![OneDev: Definition of Ready](https://img.shields.io/badge/OneDev-ready-blue.svg) To publish customer APIs, please contact us to prepare the publication on the API Hub.
- The internal reference is updated automatically. The API Hub reference requires a manual publication process.

## Related Documents

- [CTO Circle - REST API Harmonization Direction v1.0](https://jam4.sapjam.com/groups/7G2t6P7Kezwk4wGn4eQE5r/documents/u7hbLkqcK5s6JnToT9PftP/slide_viewer)
- [CTO Circle – API Deprecation](https://jam4.sapjam.com/groups/jnA6Yg2dO6LPpPulNx8hFL/documents/qInKPF2j59YhVa7HFbKrWL/slide_viewer)
- [Product Standard SLC-34 - Deprecation of Services](https://wiki.wdf.sap.corp/wiki/display/pssl/SLC-34)
- [Product Standard INTG-021 - Aligned Business APIs](https://wiki.wdf.sap.corp/wiki/display/PSITG/INTG-021)
- [Technology Guideline TG03 - Aligned Business APIs](https://github.tools.sap/CentralEngineering/TechnologyGuidelines/tree/latest/tg03)

## Contact

For questions regarding these requirements, please contact the [DL Data Intelligence API Management](mailto:DL_5ED8CCF14687A4027D3F8D0F@global.corp.sap).

For updates on API requirements and tooling, you can subscribe to the [DL Data Intelligence API Providers](mailto:DL_5E8DC07F278FC7027E4FE6D3@global.corp.sap).
