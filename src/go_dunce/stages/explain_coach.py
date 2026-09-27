from __future__ import annotations

from ..contracts import (
    Color,
    Contract,
    Explanation,
    ExplanationSet,
    GameRecord,
    Mistake,
    MistakeSet,
    RenderSet,
    Theme,
)
from ..coords import line, to_gtp
from ..llm import LLM, Part

RECENT_MOVES_SHOWN = 6

SYSTEM = f"""\
You are a Go teacher reviewing a beginner's game, move by move.

KataGo, a superhuman Go engine, has already judged each move. Its numbers and
variations are correct; never contradict them. Do not claim to have read a
sequence that the given variations do not show. Your job is to say, in words a
beginner can follow, why the engine's move is better: what the played move
neglected or overdid, and what idea the better move carries.

Write plainly. The first time you use a Go term (for example "atari",
"liberty", "sente"), define it in a short clause. Refer to points by their
coordinates, like D5.

For each mistake, pick one to three themes, most important first, from this
list: {", ".join(t.value for t in Theme)}.
"""


class ExplanationDraft(Contract):
    explanations: list[Explanation]


class CoachExplainer:
    """Explains all of a game's mistakes in one request, so the model sees the game's arc."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.produced_by = f"coach/1 {llm.produced_by}"
        self.last_prompt: list[Part] = []

    def explain(self, game: GameRecord, mistakes: MistakeSet, renders: RenderSet) -> ExplanationSet:
        if not mistakes.mistakes:
            return ExplanationSet(produced_by=self.produced_by, game_id=game.game_id, explanations=[])
        boards = {r.move_number: r for r in renders.positions}
        parts = [Part("text/plain", _game_header(game, len(mistakes.mistakes)))]
        for mistake in mistakes.mistakes:
            board = boards[mistake.move_number]
            parts.append(Part("text/plain", _mistake_facts(game, mistake) + f"\nBoard key: {board.legend}"))
            parts.append(Part(board.media_type, board.content))
        self.last_prompt = parts

        draft = self.llm.generate(SYSTEM, parts, ExplanationDraft)
        expected = {m.move_number for m in mistakes.mistakes}
        returned = {e.move_number for e in draft.explanations}
        if returned != expected:
            raise ValueError(f"explanations cover moves {sorted(returned)}, expected {sorted(expected)}")
        return ExplanationSet(produced_by=self.produced_by, game_id=game.game_id, explanations=draft.explanations)


def _game_header(game: GameRecord, count: int) -> str:
    learner = game.player.word if game.player else "both players"
    return (
        f"Game: {game.black} (Black) vs {game.white} (White), {game.board_size}x{game.board_size}, "
        f"komi {game.komi}, {game.rules} rules, result {game.result or 'unknown'}.\n"
        f"The learner played {learner}. Explain each of the {count} mistakes below."
    )


def _mistake_facts(game: GameRecord, m: Mistake) -> str:
    size = game.board_size
    sign = 1 if m.color is Color.BLACK else -1

    def lead(score_lead: float) -> str:
        return f"{m.color.word} {'leads' if sign * score_lead >= 0 else 'trails'} by {abs(score_lead):.1f}"

    start = max(0, m.move_number - 1 - RECENT_MOVES_SHOWN)
    recent = ", ".join(
        f"{mv.color.value} {to_gtp(mv.point, size)}" for mv in game.moves[start : m.move_number - 1]
    )
    better = "\n".join(
        f"  {label} = {to_gtp(c.point, size)} ({lead(c.score_lead)}); expected line: {line(c.pv[:8], size)}"
        for label, c in zip("ABC", m.better)
    )
    return (
        f"## Move {m.move_number}: {m.color.word} played {to_gtp(m.played, size)}, a {m.severity.value}\n"
        f"It lost {m.points_lost:.1f} points and {m.winrate_lost:.0%} of {m.color.word}'s winning chances.\n"
        f"Moves just before it: {recent or 'none'}\n"
        f"Engine's preferred moves:\n{better}\n"
        f"Engine's expected reply to the move played: {line(m.punishment[:8], size) or 'none'}"
    )
