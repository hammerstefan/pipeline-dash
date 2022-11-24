from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Concatenate, List, ParamSpec, Sequence, Union, TypeVar, Generic

import dash  # type: ignore

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class PartialCallback(Generic[T, P]):
    output: dash.dependencies.Output | List[dash.dependencies.Output]
    inputs: Sequence[dash.dependencies.Input | dash.dependencies.State]
    function: Callable[Concatenate[T, P], Any]
