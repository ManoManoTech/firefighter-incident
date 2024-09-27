# pylint: skip-file
import sys
from collections import OrderedDict
from collections.abc import Callable, Sequence
from configparser import ConfigParser
from pathlib import Path
from typing import Any, TypeVar, overload

from _typeshed import Incomplete

PYVERSION: sys._version_info
text_type: type[str]

read_config: Callable[[ConfigParser, Any], Any]
DEFAULT_ENCODING: str = "UTF-8"
TRUE_VALUES: set[str]
FALSE_VALUES: set[str]

def strtobool(value: str) -> bool: ...

class UndefinedValueError(Exception): ...
class Undefined: ...

undefined: Undefined

class Config:
    repository: Incomplete
    def __init__(self, repository: RepositoryEmpty) -> None: ...
    def get(self, option: str, default: Any = ..., cast: Any = ...) -> Any: ...
    def __call__(self, *args: Any, **kwargs: Any) -> str: ...

class RepositoryEmpty:
    def __init__(self, source: str = ..., encoding: str = ...) -> None: ...
    def __contains__(self, key: str) -> Any: ...
    def __getitem__(self, key: str) -> None: ...

class RepositoryIni(RepositoryEmpty):
    SECTION: str
    parser: ConfigParser
    def __init__(self, source: Any, encoding: str = ...) -> None: ...
    def __contains__(self, key: str) -> Any: ...
    def __getitem__(self, key: str) -> Any: ...

class RepositoryEnv(RepositoryEmpty):
    data: dict[Any, Any]
    def __init__(self, source: Any, encoding: Any = ...) -> None: ...
    def __contains__(self, key: Any) -> Any: ...
    def __getitem__(self, key: Any) -> Any: ...

class RepositorySecret(RepositoryEmpty):
    data: dict[Any, Any]
    def __init__(self, source: str = ...) -> None: ...
    def __contains__(self, key: Any) -> Any: ...
    def __getitem__(self, key: Any) -> Any: ...

_T = TypeVar("_T")
_Q = TypeVar("_Q")

class AutoConfig:
    SUPPORTED: OrderedDict[str, type[RepositoryEmpty]]
    encoding: str = "UTF-8"
    search_path: Path
    config: Config
    def __init__(self, search_path: str | Path | None = ...) -> None: ...
    @overload
    def __call__(self, arg: str, default: str = ...) -> str: ...
    @overload
    def __call__(self, arg: str, cast: Csv = ..., default: str = ...) -> list[str]: ...
    @overload
    def __call__(self, arg: str, cast: type[_T] = ...) -> _T: ...
    @overload
    def __call__(self, arg: str, default: _Q = ...) -> str | _Q: ...
    @overload
    def __call__(
        self, arg: str, default: _Q = ..., cast: type[_T] = ...
    ) -> _T | _Q: ...

config: AutoConfig

_RT = TypeVar("_RT", bound=list[Any] | set[Any])
_IT = TypeVar("_IT")

class Csv:
    cast: Callable[[str], Any]
    delimiter: str
    strip: str
    post_process: Callable[[list[Any]], Any]
    def __init__(
        self,
        cast: Callable[[str], _IT] = ...,
        delimiter: str = ",",
        strip: str = ...,
        post_process: Callable[[list[Any]], _RT] = ...,
    ) -> None: ...
    def __call__(self, value: str) -> Sequence[_IT]: ...

class Choices:
    flat: Incomplete
    cast: Incomplete
    choices: Incomplete
    def __init__(
        self,
        flat: list[Any] | None = ...,
        cast: Callable[..., Any] = ...,
        choices: tuple[Any] | None = ...,
    ) -> None: ...
    def __call__(self, value: str) -> Any: ...
