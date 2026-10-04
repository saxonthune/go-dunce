#!/usr/bin/env python3
"""go-dunce harness that runs `claude -p`, so a Claude subscription is enough.

The request and reply formats are in the README, under "Writing a harness".
"""

import argparse
import json
import subprocess
import sys

TEXT = {"text/plain", "text/markdown"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model")
    args = parser.parse_args()

    request = json.load(sys.stdin)
    unsupported = {p["media_type"] for p in request["parts"]} - TEXT
    if unsupported:
        sys.exit(f"claude_cli accepts text parts only, got {sorted(unsupported)}")

    # Tools, MCP servers, and user settings are off, so the reply depends only on this request.
    command = [
        "claude", "-p",
        "--output-format", "json",
        "--tools", "",
        "--strict-mcp-config",
        "--setting-sources", "",
        "--system-prompt", request["system"],
        "--json-schema", json.dumps(request["schema"]),
    ]
    if args.model:
        command += ["--model", args.model]
    prompt = "\n\n".join(p["content"] for p in request["parts"])
    done = subprocess.run(command, input=prompt, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        sys.exit(f"claude exited with {done.returncode}: {done.stderr[-2000:]}")
    reply = json.loads(done.stdout)
    if reply.get("is_error") or "structured_output" not in reply:
        sys.exit(f"claude returned no structured output: {done.stdout[-2000:]}")
    json.dump(reply["structured_output"], sys.stdout)


if __name__ == "__main__":
    main()
