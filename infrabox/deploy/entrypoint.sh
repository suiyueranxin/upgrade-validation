#!/bin/bash

set -eo pipefail

set +e
tag=$(curl --insecure --retry 20 -u $DOCKER_WDF_REGISTRY_USERNAME:$DOCKER_WDF_REGISTRY_PASSWORD \
"https://${DOCKER_WDF_REGISTRY}/v2/${DOCKER_WDF_REPOSITORY}/manifests/${CURRENT_VERSION}" \
| jq -r '.tag')
set -e

if [[ -n "${tag}" && "${tag}" == "${CURRENT_VERSION}" ]]; then
  echo "## The image with version ${CURRENT_VERSION} already exists. No need to generate a new image."
else
  echo "## The image with version ${CURRENT_VERSION} does not exist. \
  The image will be built and deployed in the following infrabox job \
  with the name build-and-deploy-upgrade-validation-image."
  infraboxjson=$(cat /infrabox/context/infrabox/deploy/infrabox.json)
  echo ${infraboxjson/VERSION_TO_REPLACE/$CURRENT_VERSION} > /infrabox/output/infrabox.json
fi
