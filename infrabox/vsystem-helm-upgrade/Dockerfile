# component-reference: datahub-operator
ARG DEPENDENCY_INSTALLER_BASE_VERSION=0.1.48
FROM docker.wdf.sap.corp:51022/com.sap.datahub.linuxx86_64/datahub-operator-unit-test-framework:${DEPENDENCY_INSTALLER_BASE_VERSION}

ARG KUBECONFIG_PARENT=/tmp
ARG KUBECONFIG=${KUBECONFIG_PARENT}/.control-plane
ARG TEST_DIR=/infrabox/context/vsystem/infrabox/helm-upgrades
ARG ASYNC_TIMEOUT=300s
ARG CONSISTENTLY_TIMEOUT=10s

ENV KUBECONFIG_PARENT=${KUBECONFIG_PARENT}
ENV KUBECONFIG=${KUBECONFIG}
ENV TEST_DIR=${TEST_DIR}
ENV ASYNC_TIMEOUT=${ASYNC_TIMEOUT}
ENV CONSISTENTLY_TIMEOUT=${CONSISTENTLY_TIMEOUT}

RUN zypper rl libdb-4_8 && \
    zypper --non-interactive refresh && \
    zypper --non-interactive install perl perl-Error git-core

ENTRYPOINT ["/infrabox/context/infrabox/vsystem-helm-upgrade/entrypoint.sh"]
