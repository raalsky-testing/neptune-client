#
# Copyright (c) 2020, Neptune Labs Sp. z o.o.
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

# pylint: disable=protected-access

from mock import MagicMock

from neptune.new.attributes.atoms.string import (
    String,
    StringVal,
)
from neptune.new.internal.operation import AssignString
from tests.neptune.new.attributes.test_attribute_base import TestAttributeBase


class TestString(TestAttributeBase):
    def test_assign(self):
        value_and_expected = [
            ("qwertyu", "qwertyu"),
            (StringVal("Some string"), "Some string"),
        ]

        for value, expected in value_and_expected:
            processor = MagicMock()
            exp, path, wait = (
                self._create_run(processor),
                self._random_path(),
                self._random_wait(),
            )
            var = String(exp, path)
            var.assign(value, wait=wait)
            processor.enqueue_operation.assert_called_once_with(AssignString(path, expected), wait)

    def test_get(self):
        exp, path = self._create_run(), self._random_path()
        var = String(exp, path)
        var.assign("adfh")
        self.assertEqual("adfh", var.fetch())
