#!/bin/bash
set -ex

# TODO: source CODELINE, GIT_COMMIT_ID and VERSION_TAG from previous milestone validation creation job

git clone git@github.wdf.sap.corp:bdh/milestone-validation.git
pushd milestone-validation
  git checkout ${CODELINE}
  if [[ -n "${GIT_COMMIT_ID}" ]]; then
    git checkout -qf ${GIT_COMMIT_ID}
  fi
  git config user.name VELOBOT
  git config user.email DL_57B30BA95F99B7A3560000F5@exchange.sap.corp
  git tag -a ${VERSION_TAG} -m "create tag ${VERSION_TAG} by velobot"
  git push origin ${VERSION_TAG}
popd
