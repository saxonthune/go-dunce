from __future__ import annotations

from ..contracts import Color, GameAnalysis, GameRecord, Mistake, MistakeSet, Severity

DEFAULT_THRESHOLDS = {Severity.INACCURACY: 1.5, Severity.MISTAKE: 3.0, Severity.BLUNDER: 6.0}
BETTER_MOVES_KEPT = 3


class ThresholdSelector:
    """Keeps the learner's moves that lost the most points, measured by the change in the engine's score lead."""

    def __init__(self, max_mistakes: int, thresholds: dict[Severity, float] = DEFAULT_THRESHOLDS) -> None:
        self.max_mistakes = max_mistakes
        self.thresholds = thresholds
        limits = ",".join(f"{s.value}={v}" for s, v in thresholds.items())
        self.produced_by = f"threshold/1 max={max_mistakes} {limits}"

    def select(self, game: GameRecord, analysis: GameAnalysis) -> MistakeSet:
        found = []
        for number, move in enumerate(game.moves, start=1):
            if game.player is not None and move.color is not game.player:
                continue
            before, after = analysis.positions[number - 1], analysis.positions[number]
            sign = 1 if move.color is Color.BLACK else -1
            points_lost = sign * (before.score_lead - after.score_lead)
            severity = self._severity(points_lost)
            if severity is None:
                continue
            found.append(
                Mistake(
                    move_number=number,
                    color=move.color,
                    played=move.point,
                    points_lost=round(points_lost, 1),
                    winrate_lost=round(sign * (before.winrate - after.winrate), 3),
                    severity=severity,
                    better=before.candidates[:BETTER_MOVES_KEPT],
                    punishment=after.candidates[0].pv if after.candidates else [],
                )
            )
        found.sort(key=lambda m: m.points_lost, reverse=True)
        kept = sorted(found[: self.max_mistakes], key=lambda m: m.move_number)
        return MistakeSet(produced_by=self.produced_by, game_id=game.game_id, thresholds=self.thresholds, mistakes=kept)

    def _severity(self, points_lost: float) -> Severity | None:
        reached = [s for s, limit in self.thresholds.items() if points_lost >= limit]
        return max(reached, key=lambda s: self.thresholds[s]) if reached else None
