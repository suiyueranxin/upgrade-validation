# Please follow the following steps to update an image:

1. login to the docker registry:

```
export DOCKER_WDF_PASSWORD=
docker login -u vora_docker -p $DOCKER_WDF_PASSWORD docker.wdf.sap.corp:51055
```

2. build the image with the new version tag:

```
export NEW_VERSION_TAG=
docker build -t docker.wdf.sap.corp:51055/com.sap.datahub.linuxx86_64/upgrade-validation-base:$NEW_VERSION_TAG .
```

3. push the image to the registry:

```
docker push docker.wdf.sap.corp:51055/com.sap.datahub.linuxx86_64/upgrade-validation-base:$NEW_VERSION_TAG
```
