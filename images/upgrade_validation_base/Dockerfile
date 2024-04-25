FROM docker.wdf.sap.corp:51022/com.sap.datahub.linuxx86_64/sles:15.0-sap-009

RUN pip3 install pytest requests pyyaml pytest_check
RUN curl -L -s -o /usr/bin/jq https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64 && chmod oug+x /usr/bin/jq
