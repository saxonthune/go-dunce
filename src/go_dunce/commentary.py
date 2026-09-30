from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .contracts import GameCommentary

FILE = "commentary.json"


def save(output_dir: Path, game_id: str, draft_path: Path) -> Path:
    """Validates a draft commentary and stores it with the game's other outputs, replacing any earlier one."""
    data = json.loads(draft_path.read_text())
    data.setdefault("game_id", game_id)
    data.setdefault("written_on", date.today().isoformat())
    commentary = GameCommentary.model_validate(data)
    if commentary.game_id != game_id:
        raise ValueError(f"draft is for {commentary.game_id}, not {game_id}")
    game_dir = output_dir / game_id
    if not game_dir.is_dir():
        raise FileNotFoundError(f"{game_dir} does not exist; run the pipeline on this game first")
    path = game_dir / FILE
    path.write_text(commentary.model_dump_json(indent=2))
    return path


def load_all(output_dir: Path) -> list[GameCommentary]:
    """Every stored commentary, oldest game first. OGS game ids increase over time."""
    found = [GameCommentary.model_validate_json(p.read_text()) for p in output_dir.glob(f"*/{FILE}")]
    return sorted(found, key=lambda c: (len(c.game_id), c.game_id))


def history_markdown(commentaries: list[GameCommentary]) -> str:
    out = []
    for c in commentaries:
        out += [
            f"## {c.game_id} (written {c.written_on} by {c.author})",
            "",
            c.summary,
            "",
            f"**Level.** {c.player_level}",
            "",
            f"**Themes:** {', '.join(t.value for t in c.themes)}",
            "",
        ]
        out += [f"- Move {m.move_number}: {m.note}" for m in c.key_moments]
        out.append("")
    return "\n".join(out)
