"""Backends that turn a prompt into a validated pydantic object."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
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


class ClaudeCli:
    """Runs `claude -p` so the pipeline works on a Claude subscription without an API key.

    Tools, MCP servers, and user settings are switched off so each call carries only this prompt.
    """

    def __init__(self, model: str | None) -> None:
        self.model = model
        self.produced_by = f"claude-cli/{model or 'default'}"

    def generate(self, system: str, parts: list[Part], schema: type[T]) -> T:
        unsupported = {p.media_type for p in parts} - {"text/plain", "text/markdown"}
        if unsupported:
            raise ValueError(f"the claude-cli backend accepts text only, got {sorted(unsupported)}")
        command = [
            "claude", "-p",
            "--output-format", "json",
            "--tools", "",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--system-prompt", system,
            "--json-schema", json.dumps(schema.model_json_schema()),
        ]
        if self.model:
            command += ["--model", self.model]
        prompt = "\n\n".join(p.content for p in parts)
        done = subprocess.run(command, input=prompt, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise RuntimeError(f"claude exited with {done.returncode}: {done.stderr[-2000:]}")
        reply = json.loads(done.stdout)
        if reply.get("is_error") or "structured_output" not in reply:
            raise RuntimeError(f"claude returned no structured output: {done.stdout[-2000:]}")
        return schema.model_validate(reply["structured_output"])


class AnthropicApi:
    def __init__(self, model: str | None) -> None:
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model or "claude-opus-5"
        self.produced_by = f"anthropic-api/{self.model}"

    def generate(self, system: str, parts: list[Part], schema: type[T]) -> T:
        content = []
        for part in parts:
            if part.media_type.startswith("image/"):
                source = {"type": "base64", "media_type": part.media_type, "data": part.content}
                content.append({"type": "image", "source": source})
            else:
                content.append({"type": "text", "text": part.content})
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            thinking={"type": "adaptive"},
            output_config={"format": {"type": "json_schema", "schema": schema.model_json_schema()}},
            # On a safety decline, the API retries the request on a fallback model it picks.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"the model declined: {response.stop_details}")
        text = next(block.text for block in response.content if block.type == "text")
        return schema.model_validate_json(text)


BACKENDS = {"claude-cli": ClaudeCli, "anthropic-api": AnthropicApi}
