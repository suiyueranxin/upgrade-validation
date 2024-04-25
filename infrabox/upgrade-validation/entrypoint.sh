#!/bin/bash

echo "## Preflight checks"

# make sure the git repo exists
if [ -z "$GIT_ROOT" ]; then
  GIT_ROOT=/infrabox/context
fi
if [ ! -d "${GIT_ROOT}/.git" ]; then
  echo "Error: no git repository found at ${GIT_ROOT}"
  exit 1
fi

# get pull request commit
pushd $GIT_ROOT > /dev/null
PULL_REQUEST_COMMIT=$(git rev-parse HEAD)
popd > /dev/null

# check repository name
if [ -z "${GITHUB_REPOSITORY_FULL_NAME}" ]; then
  echo "Warning: GITHUB_REPOSITORY_FULL_NAME not set, determining from $GIT_ROOT"
  pushd $GIT_ROOT > /dev/null
  git_url=$(git remote -v | grep origin | grep fetch | sed -n 's/[^:]*:\(.*\)\.git (fetch)/\1/p')
  git_repo=$(basename $git_url)
  git_org=$(basename $(dirname $git_url))
  export GITHUB_REPOSITORY_FULL_NAME="${git_org}/${git_repo}"
  popd > /dev/null
  if [ -z "${GITHUB_REPOSITORY_FULL_NAME}" ]; then
    echo "Error: cannot determine GITHUB_REPOSITORY_FULL_NAME from $GIT_ROOT"
    exit 1
  fi
  echo "Setting GITHUB_REPOSITORY_FULL_NAME=${GITHUB_REPOSITORY_FULL_NAME}"
fi

# if repo is bdh/upgrade-validation, check master branch of all registered components
if [ "${GITHUB_REPOSITORY_FULL_NAME}" = "bdh/upgrade-validation" ]; then
  if [ -z "$UPGRADE_VALIDATION_TARGET_VERSION" ]; then
    # determine upgrade-validation branch
    PULL_REQUEST_COMMIT=$(basename $INFRABOX_GIT_BRANCH) # should be "stable" or "master"
    if [ "$GITHUB_PULL_REQUEST_BASE_REF" = "stable" ]; then
      PULL_REQUEST_COMMIT="stable"
    else
      PULL_REQUEST_COMMIT="master"
    fi
  fi
fi

# check target commit/branch
if [ -z "${PULL_REQUEST_COMMIT}" ]; then
  echo "PULL_REQUEST_COMMIT not set!"
  exit 1
fi

# create folder for test results
if [ -z "$TEST_RESULTS" ]; then
  TEST_RESULTS=/infrabox/upload/testresult
fi
mkdir -p $TEST_RESULTS

# set test arguments
api_args=""
operator_args=""
if [ "${GITHUB_REPOSITORY_FULL_NAME}" != "bdh/upgrade-validation" ]; then
  api_args="${api_args} --repo=${GITHUB_REPOSITORY_FULL_NAME}"
  operator_args="${operator_args} --solution=${GITHUB_REPOSITORY_FULL_NAME}"
fi
if [ -n "${UPGRADE_VALIDATION_BASE_VERSION}" ]; then
  api_args="${api_args} --base=${UPGRADE_VALIDATION_BASE_VERSION}"
  operator_args="${operator_args} --old-version=${UPGRADE_VALIDATION_BASE_VERSION}"
fi
if [ -n "${UPGRADE_VALIDATION_TARGET_VERSION}" ]; then
  api_args="${api_args} --target=${UPGRADE_VALIDATION_TARGET_VERSION}"
  operator_args="${operator_args} --new-version=${UPGRADE_VALIDATION_TARGET_VERSION}"
else
  api_args="${api_args} --target=${PULL_REQUEST_COMMIT}"
  operator_args="${operator_args} --new-version=${PULL_REQUEST_COMMIT}"
fi
if [ "$UPGRADE_VALIDATION_CHECK_ALL" = "true" ]; then
  api_args="${api_args} -a"
fi
if [ "$UPGRADE_VALIDATION_CHECK_PRIVATE_APIS" = "true" ]; then
  api_args="${api_args} -p"
fi

EXIT_CODE=0

# run api tests
echo "## Run API compatibility checks"
pushd /tests/api
python3 swagger_test.py ${api_args} -x ${TEST_RESULTS}/api-test.xml -c ${TEST_RESULTS}/api-diff.csv
if [ $? -ne 0 ]; then
  echo "## Error: API compatibility check failed!"
  EXIT_CODE=1
fi
popd

# run operator checks
echo "## Run operator checks"
pushd /tests/vflow
python3 main.py ${operator_args} -x ${TEST_RESULTS}/operators-test.xml
if [ $? -ne 0 ]; then
  echo "## Error: operator check failed!"
  EXIT_CODE=1
fi
popd

exit $EXIT_CODE
