from __future__ import annotations

from collections import defaultdict

from ..contracts import Contract, StudyItem, StudyPlan, ThemeTally
from ..llm import LLM, Part
from . import ReviewedGame

SYSTEM = """\
You are a Go teacher planning a beginner's study. You receive every mistake
from their recent games, already explained and labeled with themes, plus a
count of how many points each theme cost them.

Write a short overview of the learner's recurring weaknesses, then three to
five study items, most valuable first. Base every item on mistakes that
actually recur in the data; cite move numbers as evidence. For practice,
name a concrete exercise type (for example "9x9 life-and-death problems
where the corner group has two eyes' worth of space") rather than a
generic instruction like "study more". Write plainly, and define any Go term
in a short clause the first time you use it.
"""


class PlanDraft(Contract):
    overview: str
    study_items: list[StudyItem]


class CoachSummarizer:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.produced_by = f"coach-summary/1 {llm.produced_by}"

    def summarize(self, reviewed: list[ReviewedGame]) -> StudyPlan:
        tallies = tally(reviewed)
        lines = ["Theme totals (points lost, count):"]
        lines += [f"- {t.theme.value}: {t.points_lost:.1f} points over {t.count} mistakes" for t in tallies]
        for r in reviewed:
            lost = {m.move_number: m for m in r.mistakes.mistakes}
            lines.append(f"\n## Game {r.game.game_id}: {r.game.black} vs {r.game.white}, {r.game.board_size}x{r.game.board_size}")
            for e in r.explanations.explanations:
                m = lost[e.move_number]
                lines.append(
                    f"- Move {e.move_number} ({m.severity.value}, {m.points_lost:.1f} points; "
                    f"themes: {', '.join(t.value for t in e.themes)}): {e.what_went_wrong} "
                    f"Principle: {e.principle}"
                )
        draft = self.llm.generate(SYSTEM, [Part("text/plain", "\n".join(lines))], PlanDraft)
        return StudyPlan(
            produced_by=self.produced_by,
            games=[r.game.game_id for r in reviewed],
            tallies=tallies,
            overview=draft.overview,
            study_items=draft.study_items,
        )


def tally(reviewed: list[ReviewedGame]) -> list[ThemeTally]:
    """Credits each mistake's points to its first (most important) theme and counts every theme it names."""
    counts: dict = defaultdict(int)
    points: dict = defaultdict(float)
    games: dict = defaultdict(set)
    for r in reviewed:
        lost = {m.move_number: m.points_lost for m in r.mistakes.mistakes}
        for e in r.explanations.explanations:
            for i, theme in enumerate(e.themes):
                counts[theme] += 1
                games[theme].add(r.game.game_id)
                if i == 0:
                    points[theme] += lost[e.move_number]
    return sorted(
        (ThemeTally(theme=t, count=counts[t], points_lost=round(points[t], 1), games=sorted(games[t])) for t in counts),
        key=lambda t: (t.points_lost, t.count),
        reverse=True,
    )
