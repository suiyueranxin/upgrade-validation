#!/usr/bin/env python

import sys
import os
import json
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import logging
os.environ["GIT_PYTHON_REFRESH"] = "quiet"
from git import Repo

#pylint: disable=dangerous-default-value
def requests_retry_session(
        retries=3,
        backoff_factor=1,
        status_forcelist=list(range(500, 600)),
        session=None,
):

    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    request_retry = HTTPAdapter(max_retries=retry)
    session.mount('http://', request_retry)
    session.mount('https://', request_retry)
    return session

def registration(logger, url, bubbleup_url, vtype, ptype, my_url):
    proxies = {
        "http": None,
        "https": None,
    }
    if not url:
        url = 'https://ci-dashboard.datahub.only.sap/api/pipelines/releasepack/job'

    task_name = vtype + '_' + ptype

    body = {
        "build_link": bubbleup_url,
        "job_data": {
            "name": task_name,
            "link": my_url
        }
    }
    try:
        logger.info(
            'Start to do pipeline registration with url ' + bubbleup_url + ' with info ' + str(body))
        resp = requests_retry_session().put(url,
                                             json=body,
                                             verify=False,
                                             proxies=proxies,
                                             timeout=300)
        if resp.status_code == 200:
            logger.info('Successfully registration to ci dashboard with resp info ' + str(resp.text))
        else:
            logger.error('Failed to registration to ci dashboard with resp error ' + str(resp.text))
    except Exception as ex:
        logger.error('Failed to registration to ci dashboard with exception ' + str(ex))


def get_burl(logger, cmsgs):
    for line in cmsgs.split('\n'):
        if line.strip().startswith('Jenkins build url:'):
            logger.info('Found Jenkins build url: ' + str(line))
            return line.split('Jenkins build url:')[1].strip()
    return False

def main():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logger = logging.getLogger("Registration_for_upgrade_validation")
    repo_path = os.environ.get("GIT_ROOT", "/infrabox/context/.git")
    git_repo = Repo(repo_path)
    commits = git_repo.head.commit.message
    logger.info('Latest commit message is: ' + str(commits))
    bubbleup_url = get_burl(logger, commits)
    if os.environ.get("CI_DASHBOARD_URL") and os.environ.get("DEPLOY_TYPE") and bubbleup_url and os.environ.get("INFRABOX_BUILD_URL") and os.environ.get("VALIDATION_TYPE"):
        registration(logger, os.environ.get("CI_DASHBOARD_URL"), bubbleup_url, os.environ.get("VALIDATION_TYPE"), os.environ.get(
            "DEPLOY_TYPE"), os.environ.get("INFRABOX_BUILD_URL", False))
    else:
        logger.info('Not qualified for registration to ci dashboard...')


if __name__ == "__main__":
    main()


