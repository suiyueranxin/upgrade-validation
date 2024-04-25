#!/bin/bash
set -eo pipefail

pushd /infrabox/context

echo "## Checkout vsystem repo"

# run test
git config --global http.sslVerify "false"
git clone https://github.wdf.sap.corp/velocity/vsystem.git
pushd vsystem

cp -rv /infrabox/context/vsystem/helm /infrabox/context/
/infrabox/context/vsystem/infrabox/helm-upgrades/entrypoint.sh