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
import abc
import argparse
import atexit
import itertools
import threading
import time
import traceback
from contextlib import AbstractContextManager
from datetime import datetime
from functools import wraps
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Union,
)

from neptune.common.deprecation import warn_once
from neptune.common.exceptions import UNIX_STYLES
from neptune.new.attributes import create_attribute_from_type
from neptune.new.attributes.attribute import Attribute
from neptune.new.attributes.namespace import Namespace as NamespaceAttr
from neptune.new.attributes.namespace import NamespaceBuilder
from neptune.new.exceptions import (
    InactiveModelException,
    InactiveModelVersionException,
    InactiveProjectException,
    InactiveRunException,
    MetadataInconsistency,
    NeptunePossibleLegacyUsageException,
)
from neptune.new.handler import Handler
from neptune.new.internal.backends.api_model import AttributeType
from neptune.new.internal.backends.neptune_backend import NeptuneBackend
from neptune.new.internal.backends.nql import NQLQuery
from neptune.new.internal.background_job import BackgroundJob
from neptune.new.internal.container_structure import ContainerStructure
from neptune.new.internal.container_type import ContainerType
from neptune.new.internal.id_formats import (
    SysId,
    UniqueId,
)
from neptune.new.internal.operation import DeleteAttribute
from neptune.new.internal.operation_processors.operation_processor import OperationProcessor
from neptune.new.internal.state import ContainerState
from neptune.new.internal.utils import (
    is_bool,
    is_dict_like,
    is_float,
    is_float_like,
    is_int,
    is_string,
    is_string_like,
    verify_type,
)
from neptune.new.internal.utils.logger import logger
from neptune.new.internal.utils.paths import parse_path
from neptune.new.internal.utils.runningmode import (
    in_interactive,
    in_notebook,
)
from neptune.new.internal.utils.uncaught_exception_handler import instance as uncaught_exception_handler
from neptune.new.internal.value_to_attribute_visitor import ValueToAttributeVisitor
from neptune.new.metadata_containers.metadata_containers_table import Table
from neptune.new.types import (
    Boolean,
    Integer,
)
from neptune.new.types.atoms.datetime import Datetime
from neptune.new.types.atoms.float import Float
from neptune.new.types.atoms.string import String
from neptune.new.types.mode import Mode
from neptune.new.types.namespace import Namespace
from neptune.new.types.value import Value
from neptune.new.types.value_copy import ValueCopy


def ensure_not_stopped(fun):
    @wraps(fun)
    def inner_fun(self: "MetadataContainer", *args, **kwargs):
        # pylint: disable=protected-access
        if self._state == ContainerState.STOPPED:
            if self.container_type == ContainerType.RUN:
                raise InactiveRunException(label=self._label)
            elif self.container_type == ContainerType.PROJECT:
                raise InactiveProjectException(label=self._label)
            elif self.container_type == ContainerType.MODEL:
                raise InactiveModelException(label=self._label)
            elif self.container_type == ContainerType.MODEL_VERSION:
                raise InactiveModelVersionException(label=self._label)
            else:
                raise ValueError(f"Unknown container type: {self.container_type}")
        return fun(self, *args, **kwargs)

    return inner_fun


