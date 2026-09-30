"""Plain-text views of an analyzed game, for an agent or person reviewing it."""

from __future__ import annotations

from pathlib import Path

from .board import Board
from .contracts import Color, GameAnalysis, GameRecord, Point
from .coords import COLUMNS, line, to_gtp

STONE = {Color.BLACK: "X", Color.WHITE: "O"}
SHORT_OF_LIBERTIES = 2


def move_table(game: GameRecord, analysis: GameAnalysis) -> str:
    size = game.board_size
    rows = [f"{game.black} (Black) vs {game.white} (White), result {game.result}; learner: {game.player.word if game.player else 'unknown'}",
            "move  played  points lost  Black lead after  engine's choice and line"]
    for number, move in enumerate(game.moves, start=1):
        before, after = analysis.positions[number - 1], analysis.positions[number]
        sign = 1 if move.color is Color.BLACK else -1
        lost = sign * (before.score_lead - after.score_lead)
        best = before.candidates[0] if before.candidates else None
        choice = f"{to_gtp(best.point, size)}: {line(best.pv[:7], size)}" if best else "-"
        rows.append(f"{number:>4}  {move.color.value} {to_gtp(move.point, size):<5} {lost:>11.1f}  {after.score_lead:>+16.1f}  {choice}")
    return "\n".join(rows)


def board_view(game: GameRecord, moves_played: int) -> str:
    size = game.board_size
    board = Board.after(game, moves_played)
    header = "   " + " ".join(COLUMNS[:size])
    rows = [f"after move {moves_played} (X = Black, O = White)", header]
    for y in range(size):
        cells = " ".join(STONE.get(board.at(x, y), ".") for x in range(size))
        rows.append(f"{size - y:>2} {cells} {size - y}")
    rows.append(header)

    seen: set[tuple[int, int]] = set()
    for (x, y), color in sorted(board.stones.items()):
        if (x, y) in seen:
            continue
        stones, liberties = board.group(x, y)
        seen |= stones
        if len(liberties) <= SHORT_OF_LIBERTIES:
            names = ", ".join(sorted(to_gtp(Point(x=a, y=b), size) for a, b in stones))
            libs = ", ".join(sorted(to_gtp(Point(x=a, y=b), size) for a, b in liberties))
            rows.append(f"{color.word} chain {names}: liberties {libs}")
    return "\n".join(rows)


def inspect(output_dir: Path, game_id: str, boards: list[int]) -> str:
    game_dir = output_dir / game_id
    game = GameRecord.model_validate_json((game_dir / "game.json").read_text())
    analysis = GameAnalysis.model_validate_json((game_dir / "analysis.json").read_text())
    parts = [move_table(game, analysis)] + [board_view(game, n) for n in boards]
    return "\n\n".join(parts)
