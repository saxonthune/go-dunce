from __future__ import annotations

from ..board import Board
from ..contracts import Color, GameRecord, Mistake, MistakeSet, RenderedPosition, RenderSet
from ..coords import COLUMNS

STONE = {Color.BLACK: "X", Color.WHITE: "O"}
PLAYED = "*"
BETTER_LABELS = "ABC"
LEGEND = (
    "X = Black stone, O = White stone, . = empty point. "
    f"{PLAYED} = the move that was played (the mistake). "
    f"{', '.join(BETTER_LABELS)} = the engine's preferred moves, best first. "
    "Columns skip the letter I; rows count up from the bottom. "
    "The board shows the position just before the mistake."
)


class AsciiRenderer:
    produced_by = "ascii/1"

    def render(self, game: GameRecord, mistakes: MistakeSet) -> RenderSet:
        return RenderSet(
            produced_by=self.produced_by,
            game_id=game.game_id,
            positions=[self._render_one(game, m) for m in mistakes.mistakes],
        )

    def _render_one(self, game: GameRecord, mistake: Mistake) -> RenderedPosition:
        size = game.board_size
        board = Board.after(game, mistake.move_number - 1)
        marks: dict[tuple[int, int], str] = {}
        for label, candidate in zip(BETTER_LABELS, mistake.better):
            if candidate.point is not None:
                marks[(candidate.point.x, candidate.point.y)] = label
        if mistake.played is not None:
            marks[(mistake.played.x, mistake.played.y)] = PLAYED

        header = "   " + " ".join(COLUMNS[:size])
        rows = [header]
        for y in range(size):
            cells = []
            for x in range(size):
                stone = board.at(x, y)
                cells.append(STONE[stone] if stone else marks.get((x, y), "."))
            number = size - y
            rows.append(f"{number:>2} {' '.join(cells)} {number}")
        rows.append(header)
        return RenderedPosition(
            move_number=mistake.move_number, media_type="text/plain", content="\n".join(rows), legend=LEGEND
        )