class MetadataContainer(AbstractContextManager):
    container_type: ContainerType

    LEGACY_METHODS = set()

    def __init__(
        self,
        *,
        id_: UniqueId,
        mode: Mode,
        backend: NeptuneBackend,
        op_processor: OperationProcessor,
        background_job: BackgroundJob,
        lock: threading.RLock,
        project_id: UniqueId,
        project_name: str,
        workspace: str,
        sys_id: SysId,
    ):
        self._id = id_
        self._mode = mode
        self._project_id = project_id
        self._project_name = project_name
        self._workspace = workspace
        self._backend = backend
        self._op_processor = op_processor
        self._bg_job = background_job
        self._structure: ContainerStructure[Attribute, NamespaceAttr] = ContainerStructure(NamespaceBuilder(self))
        self._lock = lock
        self._state = ContainerState.CREATED
        self._sys_id = sys_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_tb is not None:
            traceback.print_exception(exc_type, exc_val, exc_tb)
        self.stop()

    def __getattr__(self, item):
        if item in self.LEGACY_METHODS:
            raise NeptunePossibleLegacyUsageException()
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    @property
    @abc.abstractmethod
    def _label(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _docs_url_stop(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _url(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def _metadata_url(self) -> str:
        raise NotImplementedError

    def _get_subpath_suggestions(self, path_prefix: str = None, limit: int = 1000) -> List[str]:
        parsed_path = parse_path(path_prefix or "")
        return list(itertools.islice(self._structure.iterate_subpaths(parsed_path), limit))

    def _ipython_key_completions_(self):
        return self._get_subpath_suggestions()

    @ensure_not_stopped
    def __getitem__(self, path: str) -> "Handler":
        return Handler(self, path)

    @ensure_not_stopped
    def __setitem__(self, key: str, value) -> None:
        self.__getitem__(key).assign(value)

    @ensure_not_stopped
    def __delitem__(self, path) -> None:
        self.pop(path)

    @ensure_not_stopped
    def assign(self, value, wait: bool = False) -> None:
        self._get_root_handler().assign(value, wait)

    @ensure_not_stopped
    def fetch(self) -> dict:
        return self._get_root_handler().fetch()

    def ping(self):
        self._backend.ping(self._id, self.container_type)

    def start(self):
        atexit.register(self._shutdown_hook)
        self._op_processor.start()
        self._bg_job.start(self)
        self._state = ContainerState.STARTED

    def stop(self, seconds: Optional[Union[float, int]] = None) -> None:
        verify_type("seconds", seconds, (float, int, type(None)))
        if self._state != ContainerState.STARTED:
            return

        self._state = ContainerState.STOPPING
        ts = time.time()
        logger.info("Shutting down background jobs, please wait a moment...")
        self._bg_job.stop()
        self._bg_job.join(seconds)
        logger.info("Done!")
        with self._lock:
            sec_left = None if seconds is None else seconds - (time.time() - ts)
            self._op_processor.stop(sec_left)
        if self._mode != Mode.OFFLINE:
            logger.info("Explore the metadata in the Neptune app:")
            logger.info(self._metadata_url)
        self._backend.close()
        self._state = ContainerState.STOPPED

    def get_structure(self) -> Dict[str, Any]:
        # This is very weird pylint false-positive.
        # pylint: disable=no-member
        return self._structure.get_structure().to_dict()

    def print_structure(self) -> None:
        self._print_structure_impl(self.get_structure(), indent=0)

    def _print_structure_impl(self, struct: dict, indent: int) -> None:
        for key in sorted(struct.keys()):
            print("    " * indent, end="")
            if isinstance(struct[key], dict):
                print("{blue}'{key}'{end}:".format(blue=UNIX_STYLES["blue"], key=key, end=UNIX_STYLES["end"]))
                self._print_structure_impl(struct[key], indent=indent + 1)
            else:
                print(
                    "{blue}'{key}'{end}: {type}".format(
                        blue=UNIX_STYLES["blue"],
                        key=key,
                        end=UNIX_STYLES["end"],
                        type=type(struct[key]).__name__,
                    )
                )

    def define(
        self,
        path: str,
        value: Union[Value, int, float, str, datetime],
        wait: bool = False,
    ) -> Attribute:
        if isinstance(value, Value):
            pass
        elif isinstance(value, Handler):
            value = ValueCopy(value)
        elif isinstance(value, argparse.Namespace):
            value = Namespace(vars(value))
        elif is_bool(value):
            value = Boolean(value)
        elif is_int(value):
            value = Integer(value)
        elif is_float(value):
            value = Float(value)
        elif is_string(value):
            value = String(value)
        elif isinstance(value, datetime):
            value = Datetime(value)
        elif is_float_like(value):
            value = Float(float(value))
        elif is_dict_like(value):
            value = Namespace(value)
        elif is_string_like(value):
            warn_once(
                message="The object you're logging will be implicitly cast to a string."
                " We'll end support of this behavior in `neptune-client==1.0.0`."
                " To log the object as a string, use `str(object)` instead.",
                stack_level=2,
            )
            value = String(str(value))
        else:
            raise TypeError("Value of unsupported type {}".format(type(value)))
        parsed_path = parse_path(path)

        with self._lock:
            old_attr = self._structure.get(parsed_path)
            if old_attr:
                raise MetadataInconsistency("Attribute or namespace {} is already defined".format(path))
            attr = ValueToAttributeVisitor(self, parsed_path).visit(value)
            self._structure.set(parsed_path, attr)
            attr.process_assignment(value, wait)
            return attr

    def get_attribute(self, path: str) -> Optional[Attribute]:
        with self._lock:
            return self._structure.get(parse_path(path))

    def set_attribute(self, path: str, attribute: Attribute) -> Optional[Attribute]:
        with self._lock:
            return self._structure.set(parse_path(path), attribute)

    def exists(self, path: str) -> bool:
        verify_type("path", path, str)
        return self.get_attribute(path) is not None

    @ensure_not_stopped
    def pop(self, path: str, wait: bool = False) -> None:
        verify_type("path", path, str)
        self._get_root_handler().pop(path, wait)

    def _pop_impl(self, parsed_path: List[str], wait: bool):
        self._structure.pop(parsed_path)
        self._op_processor.enqueue_operation(DeleteAttribute(parsed_path), wait)

    def lock(self) -> threading.RLock:
        return self._lock

    def wait(self, disk_only=False) -> None:
        with self._lock:
            if disk_only:
                self._op_processor.flush()
            else:
                self._op_processor.wait()

    def sync(self, wait: bool = True) -> None:
        with self._lock:
            if wait:
                self._op_processor.wait()
            attributes = self._backend.get_attributes(self._id, self.container_type)
            self._structure.clear()
            for attribute in attributes:
                self._define_attribute(parse_path(attribute.path), attribute.type)

    def _define_attribute(self, _path: List[str], _type: AttributeType):
        attr = create_attribute_from_type(_type, self, _path)
        self._structure.set(_path, attr)

    def _get_root_handler(self):
        return Handler(self, "")

    def get_url(self) -> str:
        """Returns the URL that can be accessed within the browser"""
        return self._url

    def _startup(self, debug_mode):
        if not debug_mode:
            logger.info(self.get_url())

        self.start()

        if not debug_mode:
            if in_interactive() or in_notebook():
                logger.info(
                    "Remember to stop your %s once you’ve finished logging your metadata (%s)."
                    " It will be stopped automatically only when the notebook"
                    " kernel/interactive console is terminated.",
                    self.container_type.value,
                    self._docs_url_stop,
                )

        uncaught_exception_handler.activate()

    def _shutdown_hook(self):
        self.stop()

    def _fetch_entries(self, child_type: ContainerType, query: NQLQuery, columns: Optional[Iterable[str]]) -> Table:
        if columns is not None:
            # always return entries with `sys/id` column when filter applied
            columns = set(columns)
            columns.add("sys/id")

        leaderboard_entries = self._backend.search_leaderboard_entries(
            project_id=self._project_id,
            types=[child_type],
            query=query,
            columns=columns,
        )

        return Table(
            backend=self._backend,
            container_type=child_type,
            entries=leaderboard_entries,
        )
