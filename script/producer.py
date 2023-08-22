
import json
from datetime import datetime
from os import environ
from random import randint
from time import sleep
from uuid import uuid4

import boto3


_NAMES = ("spam", "hum", "egg", "wakame", "kombu", "mozc", )
_LEN_NAMES = len(_NAMES)


def generate_message(wait: int):
    return json.dumps(
        {
            "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "wait": wait,
            "message": _NAMES[randint(0, _LEN_NAMES - 1)],
        },
        separators=(",", ":")
    )


def main():

    sqs_queue = boto3.resource("sqs").Queue(environ["SQS_QUEUE_URL"])

    send_msg_batch_size = 1
    send_interval = 25
    wait = 60

    running = True
    while running:

        try:
            sqs_queue.send_messages(
                Entries=[
                    {
                        "Id": str(uuid4()),
                        "MessageBody": generate_message(wait),
                    }
                    for _ in range(send_msg_batch_size)
                ]
            )
            sleep(send_interval)

        except KeyboardInterrupt:
            running = False


if __name__ == "__main__":
    main()
