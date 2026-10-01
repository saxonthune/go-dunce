from pathlib import Path

import pytest

from go_dunce.board import Board, IllegalMove
from go_dunce.contracts import (
    Candidate,
    Color,
    GameAnalysis,
    GameRecord,
    Move,
    Point,
    PositionEval,
    RenderSet,
    Severity,
    SourceGame,
)
from go_dunce.coords import from_gtp, to_gtp
from go_dunce.pipeline import Runner, Step, Steps, Workspace
from go_dunce.stages.render_ascii import AsciiRenderer
from go_dunce.stages.select_threshold import ThresholdSelector


def mv(color: str, x: int, y: int) -> Move:
    return Move(color=Color(color), point=Point(x=x, y=y))


def record(moves: list[Move], player: Color | None = Color.BLACK) -> GameRecord:
    return GameRecord(
        produced_by="test", game_id="g1", source_url="-", board_size=9, komi=7.5, rules="chinese",
        black="me", white="bot", result=None, moves=moves, player=player,
    )


def position(n: int, lead: float) -> PositionEval:
    best = Candidate(point=Point(x=4, y=4), visits=100, winrate=0.5, score_lead=lead, pv=[Point(x=4, y=4)])
    return PositionEval(
        moves_played=n, to_play=Color.BLACK if n % 2 == 0 else Color.WHITE, winrate=0.5, score_lead=lead, candidates=[best]
    )


def test_gtp_coordinates_skip_i_and_count_rows_from_bottom():
    assert to_gtp(Point(x=8, y=0), 9) == "J9"
    assert from_gtp("J9", 9) == Point(x=8, y=0)
    assert to_gtp(None, 9) == "pass"


def test_capture_removes_stones_without_liberties():
    board = Board(9)
    for m in [mv("W", 0, 0), mv("B", 1, 0), mv("B", 0, 1)]:
        captured = board.play(m)
    assert captured == [(0, 0)]
    assert board.at(0, 0) is None


def test_suicide_is_illegal():
    board = Board(9)
    board.play(mv("W", 1, 0))
    board.play(mv("W", 0, 1))
    with pytest.raises(IllegalMove):
        board.play(mv("B", 0, 0))


def test_selector_measures_loss_from_the_movers_side():
    game = record([mv("B", 2, 2), mv("W", 6, 6), mv("B", 0, 0)])
    # Black's lead: 5 -> 4 (Black loses 1), 4 -> 4, 4 -> -3 (Black loses 7).
    analysis = GameAnalysis(produced_by="test", game_id="g1", positions=[position(0, 5), position(1, 4), position(2, 4), position(3, -3)])
    mistakes = ThresholdSelector(max_mistakes=5).select(game, analysis).mistakes
    assert [(m.move_number, m.points_lost, m.severity) for m in mistakes] == [(3, 7.0, Severity.BLUNDER)]


def test_selector_reviews_both_sides_when_player_unknown():
    game = record([mv("B", 2, 2), mv("W", 6, 6)], player=None)
    # White's move raises Black's lead by 4, so White lost 4.
    analysis = GameAnalysis(produced_by="test", game_id="g1", positions=[position(0, 0), position(1, 0), position(2, 4)])
    mistakes = ThresholdSelector(max_mistakes=5).select(game, analysis).mistakes
    assert [(m.move_number, m.color) for m in mistakes] == [(2, Color.WHITE)]


def test_ascii_board_shows_position_before_the_mistake():
    game = record([mv("B", 2, 2), mv("W", 6, 6), mv("B", 0, 0)])
    analysis = GameAnalysis(produced_by="test", game_id="g1", positions=[position(0, 5), position(1, 5), position(2, 5), position(3, -3)])
    mistakes = ThresholdSelector(max_mistakes=5).select(game, analysis)
    board = AsciiRenderer().render(game, mistakes).positions[0].content.splitlines()
    assert board[1].split()[1] == "*"  # A9: the mistake, not yet played
    assert board[3].split()[3] == "X"  # C7: Black's first move
    assert board[5].split()[5] == "A"  # E5: the engine's choice


class FakeStep:
    def __init__(self, produced_by: str, result):
        self.produced_by = produced_by
        self.result = result
        self.calls = 0

    def __call__(self, *args):
        self.calls += 1
        return self.result


def fake_steps(renderer_name: str) -> tuple[Steps, dict[str, FakeStep]]:
    game = record([mv("B", 2, 2)]).model_copy(update={"produced_by": "p"})
    analysis = GameAnalysis(produced_by="a", game_id="g1", positions=[position(0, 0), position(1, -5)])
    source = SourceGame(produced_by="f", game_id="g1", source_url="-", sgf_path="g1.sgf", owner=None)
    fakes = {
        "parse": FakeStep("p", game),
        "analyze": FakeStep("a", analysis),
        "render": FakeStep(renderer_name, RenderSet(produced_by=renderer_name, game_id="g1", positions=[])),
    }
    selector = ThresholdSelector(max_mistakes=3)

    class S:
        pass

    fetcher, parser, analyzer, renderer = S(), S(), S(), S()
    fetcher.produced_by, fetcher.fetch = "f", lambda ref: source
    parser.produced_by, parser.parse = "p", fakes["parse"]
    analyzer.produced_by, analyzer.analyze = "a", fakes["analyze"]
    renderer.produced_by, renderer.render = renderer_name, fakes["render"]
    return Steps(fetcher, parser, analyzer, selector, renderer, None, None), fakes


def test_runner_reuses_current_outputs_and_redoes_a_swapped_step(tmp_path: Path):
    ws = Workspace(tmp_path / "in", tmp_path / "out")
    steps, first = fake_steps("ascii/1")
    Runner(steps, ws, Step.RENDER, force=False, log=lambda _: None).run(["g1"])
    assert [f.calls for f in first.values()] == [1, 1, 1]

    steps, second = fake_steps("ascii/2")
    Runner(steps, ws, Step.RENDER, force=False, log=lambda _: None).run(["g1"])
    assert [second[k].calls for k in ("parse", "analyze", "render")] == [0, 0, 1]


def test_commentary_round_trip_orders_games_oldest_first(tmp_path: Path):
    import json

    from go_dunce import commentary

    for game_id in ("ogs-12345678", "ogs-9876543"):
        (tmp_path / game_id).mkdir()
        draft = tmp_path / f"{game_id}.draft.json"
        draft.write_text(json.dumps({
            "author": "test", "summary": "s", "player_level": "l", "themes": ["shape"],
            "key_moments": [{"move_number": 3, "note": "n"}],
        }))
        commentary.save(tmp_path, game_id, draft)

    assert [c.game_id for c in commentary.load_all(tmp_path)] == ["ogs-9876543", "ogs-12345678"]


def test_commentary_requires_an_analyzed_game(tmp_path: Path):
    from go_dunce import commentary

    draft = tmp_path / "d.json"
    draft.write_text('{"author": "t", "summary": "s", "player_level": "l", "themes": [], "key_moments": []}')
    with pytest.raises(FileNotFoundError):
        commentary.save(tmp_path, "ogs-1", draft)
