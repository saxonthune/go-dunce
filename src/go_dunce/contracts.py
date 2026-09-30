"""The data passed between pipeline steps.

Each step reads one or more of these documents and writes one. A step's
implementation can be replaced freely as long as it reads and writes these
shapes. Every document carries a `contract` tag; bump its version when the
shape changes incompatibly.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Color(str, Enum):
    BLACK = "B"
    WHITE = "W"

    @property
    def other(self) -> Color:
        return Color.WHITE if self is Color.BLACK else Color.BLACK

    @property
    def word(self) -> str:
        return "Black" if self is Color.BLACK else "White"


class StepOutput(Contract):
    produced_by: str = Field(
        description="The implementation and settings that wrote this document. "
        "The runner redoes a step when this differs from the configured step."
    )


class Point(Contract):
    """A board intersection. x counts columns from the left, y counts rows from the top, both from 0."""

    x: int
    y: int


class Move(Contract):
    color: Color
    point: Point | None = Field(description="None means pass.")


# --- fetch -> SourceGame ---------------------------------------------------


class SourceGame(StepOutput):
    contract: Literal["source-game/1"] = "source-game/1"
    game_id: str
    source_url: str
    sgf_path: str = Field(description="Relative to the input directory.")
    owner: str | None = Field(description="Account that owns the review, if the game came from one.")


# --- parse -> GameRecord ----------------------------------------------------


class GameRecord(StepOutput):
    contract: Literal["game-record/1"] = "game-record/1"
    game_id: str
    source_url: str
    board_size: int
    komi: float
    rules: str
    black: str
    white: str
    result: str | None
    setup_black: list[Point] = Field(default_factory=list, description="Handicap or setup stones.")
    setup_white: list[Point] = Field(default_factory=list)
    moves: list[Move]
    player: Color | None = Field(description="The side the learner played; None reviews both sides.")


# --- analyze -> GameAnalysis ------------------------------------------------


class Candidate(Contract):
    point: Point | None
    visits: int
    winrate: float = Field(description="Black's win probability after this move, 0..1.")
    score_lead: float = Field(description="Black's expected lead in points after this move.")
    pv: list[Point | None] = Field(description="The engine's expected continuation, starting with this move.")


class PositionEval(Contract):
    """The engine's view of the position after `moves_played` moves."""

    moves_played: int
    to_play: Color
    winrate: float = Field(description="Black's win probability, 0..1.")
    score_lead: float = Field(description="Black's expected lead in points.")
    candidates: list[Candidate] = Field(description="Best moves first.")


class GameAnalysis(StepOutput):
    contract: Literal["game-analysis/1"] = "game-analysis/1"
    game_id: str
    positions: list[PositionEval] = Field(description="One per position, from the empty board to the final move.")


# --- select -> MistakeSet ---------------------------------------------------


class Severity(str, Enum):
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


class Mistake(Contract):
    move_number: int = Field(description="1 for the first move of the game.")
    color: Color
    played: Point | None
    points_lost: float
    winrate_lost: float
    severity: Severity
    better: list[Candidate] = Field(description="The engine's preferred moves in the position before the mistake.")
    punishment: list[Point | None] = Field(description="The engine's expected continuation after the move played.")


class MistakeSet(StepOutput):
    contract: Literal["mistake-set/1"] = "mistake-set/1"
    game_id: str
    thresholds: dict[Severity, float] = Field(description="Minimum points lost for each severity.")
    mistakes: list[Mistake]


# --- render -> RenderSet ----------------------------------------------------


class RenderedPosition(Contract):
    move_number: int
    media_type: str = Field(description="How `content` is encoded, e.g. text/plain or image/png (base64).")
    content: str
    legend: str = Field(description="Plain-text key to the symbols or markings in `content`.")


class RenderSet(StepOutput):
    contract: Literal["render-set/1"] = "render-set/1"
    game_id: str
    positions: list[RenderedPosition]


# --- explain -> ExplanationSet ----------------------------------------------


class Theme(str, Enum):
    """The fixed set of mistake themes. The summary step counts these across games."""

    LIFE_AND_DEATH = "life_and_death"
    CAPTURING_RACE = "capturing_race"
    CUTTING_AND_CONNECTING = "cutting_and_connecting"
    SHAPE = "shape"
    OVERCONCENTRATION = "overconcentration"
    DIRECTION_OF_PLAY = "direction_of_play"
    OPENING_PRIORITIES = "opening_priorities"
    INVASION_AND_REDUCTION = "invasion_and_reduction"
    TOO_SLOW = "too_slow"
    OVERPLAY = "overplay"
    IGNORED_THREAT = "ignored_threat"
    MISSED_ATTACK = "missed_attack"
    ENDGAME_SIZE = "endgame_size"
    SENTE_AND_GOTE = "sente_and_gote"
    OTHER = "other"


class Explanation(Contract):
    move_number: int
    themes: list[Theme] = Field(description="One to three themes, most important first.")
    what_went_wrong: str
    better_idea: str
    principle: str = Field(description="The general lesson, stated so it applies beyond this position.")


class ExplanationSet(StepOutput):
    contract: Literal["explanation-set/1"] = "explanation-set/1"
    game_id: str
    explanations: list[Explanation]


# --- summarize -> StudyPlan -------------------------------------------------


class ThemeTally(Contract):
    theme: Theme
    count: int
    points_lost: float
    games: list[str]


class StudyItem(Contract):
    topic: str
    why: str = Field(description="Which of the learner's mistakes this addresses.")
    practice: str = Field(description="A concrete exercise or resource type.")


class StudyPlan(StepOutput):
    contract: Literal["study-plan/1"] = "study-plan/1"
    games: list[str]
    tallies: list[ThemeTally] = Field(description="Sorted by points lost, largest first.")
    overview: str
    study_items: list[StudyItem]


# --- commentary (written by an agent reviewing a game, not by the runner) ---


class KeyMoment(Contract):
    move_number: int
    note: str


class GameCommentary(Contract):
    contract: Literal["game-commentary/1"] = "game-commentary/1"
    game_id: str
    author: str = Field(description="The agent and model that wrote this, e.g. 'Claude Code (claude-opus-5-5)'.")
    written_on: date
    summary: str = Field(description="What decided the game, in a few sentences.")
    player_level: str = Field(
        description="What this game shows about the learner's current level, including change since earlier games."
    )
    themes: list[Theme] = Field(description="The learner's weaknesses shown in this game, most costly first.")
    key_moments: list[KeyMoment]
