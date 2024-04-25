#!/bin/bash

set -exo pipefail

echo "Checking branch..."

if [[ -n "${GITHUB_PULL_REQUEST_BASE_REF}" ]]; then
    target_branch=$GITHUB_PULL_REQUEST_BASE_REF
elif [[ -n "${INFRABOX_GIT_BRANCH}" ]]; then
    target_branch=$INFRABOX_GIT_BRANCH
else
    target_branch="main"
fi

if ! [[ "${target_branch}" == "rel-"* || "${target_branch}" == "stable" ]]; then
    target_branch="main"  
fi

function check_infra_branch {
  curl -u di-upgrade-validation-bot:$UPGRADE_VALIDATION_GITHUB_TOKEN -s -k -o /dev/null -w "%{http_code}" https://github.wdf.sap.corp/api/v3/repos/bdh/bdh-infra-tools/branches/$1
}

skip_on_cloud="false"
skip_on_premise="false"
checkout_branch=$target_branch
if [[ "${target_branch}" == "rel-"* ]]; then
    branch_prefix=$(echo $target_branch |cut -d '-' -f2 |cut -d '.' -f1)
    if [ $branch_prefix -gt 2005 ]; then
      skip_on_premise="true"
    fi
    main_exists=$(check_infra_branch main)
    target_exists=$(check_infra_branch ${target_branch})
    if [ "${main_exists}" -ne 200 ]; then
        echo "Error getting bdh-infra-tools branch info from GitHub"
        exit 1
    fi
    if [ "${target_exists}" -ne 200 ]; then
        checkout_branch="main"
    fi
fi
echo "The ${target_branch} branch was chosen as target."

if [[ "${target_branch}" == "rel-3."* ]]; then
    echo "Skip on cloud validation for ${target_branch}"
    skip_on_cloud="true"
fi
if [[ "${target_branch}" == "rel-dhaas" ]]; then
    echo "Skip on premise validation for ${target_branch}"
    skip_on_premise="true"
fi

target_version=$(cat /infrabox/context/deps/hanalite-releasepack.dep | jq -r '.VERSION')
echo "The target version is ${target_version}."

base_versions=$(cat /infrabox/context/deps/upgrade_multi_base_version.json | jq -r .BASE_BDH_VERSION[].version)
deploy_types=$(cat /infrabox/context/deps/upgrade_multi_base_version.json | jq -r .BASE_BDH_VERSION[].\"di-validation\")

infrabox_output="/infrabox/output/infrabox.json"
echo "{\"version\": 1, \"jobs\": [" > $infrabox_output
versionsarray=($base_versions)
version_length=${#versionsarray[@]}
deploy_types_array=($deploy_types)

for (( index = 0; index < ${version_length}; index++ )) 
do
    echo "## Generate upgrade jobs for the base version ${versionsarray[${index}]}."
    infraboxjson=$(cat /infrabox/context/infrabox/e2e-upgrade-validation/infrabox.json)
    mod_base_version=${versionsarray[${index}]//./-}
    mod_target_version=${target_version//./-}
    deploy_type="on_premise"
    if [[ "${deploy_types_array[${index}]}" == "yes" ]]; then
        deploy_type="on_cloud"
    fi
    if [[ "${deploy_type}" == "on_cloud" ]] && [[ "${skip_on_cloud}" == "true" ]]; then
        continue
    fi
    if [[ "${deploy_type}" == "on_premise" ]] && [[ "${skip_on_premise}" == "true" ]]; then
        continue
    fi
    if [[ $target_branch == 'main' ]]; then
        release_branch='master'
    else
        release_branch=$target_branch     
    fi 
    infraboxjson=${infraboxjson//BASE_NAME_TO_REPLACE/$mod_base_version}
    infraboxjson=${infraboxjson//TARGET_NAME_TO_REPLACE/$mod_target_version}
    infraboxjson=${infraboxjson//BASE_VERSION_TO_REPLACE/${versionsarray[${index}]}}
    infraboxjson=${infraboxjson//TARGET_VERSION_TO_REPLACE/$target_version}
    infraboxjson=${infraboxjson//RELEASEPACK_BRANCH_TO_REPLACE/$release_branch}
    infraboxjson=${infraboxjson//DEPLOY_TYPE_TO_REPLACE/$deploy_type}
    infraboxjson=${infraboxjson//CHECKOUT_BRANCH_TO_REPLACE/$checkout_branch}
    echo $infraboxjson >> $infrabox_output
    echo "," >> $infrabox_output
    echo "## Generate ci dashboard registration jobs for $deploy_type."
    infraboxjson_ci_dashboard=$(cat /infrabox/context/infrabox/ci_dashboard_registration/infrabox.json)
    infraboxjson_ci_dashboard=${infraboxjson_ci_dashboard//BASE_NAME_TO_REPLACE/$mod_base_version}
    infraboxjson_ci_dashboard=${infraboxjson_ci_dashboard//TARGET_NAME_TO_REPLACE/$mod_target_version}
    infraboxjson_ci_dashboard=${infraboxjson_ci_dashboard//DEPLOY_TYPE_TO_REPLACE/$deploy_type}
    echo $infraboxjson_ci_dashboard >> $infrabox_output
    echo "Current base version iteration is $[$index+1] out of $version_length"
    if [[ $[$index+1] -ne $version_length ]]; then
        echo "," >> $infrabox_output
    fi
done
echo "]}" >> $infrabox_output

echo "## The following file was generated:"
cat $infrabox_output

cp $infrabox_output /infrabox/upload/archive/infrabox.json
