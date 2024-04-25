FROM docker.wdf.sap.corp:51055/com.sap.datahub.linuxx86_64/upgrade-validation-base:1

COPY deps/ /deps/
COPY tests/ /tests/
COPY pylibs /pylibs/
COPY get_upgrade_versions.sh /
COPY infrabox/upgrade-validation/entrypoint.sh /

ENV LANG C.UTF-8

ENTRYPOINT ["/entrypoint.sh"]
