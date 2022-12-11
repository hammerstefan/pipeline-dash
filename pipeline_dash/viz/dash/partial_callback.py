from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Concatenate, List, ParamSpec, Sequence, Union, TypeVar, Generic

import dash  # type: ignore

# P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class PartialCallback(Generic[T]):
    function: T
    outputs: list[dash.dependencies.Output] = field(default_factory=list)
    inputs: list[dash.dependencies.Input | dash.dependencies.State] = field(default_factory=list)
