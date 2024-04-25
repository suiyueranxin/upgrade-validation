# VFlow operator API compatibility tests

The script in this folder checks the compatibility of operator APIs between different versions.

## Running the script

```
usage: main.py [-h] [--solution SOLUTION] [--old-version OLD_VERSION]
               [--new-version NEW_VERSION] [--log-level LOG_LEVEL]
               [--Wdeprecation] [--verbose] [-x [XML]]

Options:
  -h, --help            show this help message and exit
  --solution SOLUTION   Solution to test. Available solutions are defined in
                        solutions.json
  --old-version=OLD_VERSION
                        Version to upgrade from. Either a milestone version
                        number or a git refspec.
  --new-version=NEW_VERSION
                        Version to upgrade to. Either a milestone version
                        number or a git refspec.
  --log-level=LOG_LEVEL
                        Level of logging. One of ERROR, WARNING, INFO, or
                        DEBUG
  --Wdeprecation        Warn of missing fields for deprecated operators
  --verbose             Verbose output for property changes
  -x [XML]              path for xml test report
```

Calling the script without parameters, i.e. `python3 main.py`, compares the oldest upgradable version with the newest milestone on Artifactory.

The script performs the following checks on operators. Note that some rules do not apply to operators marked as _deprecated_ or _beta_ in the old version.
- Deprecation:
  Checks if an operator marked as deprecated fulfils all the criteria given in [the documentation](https://github.wdf.sap.corp/velocity/vflow/blob/master/src/repo/deprecation/README.md).
- Removal of operators:
  Checks if an operator was removed. Only operators marked as _deprecated_ or _beta_ may be removed.
- Removal/change of I/O ports:
  Checks if, for a (non-_beta_) operator, I/O ports were changed or removed.
  *Caveat*: Currently, this includes only the ports specified in the `operator.json` or `lineage.json` files. Ports which are defined in the operator's Golang code are not checked.
- Removal/change of properties
  Checks if properties of a (non-_beta_) operator were changed.

The addition of operators, I/O ports or properties is considered harmless.

## Dealing with false positives

For false positives, a file `fixed.json` is provided that allows one to specify exceptions to the rules enforced by the scrip.

The `fixed.json` file consists of a single root element named "fixes", containing an array of fixes.
The fixes in this array look as follows:

```json
    {
        "kind": one of the CHANGE_TYPES listed below,
        "operator": the name of the operator, e.g. "com.sap.vora.voraLoader",
        "key": the key belonging to the change, i.e. the name of the ioport/property,
        "subkey": the subkey of the change; only valid for 'kind==pkey-chg',
        "version": version where this API change was introduced,
        "reason": the reason why this does not constitute a proper API change
    }
```

Of all these fields, the "reason" field is the most important.

## Contact

For issues or requests regarding this test, please contact the [DL Data Intelligence API Management](mailto:DL_5ED8CCF14687A4027D3F8D0F@global.corp.sap).
