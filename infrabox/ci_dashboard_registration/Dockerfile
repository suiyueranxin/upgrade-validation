FROM registry.datahub.only.sap/bdh-infra-tools/python:3.7.0-alpine3.8

RUN apk add git
RUN pip install requests GitPython==3.1.17

WORKDIR /workdir

COPY ./infrabox/ci_dashboard_registration/*.py /workdir

CMD ["python", "registration_to_ci_dashboard.py"]

