#
# Copyright (c) 2022, Neptune Labs Sp. z o.o.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# pylint: disable=unused-import
__all__ = [
    "API_TOKEN_ENV_NAME",
    "CONNECTION_MODE",
    "PROJECT_ENV_NAME",
    "CUSTOM_RUN_ID_ENV_NAME",
    "MONITORING_NAMESPACE",
    "NEPTUNE_ALLOW_SELF_SIGNED_CERTIFICATE",
    "NEPTUNE_NOTEBOOK_ID",
    "NEPTUNE_NOTEBOOK_PATH",
    "NEPTUNE_RETRIES_TIMEOUT_ENV",
    "NEPTUNE_SYNC_BATCH_TIMEOUT_ENV",
    "NEPTUNE_SUBPROCESS_KILL_TIMEOUT",
    "NEPTUNE_FETCH_TABLE_STEP_SIZE",
]

from neptune.common.envs import API_TOKEN_ENV_NAME

CONNECTION_MODE = "NEPTUNE_MODE"

PROJECT_ENV_NAME = "NEPTUNE_PROJECT"

CUSTOM_RUN_ID_ENV_NAME = "NEPTUNE_CUSTOM_RUN_ID"

MONITORING_NAMESPACE = "NEPTUNE_MONITORING_NAMESPACE"

NEPTUNE_ALLOW_SELF_SIGNED_CERTIFICATE = "NEPTUNE_ALLOW_SELF_SIGNED_CERTIFICATE"

NEPTUNE_NOTEBOOK_ID = "NEPTUNE_NOTEBOOK_ID"

NEPTUNE_NOTEBOOK_PATH = "NEPTUNE_NOTEBOOK_PATH"

NEPTUNE_RETRIES_TIMEOUT_ENV = "NEPTUNE_RETRIES_TIMEOUT"

NEPTUNE_SYNC_BATCH_TIMEOUT_ENV = "NEPTUNE_SYNC_BATCH_TIMEOUT"

NEPTUNE_SUBPROCESS_KILL_TIMEOUT = "NEPTUNE_SUBPROCESS_KILL_TIMEOUT"

NEPTUNE_FETCH_TABLE_STEP_SIZE = "NEPTUNE_FETCH_TABLE_STEP_SIZE"

S3_ENDPOINT_URL = "S3_ENDPOINT_URL"
