from __future__ import annotations

from typing import TYPE_CHECKING

from .contracts import RenderSet, StudyPlan
from .coords import to_gtp

if TYPE_CHECKING:
    from .stages import ReviewedGame


def game_review_markdown(r: ReviewedGame, renders: RenderSet | None = None) -> str:
    game = r.game
    size = game.board_size
    boards = {p.move_number: p for p in renders.positions} if renders else {}
    explained = {e.move_number: e for e in r.explanations.explanations}
    out = [
        f"# {game.black} (Black) vs {game.white} (White)",
        "",
        f"{size}x{size}, komi {game.komi}, result {game.result or 'unknown'}. [Game on OGS]({game.source_url})",
        "",
    ]
    for m in r.mistakes.mistakes:
        e = explained.get(m.move_number)
        best = m.better[0].point if m.better else None
        out += [
            f"## Move {m.move_number}: {m.color.word} {to_gtp(m.played, size)} ({m.severity.value}, -{m.points_lost:.1f} points)",
            "",
            f"Engine preferred **{to_gtp(best, size)}**.",
            "",
        ]
        board = boards.get(m.move_number)
        if board is not None and board.media_type == "text/plain":
            out += ["```", board.content, "```", ""]
        if e is not None:
            out += [
                f"*Themes: {', '.join(t.value for t in e.themes)}*",
                "",
                f"**What went wrong.** {e.what_went_wrong}",
                "",
                f"**Better idea.** {e.better_idea}",
                "",
                f"**Principle.** {e.principle}",
                "",
            ]
    return "\n".join(out)


def study_plan_markdown(plan: StudyPlan, reviewed: list[ReviewedGame]) -> str:
    out = ["# Study plan", "", plan.overview, "", "## What to study", ""]
    for i, item in enumerate(plan.study_items, start=1):
        out += [f"{i}. **{item.topic}.** {item.why} *Practice:* {item.practice}", ""]
    out += ["## Mistake themes", "", "| Theme | Mistakes | Points lost where it was the main theme |", "| --- | --- | --- |"]
    out += [f"| {t.theme.value} | {t.count} | {t.points_lost:.1f} |" for t in plan.tallies]
    out += ["", "## Games", ""]
    out += [f"- [{r.game.game_id}]({r.game.game_id}/review.md): {r.game.black} vs {r.game.white}" for r in reviewed]
    return "\n".join(out) + "\n"
