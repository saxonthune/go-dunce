from __future__ import annotations

from pathlib import Path

from sgfmill import sgf

from ..contracts import Color, GameRecord, Move, Point, SourceGame


class SgfParser:
    """Reads the main line of an SGF file. Variations are ignored."""

    def __init__(self, input_dir: Path, player: str | None) -> None:
        self.input_dir = input_dir
        self.player = player
        self.produced_by = f"sgfmill/1 player={player or '-'}"

    def parse(self, source: SourceGame) -> GameRecord:
        game = sgf.Sgf_game.from_bytes((self.input_dir / source.sgf_path).read_bytes())
        size = game.get_size()
        root = game.get_root()

        def point(rc: tuple[int, int]) -> Point:
            row, col = rc  # sgfmill counts rows from the bottom
            return Point(x=col, y=size - 1 - row)

        black_setup, white_setup, _ = root.get_setup_stones()
        moves = []
        for node in game.get_main_sequence()[1:]:
            colour, rc = node.get_move()
            if colour is not None:
                moves.append(Move(color=Color(colour.upper()), point=None if rc is None else point(rc)))

        black = _prop(root, "PB") or "Black"
        white = _prop(root, "PW") or "White"
        learner = self.player or source.owner
        player = Color.BLACK if learner == black else Color.WHITE if learner == white else None

        return GameRecord(
            produced_by=self.produced_by,
            game_id=source.game_id,
            source_url=source.source_url,
            board_size=size,
            komi=game.get_komi(),
            rules=_prop(root, "RU") or "chinese",
            black=black,
            white=white,
            result=_prop(root, "RE"),
            setup_black=[point(rc) for rc in black_setup],
            setup_white=[point(rc) for rc in white_setup],
            moves=moves,
            player=player,
        )


def _prop(node, name: str) -> str | None:
    return node.get(name) if node.has_property(name) else None
