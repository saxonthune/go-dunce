"""Runs a harness: any command that reads a JSON request on stdin and prints a JSON reply.

The formats are in the README, under "Writing a harness".
"""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import asdict, dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class Part:
    media_type: str
    content: str


class LLM(Protocol):
    produced_by: str

    def generate(self, system: str, parts: list[Part], schema: type[T]) -> T: ...


class Harness:
    def __init__(self, command: str) -> None:
        self.argv = shlex.split(command)
        self.produced_by = f"harness:{command}"

    def generate(self, system: str, parts: list[Part], schema: type[T]) -> T:
        request = {"system": system, "parts": [asdict(p) for p in parts], "schema": schema.model_json_schema()}
        done = subprocess.run(self.argv, input=json.dumps(request), capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise RuntimeError(f"harness {self.argv[0]} exited with {done.returncode}: {done.stderr[-2000:]}")
        return schema.model_validate_json(done.stdout)
