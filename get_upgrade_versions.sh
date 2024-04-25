#!/bin/bash
set -eo pipefail

COMPONENT=""
BRANCH=""

while [[ $# -ge 1 ]]
do
key="$1"
case ${key} in
  --component=*)
  ARG="${key#*=}"
  if [ ! -z "$ARG" ]; then
    COMPONENT="$ARG"
  fi
  ;;
  --branch=*)
  ARG="${key#*=}"
  if [ ! -z "$ARG" ]; then
    BRANCH="$ARG"
  fi
  ;;
  --base-version=*)
  ARG="${key#*=}"
  if [ ! -z "$ARG" ]; then
    BASE_RELEASEPACK_VERSIONS="$ARG"
  fi
  ;;
esac
shift
done

get_dep_version() {
  DEP=$1
  URL=$2
  DEP_NAME="hldep.${DEP}.version"
  echo $(curl -sk ${URL} | grep ${DEP_NAME} | sed -n 's/^.*<'"${DEP_NAME}"'>\([0-9]\+.[0-9]\+.[0-9]\+\).*/rel\/\1/mp')
}

echoerr() { 
  printf "%s\n" "$*" >&2; 
}

get_vsolution_version() {
  echoerr "Retrieving ${2} version from ${1}"
  VSOLUTION_VERSION=$(get_dep_version "${2}" "${1}")
  echoerr "${2} version: ${VSOLUTION_VERSION}"
  echoerr "Retrieving ${4} version from ${3}"
  VSOLUTION_DEP_URL="https://github.wdf.sap.corp/raw/${3}/${VSOLUTION_VERSION}/deps/${4}.dep"
  BARE_VERSION=$(curl -sk $VSOLUTION_DEP_URL | jq -r '.VERSION')
  VERSION="rel/${BARE_VERSION}"
  echo $VERSION
}

if [ -z "$COMPONENT" ]; then
  echoerr "#### [level=error] COMPONENT variable is not set, e.g. --component=VFLOW. Supported options are VFLOW, RELEASEPACK, APP_BASE, APP_DATA, HANALITE, VSYSTEM, STORAGEGATEWAY, FLOWAGENT, DIAGNOSTICS, CODE_SERVER, AXINO, ML_API, ML_DM_API, ML_TRACKING, DQ_INTEGRATION"
  exit 1
fi

if [[ -z "$BRANCH" && -z "$BASE_RELEASEPACK_VERSIONS" ]]; then
  echoerr "### [level=error] --branch or --base-version must be set"
  exit 1
fi

if [ -z "$BASE_RELEASEPACK_VERSIONS" ]; then
  echoerr "Determining releasepack base versions"
  RELEASEPACK_JSON=""
  if [[ -n "${GITHUB_REPOSITORY_FULL_NAME}" && "${GITHUB_REPOSITORY_FULL_NAME}" == "bdh/upgrade-validation" ]]; then
    version_file="/infrabox/context/deps/upgrade_multi_base_version.json"
    if [ -f $version_file ]; then
      echoerr "Base version request comes from upgrade-validation repo."
      echoerr "Local file ${version_file} will be used."
      RELEASEPACK_JSON=$(cat ${version_file})
    else
      echoerr "Local file is not found. The script will try to request the file remotely."
    fi
  fi
  if [ "${RELEASEPACK_JSON:-0}" == 0 ]; then
    UPGRADE_REPO_URL="https://github.wdf.sap.corp/raw/bdh/upgrade-validation/${BRANCH}/deps/upgrade_multi_base_version.json"
    RELEASEPACK_JSON=$(curl -sk $UPGRADE_REPO_URL)
    # check whether the response starts as json
    if [[ ${RELEASEPACK_JSON:0:1} != "{" ]]; then
      echoerr "The curl request to ${UPGRADE_REPO_URL} has failed: ${RELEASEPACK_JSON}."
      echoerr "Please check whether ${BRANCH} branch exists."
      exit 2
    fi
  fi
  BASE_RELEASEPACK_VERSIONS=$(echo $RELEASEPACK_JSON | jq -r .BASE_BDH_VERSION[].version)
  echoerr "Using releasepack base versions ${BASE_RELEASEPACK_VERSIONS}"
fi

declare -a VERSION_ARRAY=()

