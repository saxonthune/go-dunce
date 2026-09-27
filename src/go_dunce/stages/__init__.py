"""The interfaces each pipeline step implements.

`produced_by` must name the implementation and every setting that changes its
output, because the runner compares it to decide whether to redo the step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..contracts import (
    ExplanationSet,
    GameAnalysis,
    GameRecord,
    MistakeSet,
    RenderSet,
    SourceGame,
    StudyPlan,
)


class Fetcher(Protocol):
    produced_by: str

    def fetch(self, ref: str) -> SourceGame: ...


class Parser(Protocol):
    produced_by: str

    def parse(self, source: SourceGame) -> GameRecord: ...


class Analyzer(Protocol):
    produced_by: str

    def analyze(self, game: GameRecord) -> GameAnalysis: ...


class Selector(Protocol):
    produced_by: str

    def select(self, game: GameRecord, analysis: GameAnalysis) -> MistakeSet: ...


class Renderer(Protocol):
    produced_by: str

    def render(self, game: GameRecord, mistakes: MistakeSet) -> RenderSet: ...


class Explainer(Protocol):
    produced_by: str

    def explain(self, game: GameRecord, mistakes: MistakeSet, renders: RenderSet) -> ExplanationSet: ...


@dataclass
class ReviewedGame:
    game: GameRecord
    mistakes: MistakeSet
    explanations: ExplanationSet


class Summarizer(Protocol):
    produced_by: str

    def summarize(self, reviewed: list[ReviewedGame]) -> StudyPlan: ...
