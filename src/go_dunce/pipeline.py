from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, TypeVar

from .contracts import (
    ExplanationSet,
    GameAnalysis,
    GameRecord,
    MistakeSet,
    RenderSet,
    SourceGame,
    StepOutput,
    StudyPlan,
)
from .report import game_review_markdown, study_plan_markdown
from .stages import Analyzer, Explainer, Fetcher, Parser, Renderer, ReviewedGame, Selector, Summarizer

D = TypeVar("D", bound=StepOutput)


class Step(str, Enum):
    FETCH = "fetch"
    PARSE = "parse"
    ANALYZE = "analyze"
    SELECT = "select"
    RENDER = "render"
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"


ORDER = list(Step)


@dataclass
class Steps:
    fetcher: Fetcher
    parser: Parser
    analyzer: Analyzer
    selector: Selector
    renderer: Renderer
    explainer: Explainer | None
    summarizer: Summarizer | None


@dataclass
class Workspace:
    input_dir: Path
    output_dir: Path

    def game_dir(self, game_id: str) -> Path:
        path = self.output_dir / game_id
        path.mkdir(parents=True, exist_ok=True)
        return path


class Runner:
    def __init__(self, steps: Steps, workspace: Workspace, until: Step, force: bool, log: Callable[[str], None] = print):
        self.steps = steps
        self.ws = workspace
        self.until = until
        self.force = force
        self.log = log

    def run(self, refs: list[str]) -> StudyPlan | None:
        reviewed, any_redone = [], False
        for ref in refs:
            result, redone = self.run_game(ref)
            any_redone |= redone
            if result is not None:
                reviewed.append(result)
        if self.until is not Step.SUMMARIZE or not reviewed or self.steps.summarizer is None:
            return None

        path = self.ws.output_dir / "study-plan.json"
        games = [r.game.game_id for r in reviewed]
        plan = _load(path, StudyPlan)
        if self.force or any_redone or plan is None or plan.produced_by != self.steps.summarizer.produced_by or plan.games != games:
            self.log(f"summarize: {len(reviewed)} games with {self.steps.summarizer.produced_by}")
            plan = self.steps.summarizer.summarize(reviewed)
            path.write_text(plan.model_dump_json(indent=2))
        report = self.ws.output_dir / "report.md"
        report.write_text(study_plan_markdown(plan, reviewed))
        self.log(f"wrote {report}")
        return plan

    def run_game(self, ref: str) -> tuple[ReviewedGame | None, bool]:
        """Runs the per-game steps. Returns the reviewed game (when explain ran) and whether any step was redone."""
        source: SourceGame = self.steps.fetcher.fetch(ref)
        out = self.ws.game_dir(source.game_id)
        stale = self.force

        def step(name: Step, file: str, kind: type[D], produced_by: str, compute: Callable[[], D]) -> D | None:
            nonlocal stale
            if ORDER.index(name) > ORDER.index(self.until):
                return None
            path = out / file
            doc = None if stale else _load(path, kind)
            if doc is not None and doc.produced_by == produced_by:
                return doc
            self.log(f"{source.game_id} {name.value}: {produced_by}")
            doc = compute()
            path.write_text(doc.model_dump_json(indent=2))
            stale = True
            return doc

        s = self.steps
        game = step(Step.PARSE, "game.json", GameRecord, s.parser.produced_by, lambda: s.parser.parse(source))
        if game is None:
            return None, stale
        analysis = step(Step.ANALYZE, "analysis.json", GameAnalysis, s.analyzer.produced_by, lambda: s.analyzer.analyze(game))
        if analysis is None:
            return None, stale
        mistakes = step(Step.SELECT, "mistakes.json", MistakeSet, s.selector.produced_by, lambda: s.selector.select(game, analysis))
        if mistakes is None:
            return None, stale
        renders = step(Step.RENDER, "renders.json", RenderSet, s.renderer.produced_by, lambda: s.renderer.render(game, mistakes))
        if renders is None or s.explainer is None:
            return None, stale

        def explain() -> ExplanationSet:
            result = s.explainer.explain(game, mistakes, renders)
            prompt = getattr(s.explainer, "last_prompt", None)
            if prompt:
                (out / "explain.prompt.md").write_text("\n\n".join(p.content for p in prompt))
            return result

        explanations = step(Step.EXPLAIN, "explanations.json", ExplanationSet, s.explainer.produced_by, explain)
        if explanations is None:
            return None, stale
        reviewed = ReviewedGame(game=game, mistakes=mistakes, explanations=explanations)
        (out / "review.md").write_text(game_review_markdown(reviewed, renders))
        return reviewed, stale


def _load(path: Path, kind: type[D]) -> D | None:
    return kind.model_validate_json(path.read_text()) if path.exists() else None