for BASE_RELEASEPACK_VERSION in $BASE_RELEASEPACK_VERSIONS; do
  echoerr "Checking releasepack base version $BASE_RELEASEPACK_VERSION"
  if [[ "$BASE_RELEASEPACK_VERSION" = *-ms ]]; then
    POM_URL="https://int.repositories.cloud.sap/artifactory/build-milestones-xmake/com/sap/datahub/SAPDataHub/${BASE_RELEASEPACK_VERSION}/SAPDataHub-${BASE_RELEASEPACK_VERSION}.pom"
  else
    POM_URL="https://int.repositories.cloud.sap/artifactory/build-releases/com/sap/datahub/SAPDataHub/${BASE_RELEASEPACK_VERSION}/SAPDataHub-${BASE_RELEASEPACK_VERSION}.pom"
  fi
  if [ "$COMPONENT" = "RELEASEPACK" ]; then
    VERSION=$BASE_RELEASEPACK_VERSION
  elif [ "$COMPONENT" = "VFLOW" ]; then
  	VERSION=$(get_vsolution_version ${POM_URL} hl-vsolution velocity/vsolution vflow)
  elif [ "$COMPONENT" = "VFLOW_SUB_ABAP" ]; then
  	VERSION=$(get_vsolution_version ${POM_URL} hl-vsolution velocity/vsolution vflow-sub-abap)
  elif [ "$COMPONENT" = "AXINO" ]; then
  	VERSION=$(get_vsolution_version ${POM_URL} hl-vsolution velocity/vsolution axino)
  elif [ "$COMPONENT" = "ML_API" ]; then
  	VERSION=$(get_vsolution_version ${POM_URL} dsp-release dsp/dsp-release ml-api)
  elif [ "$COMPONENT" = "ML_DM_API" ]; then
  	VERSION=$(get_vsolution_version ${POM_URL} dsp-release dsp/dsp-release ml-dm-api)
  elif [ "$COMPONENT" = "ML_TRACKING" ]; then
  	VERSION=$(get_vsolution_version ${POM_URL} dsp-release dsp/dsp-release ml-tracking)
  elif [ "$COMPONENT" = "DSP_GITSERVER" ]; then
  	VERSION=$(get_vsolution_version ${POM_URL} dsp-release dsp/dsp-release dsp-git-server)
  elif [ "$COMPONENT" = "APP_BASE" ]; then
    echoerr "Retrieving datahub-app-base version from ${POM_URL}"
    VERSION=$(get_dep_version "datahub-app-base" $POM_URL)
  elif [ "$COMPONENT" = "APP_DATA" ]; then
    major_version=${BASE_RELEASEPACK_VERSION%.*.*}
    if [[ "$major_version" = 2 || ( "$major_version" -gt 1900 && "$major_version" -lt 2003 ) ]]; then
      echoerr "## The datahub-app-data version is not available in ${POM_URL}. Please request version of the APP_BASE"
    else
      echoerr "Retrieving datahub-app-data version from ${POM_URL}"
      VERSION=$(get_dep_version "datahub-app-data" $POM_URL)
    fi
  elif [ "$COMPONENT" = "HANALITE" ]; then
    echoerr "Retrieving hl-lib version from ${POM_URL}"
    VERSION=$(get_dep_version "hl-lib" $POM_URL)
  elif [ "$COMPONENT" = "VSYSTEM" ]; then
    echoerr "Retrieving hl-vsystem version from ${POM_URL}"
    VERSION=$(get_dep_version "hl-vsystem" $POM_URL)
  elif [ "$COMPONENT" = "STORAGEGATEWAY" ]; then
    echoerr "Retrieving storagegateway version from ${POM_URL}"
    VERSION=$(get_dep_version "storagegateway" $POM_URL)
  elif [ "$COMPONENT" = "FLOWAGENT" ]; then
    echoerr "Retrieving datahub-flowagent version from ${POM_URL}"
    VERSION=$(get_dep_version "datahub-flowagent" $POM_URL)
  elif [ "$COMPONENT" = "DQ_INTEGRATION" ]; then
    echoerr "Retrieving datahub-flowagent version from ${POM_URL}"
    flowagent_version=$(get_dep_version "datahub-flowagent" $POM_URL)
    flowagent_pom_url="https://github.wdf.sap.corp/raw/bdh/datahub-flowagent/${flowagent_version}/build/parent/pom.xml"
    echoerr "Retrieving datahub-dq-integration version from ${flowagent_pom_url}"
    VERSION=$(get_dep_version "datahub-dq-integration" $flowagent_pom_url)
  elif [ "$COMPONENT" = "DIAGNOSTICS" ]; then
    echoerr "Retrieving diagnostics version from ${POM_URL}"
    VERSION=$(get_dep_version "diagnostics" $POM_URL)
  elif [ "$COMPONENT" = "CODE_SERVER" ]; then
    echoerr "Retrieving code server version from ${POM_URL}"
    VERSION=$(get_dep_version "code-server" $POM_URL)
  else
    echo "### [level=error] Unsupported component name: ${COMPONENT}"
    exit 3
  fi
  VERSION_ARRAY+=($VERSION)
done

if [ ${#VERSION_ARRAY[@]} -ne 0 ]; then
  # print only unique values
  printf "%q\n" "${VERSION_ARRAY[@]}" | sort -u
else
  echoerr "## No versions found!"
fi
