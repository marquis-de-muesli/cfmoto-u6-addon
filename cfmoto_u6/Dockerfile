FROM ghcr.io/home-assistant/base:latest

RUN apk add --no-cache \
    python3 \
    py3-requests \
    py3-paho-mqtt

COPY run.sh /
COPY cfmoto_u6.py /

RUN chmod a+x /run.sh

CMD ["/run.sh"]