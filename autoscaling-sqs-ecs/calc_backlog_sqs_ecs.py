
from json import dumps
from os import environ

import boto3


_sqs_client = boto3.client("sqs")
_ecs_client = boto3.client("ecs")
_application_autoscaling_client = boto3.client("application-autoscaling")
_cw_client = boto3.client("cloudwatch")

_SQS_QUEUE_URL = environ.get("SQS_QUEUE_URL")
_ECS_CLUSTER_NAME = environ.get("ECS_CLUSTER_NAME")
_ECS_SERVICE_NAME = environ.get("ECS_SERVICE_NAME")
_MAX_CAPACITY = int(environ.get("MAX_CAPACITY", 1))
_MIN_CAPACITY = int(environ.get("MIN_CAPACITY", 1))
_EXPECTED_MSG_CAPACITY_PER_TASK = int(environ.get("EXPECTED_MSG_CAPACITY_PER_TASK", 1))


def _put_metric(
        ecs_cluster_name: str, ecs_service_name: str,
        approximate_number_of_messages: int, running_count: int, expected_msg_capacity_per_task: int):

    _cw_client.put_metric_data(
        Namespace="CustomMetricsForAutoScaling/ECS/Task",
        MetricData=(
            {
                "MetricName": "Backlog",
                "Dimensions": [
                    {
                        "Name": "ClusterName",
                        "Value": ecs_cluster_name,
                    },
                    {
                        "Name": "ServiceName",
                        "Value": ecs_service_name,
                    },
                ],
                "Value": approximate_number_of_messages - running_count * expected_msg_capacity_per_task
            },
        ),
    )


def handler_main(
        sqs_queue_url: str, ecs_cluster_name: str, ecs_service_name: str,
        min_capacity: int, max_capacity: int, expected_msg_capacity_per_task: int):

    sqs_queue_attributes = _sqs_client.get_queue_attributes(
        QueueUrl=sqs_queue_url,
        AttributeNames=(
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesDelayed",
            "ApproximateNumberOfMessagesNotVisible",
        ),
    )["Attributes"]

    approximate_number_of_messages = int(sqs_queue_attributes["ApproximateNumberOfMessages"])
    approximate_number_of_messages_delayed = int(sqs_queue_attributes["ApproximateNumberOfMessagesDelayed"])
    approximate_number_of_messages_not_visible = int(sqs_queue_attributes["ApproximateNumberOfMessagesNotVisible"])

    running_count = _ecs_client.describe_services(
        cluster=ecs_cluster_name,
        services=(ecs_service_name, ),
    )["services"][0]["runningCount"]  # pyright: ignore[reportTypedDictNotRequiredAccess]

    print(dumps(
        {
            "ApproximateNumberOfMessages": approximate_number_of_messages,
            "ApproximateNumberOfMessagesDelayed": approximate_number_of_messages_delayed,
            "ApproximateNumberOfMessagesNotVisible": approximate_number_of_messages_not_visible,
            "runningCount": running_count,
        },
        separators=(",", ":"),
    ))

    if not running_count:

        if approximate_number_of_messages:
            print("start task")
            _application_autoscaling_client.register_scalable_target(
                ServiceNamespace="ecs",
                ResourceId=f"service/{ecs_cluster_name}/{ecs_service_name}",
                ScalableDimension="ecs:service:DesiredCount",
                MinCapacity=min_capacity,
                MaxCapacity=max_capacity,
            )
            _put_metric(
                ecs_cluster_name, ecs_service_name,
                approximate_number_of_messages, min_capacity, expected_msg_capacity_per_task
            )

        else:
            # no message
            pass

        return

    assert running_count

    if all((
            not approximate_number_of_messages,
            not approximate_number_of_messages_delayed,
            not approximate_number_of_messages_not_visible,)):

        print("shutdown all tasks")
        _application_autoscaling_client.register_scalable_target(
            ServiceNamespace="ecs",
            ResourceId=f"service/{ecs_cluster_name}/{ecs_service_name}",
            ScalableDimension="ecs:service:DesiredCount",
            MinCapacity=0,
            MaxCapacity=0,
        )
        return

    _put_metric(
        ecs_cluster_name, ecs_service_name,
        approximate_number_of_messages, running_count, expected_msg_capacity_per_task
    )


def lambda_handler(event, context):
    handler_main(
        _SQS_QUEUE_URL, _ECS_CLUSTER_NAME, _ECS_SERVICE_NAME, # pyright: ignore[reportGeneralTypeIssues]
        _MAX_CAPACITY, _MIN_CAPACITY, _EXPECTED_MSG_CAPACITY_PER_TASK  # pyright: ignore[reportGeneralTypeIssues]
    )


def main():
    handler_main(
        _SQS_QUEUE_URL, _ECS_CLUSTER_NAME, _ECS_SERVICE_NAME,  # pyright: ignore[reportGeneralTypeIssues]
        _MAX_CAPACITY, _MIN_CAPACITY, _EXPECTED_MSG_CAPACITY_PER_TASK  # pyright: ignore[reportGeneralTypeIssues]
    )


if __name__ == "__main__":
    main()
