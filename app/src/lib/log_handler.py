"""Log Handler for CloudWacht Logs."""

# This file is part of anfw-automate. See LICENSE file for license information.

import datetime
from enum import Enum

import boto3
from aws_lambda_powertools import Logger


class Level(Enum):
    INFO = 0
    WARN = 1
    ERROR = 2
    CRITICAL = 3
    DEBUG = 99


class CustomerLogHandler:
    """Sends logs to a specific Cloud Watch log group and stream."""

    def __init__(
        self,
        log_group_name: str,
        credentials: dict,
        version: str = None,  # Default value set to None if not provided
    ) -> None:
        self.log_group_name = log_group_name

        self.logger = Logger(child=True)
        self.version = version
        # Create CloudWatch Logs client with assumed role credentials
        self.logclient = boto3.client(
            "logs",
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
        self.s3client = boto3.client(
            "s3",
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
        self.logger.info(f"Got logclient {str(self.logclient)}")

    # Method to update the version attribute
    def update_version(self, new_version):
        self.version = new_version

    def send_log_message(self, log_stream_name: str, message: str, level=Level.DEBUG):
        """Send log message to the CloudWatch"""
        # prepare the message with the level
        if self.version is None:
            message = f'{{"level": "{level.name}", "message": "{message}"}}'
        else:
            message = f'{{"level": "{level.name}", "version": "{self.version}", "message": "{message}"}}'
        # fist get or create the log stream message (UTF8)
        self._check_log_stream(log_stream_name)
        _time_stamp = self._generate_time_stamp()
        self.logclient.put_log_events(
            logGroupName=self.log_group_name,
            logStreamName=log_stream_name,
            logEvents=[
                {"timestamp": _time_stamp, "message": message},
            ],
        )

    def export_logs_to_s3(self, log_stream_name: str, bucket_name: str) -> None:
        """Exports the log stream to an S3 bucket."""
        self.logclient.create_export_task(
            taskName="NFW_Customer_Log_Export",
            logGroupName=self.log_group_name,
            logStreamNamePrefix=log_stream_name,
            fromTime=self._generate_time_stamp_29d(),
            to=self._generate_time_stamp(),
            destination=bucket_name,
            destinationPrefix=f"{log_stream_name}",
        )

    def _check_log_stream(self, log_stream_name: str) -> None:
        """Checks if a LogStream is available or creates a new one."""
        try:
            # try to create the log stream
            self.logclient.create_log_stream(
                logGroupName=self.log_group_name, logStreamName=log_stream_name
            )
        except self.logclient.exceptions.ResourceAlreadyExistsException:
            # it is there
            self.logger.info(
                f"LogStream {log_stream_name} exists in {self.log_group_name}"
            )
            return
        except Exception:
            self.logger.exception("_check_log_stream - Exception")

    def generate_log_stream_name(self) -> str:
        """Generates the a log stream name based on current execution time"""
        current_time = datetime.datetime.now()
        epochash = self._generate_time_stamp()
        log_stream_name = current_time.strftime("%Y/%m/%d/%H/%M")
        self.logger.info(f"Log stream name: {log_stream_name}/{epochash} ")
        return f"{log_stream_name}/{epochash}"

    def _generate_time_stamp(self) -> int:
        """Generates the current time stamp for the log entry."""
        today = datetime.datetime.now()
        return int(round(today.timestamp() * 1000))

    def _generate_time_stamp_29d(self) -> int:
        """Generates a time stamp 29d in the past."""
        start_date = datetime.datetime.now() - datetime.timedelta(29)
        return int(round(start_date.timestamp() * 1000))
