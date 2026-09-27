from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from ..contracts import SourceGame

API = "https://online-go.com/api/v1"
REF = re.compile(r"(?:online-go\.com/)?(review|game)[/:](\d+)")


class OgsFetcher:
    """Downloads an OGS game (directly or through a review of it) into the input directory.

    Files already on disk are reused, so games stay available after they leave OGS.
    """

    produced_by = "ogs/1"

    def __init__(self, input_dir: Path) -> None:
        self.input_dir = input_dir

    def fetch(self, ref: str) -> SourceGame:
        match = REF.search(ref)
        if not match:
            raise ValueError(f"expected an OGS game or review URL, or game:<id> / review:<id>, got {ref!r}")
        kind, number = match.groups()

        owner = None
        if kind == "review":
            review = self._cached_json(f"ogs-review-{number}.json", f"{API}/reviews/{number}")
            game_number = str(review["game"]["id"])
            owner = review["owner"]["username"]
        else:
            game_number = number

        game_id = f"ogs-{game_number}"
        source_path = self.input_dir / f"{game_id}.source.json"
        if source_path.exists():
            source = SourceGame.model_validate_json(source_path.read_text())
            if owner and not source.owner:
                source = source.model_copy(update={"owner": owner})
                source_path.write_text(source.model_dump_json(indent=2))
            return source

        self._cached_json(f"{game_id}.game.json", f"{API}/games/{game_number}")
        sgf_name = f"{game_id}.sgf"
        sgf_path = self.input_dir / sgf_name
        if not sgf_path.exists():
            sgf_path.write_bytes(self._get(f"{API}/games/{game_number}/sgf").content)

        source = SourceGame(
            produced_by=self.produced_by,
            game_id=game_id,
            source_url=f"https://online-go.com/game/{game_number}",
            sgf_path=sgf_name,
            owner=owner,
        )
        source_path.write_text(source.model_dump_json(indent=2))
        return source

    def _cached_json(self, name: str, url: str) -> dict:
        path = self.input_dir / name
        if not path.exists():
            path.write_bytes(self._get(url).content)
        return json.loads(path.read_text())

    @staticmethod
    def _get(url: str) -> httpx.Response:
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        return response
