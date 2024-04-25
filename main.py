import argparse
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

import boto3
import docker
from botocore.exceptions import ClientError
from docker.models.containers import Container
from mypy_boto3_logs import CloudWatchLogsClient  # Используется для аннотации типа

logger = logging.getLogger(__name__)


@contextmanager
def managed_container(image: str, command: str, detach: bool = True, auto_remove: bool = True) -> Container:
    client = docker.from_env()
    command = ["/bin/sh", "-c", command]

    container: Container = client.containers.run(image=image, command=command, detach=detach)
    try:
        logger.info("Docker container started: %s", container)
        yield container
    finally:
        container.stop()
        if auto_remove:
            container.remove()
        logger.info("Docker container stopped and removed: %s", container.id)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for the Docker and AWS configuration."""
    parser = argparse.ArgumentParser(description="Run a Docker container and log output to AWS CloudWatch.")
    parser.add_argument("--docker-image", required=True, help="Name of the Docker image")
    parser.add_argument("--bash-command", required=True, help="Bash command to run inside the Docker image")
    parser.add_argument("--aws-cloudwatch-group", required=True, help="AWS CloudWatch log group name")
    parser.add_argument("--aws-cloudwatch-stream", required=True, help="AWS CloudWatch log stream name")
    parser.add_argument("--aws-access-key-id", required=True, help="AWS access key ID")
    parser.add_argument("--aws-secret-access-key", required=True, help="AWS secret access key")
    parser.add_argument("--aws-region", required=True, help="AWS region")
    return parser.parse_args()


def handle_cloudwatch_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle exceptions for AWS CloudWatch operations."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceAlreadyExistsException":
                logger.info("Resource already exists: %s", kwargs.get("group_name", "Unknown"))
            else:
                logger.exception("AWS request failed: %s")
                raise
        except Exception:
            logger.exception("Unexpected error occurred")
            raise

    return wrapper


@handle_cloudwatch_errors
def create_or_verify_cloudwatch_log_group(cloudwatch: CloudWatchLogsClient, group_name: str) -> None:
    """Ensure the CloudWatch log group exists or create it."""
    cloudwatch.create_log_group(logGroupName=group_name)


@handle_cloudwatch_errors
def create_or_verify_cloudwatch_log_stream(cloudwatch: CloudWatchLogsClient, group_name: str, stream_name: str) -> None:
    """Ensure the CloudWatch log stream exists or create it."""
    cloudwatch.create_log_stream(logGroupName=group_name, logStreamName=stream_name)


def get_cloudwatch_logs(client: CloudWatchLogsClient, log_group_name: str, log_stream_name: str) -> None:
    try:
        response = client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name
        )
        events = response["events"]
        for event in events:
            logger.info("Log event: %s", event["message"])
    except Exception:
        logger.exception("Error getting log events")


@handle_cloudwatch_errors
def write_logs_to_cloudwatch(cloudwatch: CloudWatchLogsClient, args: argparse.Namespace, line: bytes) -> None:
    response = cloudwatch.put_log_events(
        logGroupName=args.aws_cloudwatch_group,
        logStreamName=args.aws_cloudwatch_stream,
        logEvents=[{"timestamp": int(time.time() * 1000), "message": line.decode("utf-8")}]
    )

    if "Failed" in response:
        logger.error("Failed to send log to CloudWatch: %s", response)
    else:
        logger.info("Successfully sent log to CloudWatch: %s", response.get("ResponseMetadata", {}).get("RequestId"))


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def main() -> None:
    """Main function to handle Docker and CloudWatch operations."""
    setup_logging()

    args = parse_arguments()

    cloudwatch: CloudWatchLogsClient = boto3.client(
        "logs",
        region_name=args.aws_region,
        aws_access_key_id=args.aws_access_key_id,
        aws_secret_access_key=args.aws_secret_access_key
    )
    # Ensure CloudWatch resources are available
    create_or_verify_cloudwatch_log_group(cloudwatch, args.aws_cloudwatch_group)
    create_or_verify_cloudwatch_log_stream(cloudwatch, args.aws_cloudwatch_group, args.aws_cloudwatch_stream)
    with managed_container(image=args.docker_image, command=args.bash_command, detach=True) as container:
        for line in container.logs(stream=True):
            logger.info("Container log: %s", line)
            write_logs_to_cloudwatch(cloudwatch, args, line)


if __name__ == "__main__":
    # for run
    # python main.py --docker-image python --bash-command "pip install -U pip && pip install tqdm && python -u -c \"exec('import time\\ncounter=0\\nwhile True:\\n print(counter)\\n counter+=1\\n time.sleep(0.1)')\"" --aws-cloudwatch-group test-task-group-1 --aws-cloudwatch-stream test-task-stream-1 --aws-access-key-id test --aws-secret-access-key test --aws-region us-west-2
    main()
