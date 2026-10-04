#!/usr/bin/env python3
"""go-dunce harness that calls the Anthropic API. Needs the `anthropic` package and ANTHROPIC_API_KEY.

The request and reply formats are in the README, under "Writing a harness".
"""

import argparse
import json
import sys

import anthropic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-opus-5")
    args = parser.parse_args()

    request = json.load(sys.stdin)
    content = []
    for part in request["parts"]:
        if part["media_type"].startswith("image/"):
            source = {"type": "base64", "media_type": part["media_type"], "data": part["content"]}
            content.append({"type": "image", "source": source})
        else:
            content.append({"type": "text", "text": part["content"]})

    response = anthropic.Anthropic().beta.messages.create(
        model=args.model,
        max_tokens=16000,
        system=request["system"],
        messages=[{"role": "user", "content": content}],
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": request["schema"]}},
        # On a safety decline, the API retries the request on a fallback model it picks.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        sys.exit(f"the model declined: {response.stop_details}")
    sys.stdout.write(next(block.text for block in response.content if block.type == "text"))


if __name__ == "__main__":
    main()
