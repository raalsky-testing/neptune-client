#
# Copyright (c) 2019, Neptune Labs Sp. z o.o.
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

import time

import jwt

from tests.neptune.legacy.random_utils import a_string

SECRET = "secret"


def an_access_token():
    return jwt.encode(
        {
            "exp": time.time(),
            "azp": a_string(),
            "iss": "http://{}.com".format(a_string()),
        },
        SECRET,
    )


def a_refresh_token():
    return jwt.encode({"exp": 0, "azp": a_string(), "iss": "http://{}.com".format(a_string())}, SECRET)
