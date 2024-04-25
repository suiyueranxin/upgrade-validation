FROM alpine:3.3
RUN apk update && apk upgrade && \
    apk add --no-cache bash git openssh

COPY infrabox/tag_code/id_rsa infrabox/tag_code/id_rsa.pub infrabox/tag_code/known_hosts /root/.ssh/
RUN mkdir -p /project
COPY infrabox/tag_code/entrypoint.sh /project/
RUN chmod 600 /root/.ssh/id_rsa
RUN chmod +x /project/entrypoint.sh

ENTRYPOINT /project/entrypoint.sh
