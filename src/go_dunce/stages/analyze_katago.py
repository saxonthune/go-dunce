from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..contracts import Candidate, Color, GameAnalysis, GameRecord, PositionEval
from ..coords import from_gtp, to_gtp

KATAGO_RULES = {"chinese", "japanese", "korean", "aga", "new-zealand", "tromp-taylor", "stone-scoring"}
CANDIDATES_KEPT = 5


class KataGoAnalyzer:
    """Evaluates every position of a game with KataGo's JSON analysis engine."""

    def __init__(self, engine_dir: Path, max_visits: int) -> None:
        self.binary = engine_dir / "katago"
        # The example config reports winrates and scores from Black's side, which the contract requires.
        self.config = engine_dir / "analysis_example.cfg"
        self.model = engine_dir / "model.bin.gz"
        self.log_dir = engine_dir / "logs"
        self.max_visits = max_visits
        self.produced_by = f"katago/{(engine_dir / 'model.bin.gz').resolve().name} visits={max_visits}"

    def analyze(self, game: GameRecord) -> GameAnalysis:
        for path in (self.binary, self.config, self.model):
            if not path.exists():
                raise FileNotFoundError(f"{path} is missing; run scripts/install-katago.sh")

        size = game.board_size
        rules = game.rules.lower()
        query = {
            "id": game.game_id,
            "moves": [[m.color.value, to_gtp(m.point, size)] for m in game.moves],
            "initialStones": [["B", to_gtp(p, size)] for p in game.setup_black]
            + [["W", to_gtp(p, size)] for p in game.setup_white],
            "rules": rules if rules in KATAGO_RULES else "chinese",
            "komi": game.komi,
            "boardXSize": size,
            "boardYSize": size,
            "analyzeTurns": list(range(len(game.moves) + 1)),
            "maxVisits": self.max_visits,
        }
        responses = self._run(query)

        positions = []
        for turn in range(len(game.moves) + 1):
            r = responses[turn]
            infos = sorted(r["moveInfos"], key=lambda m: m["order"])[:CANDIDATES_KEPT]
            positions.append(
                PositionEval(
                    moves_played=turn,
                    to_play=Color(r["rootInfo"]["currentPlayer"]),
                    winrate=r["rootInfo"]["winrate"],
                    score_lead=r["rootInfo"]["scoreLead"],
                    candidates=[
                        Candidate(
                            point=from_gtp(m["move"], size),
                            visits=m["visits"],
                            winrate=m["winrate"],
                            score_lead=m["scoreLead"],
                            pv=[from_gtp(p, size) for p in m.get("pv", [])],
                        )
                        for m in infos
                    ],
                )
            )
        return GameAnalysis(produced_by=self.produced_by, game_id=game.game_id, positions=positions)

    def _run(self, query: dict) -> dict[int, dict]:
        self.log_dir.mkdir(exist_ok=True)
        command = [
            str(self.binary), "analysis",
            "-config", str(self.config),
            "-model", str(self.model),
            "-override-config", f"logDir={self.log_dir}",
        ]
        # KataGo answers every query in the batch, then exits once stdin closes.
        done = subprocess.run(command, input=json.dumps(query) + "\n", capture_output=True, text=True, check=False)
        responses: dict[int, dict] = {}
        for text in done.stdout.splitlines():
            if not text.startswith("{"):
                continue
            message = json.loads(text)
            if "error" in message:
                raise RuntimeError(f"KataGo rejected the query: {message['error']}")
            if "warning" in message:
                continue
            responses[message["turnNumber"]] = message
        missing = [t for t in query["analyzeTurns"] if t not in responses]
        if missing:
            raise RuntimeError(f"KataGo returned no analysis for turns {missing}; stderr:\n{done.stderr[-2000:]}")
        return responses
