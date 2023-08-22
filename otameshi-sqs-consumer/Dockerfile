FROM python:3.11.4-slim-bookworm

RUN apt-get update \
    && apt-get full-upgrade -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/otameshi_sqs_consumer
WORKDIR /opt/otameshi_sqs_consumer

COPY ./requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt -t .

COPY ./otameshi_sqs_consumer/ .

VOLUME /tmp/

CMD [ "python3", "./main.py" ]
