
import json
from datetime import datetime, timedelta
from decimal import Decimal
from os import environ
from time import sleep
from uuid import uuid4

import boto3

_SQS_QUEUE_URL = environ["SQS_QUEUE_URL"]
_DYNAMODB_TABLE_NAME = environ["DYNAMODB_TABLE_NAME"]

_TIMEDELTA_DAY_1 = timedelta(days=1)


def process_messages(dynamodb_table, sqs_messages):

    wait_total = 0

    with dynamodb_table.batch_writer(overwrite_by_pkeys=["uuid", "timestamp"]) as dynamodb_batch_writer:
        for sqs_message in sqs_messages:

            print(sqs_message)
            message_body = json.loads(sqs_message.body)
            wait_total = message_body["wait"]
            utcnow = datetime.utcnow()

            dynamodb_batch_writer.put_item(
                Item={
                    "uuid": uuid4().bytes_le,
                    "timestamp": Decimal(utcnow.timestamp()),
                    "ttl": Decimal((utcnow + _TIMEDELTA_DAY_1).timestamp()),
                    "message_body": sqs_message.body,
                }
            )

    sleep(wait_total)


def main():

    running = True

    while running:

        sqs_queue = boto3.resource("sqs").Queue(_SQS_QUEUE_URL)
        dynamodb_table = boto3.resource("dynamodb").Table(_DYNAMODB_TABLE_NAME)

        try:
            while running:

                sqs_messages = sqs_queue.receive_messages(MaxNumberOfMessages=1, WaitTimeSeconds=20)
                if not sqs_messages:
                    print("no messages.")
                    continue

                print(f"received sqs messages. len={len(sqs_messages)}")

                process_messages(dynamodb_table, sqs_messages)

                result_delete = sqs_queue.delete_messages(
                    Entries=[
                        {
                            "Id": sqs_message.message_id,
                            "ReceiptHandle": sqs_message.receipt_handle,
                        }
                        for sqs_message in sqs_messages
                    ]
                )

                print("deleting results")
                print(result_delete)

        except KeyboardInterrupt:
            running = False

        except BaseException as e:
            print("cought unhandled exception.")
            print(e)
            sleep(1)


if __name__ == "__main__":
    main()
