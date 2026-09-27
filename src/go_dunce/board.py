from __future__ import annotations

from .contracts import Color, GameRecord, Move, Point


class IllegalMove(ValueError):
    pass


class Board:
    def __init__(self, size: int) -> None:
        self.size = size
        self.stones: dict[tuple[int, int], Color] = {}

    @classmethod
    def after(cls, game: GameRecord, moves_played: int) -> Board:
        board = cls(game.board_size)
        for p in game.setup_black:
            board.stones[(p.x, p.y)] = Color.BLACK
        for p in game.setup_white:
            board.stones[(p.x, p.y)] = Color.WHITE
        for move in game.moves[:moves_played]:
            board.play(move)
        return board

    def at(self, x: int, y: int) -> Color | None:
        return self.stones.get((x, y))

    def neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        candidates = [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
        return [(a, b) for a, b in candidates if 0 <= a < self.size and 0 <= b < self.size]

    def group(self, x: int, y: int) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
        """Return the stones connected to (x, y) and their liberties."""
        color = self.stones[(x, y)]
        stones, liberties, frontier = {(x, y)}, set(), [(x, y)]
        while frontier:
            for n in self.neighbors(*frontier.pop()):
                occupant = self.stones.get(n)
                if occupant is None:
                    liberties.add(n)
                elif occupant is color and n not in stones:
                    stones.add(n)
                    frontier.append(n)
        return stones, liberties

    def play(self, move: Move) -> list[tuple[int, int]]:
        """Place a stone and remove captured groups. Returns the captured points."""
        if move.point is None:
            return []
        here = (move.point.x, move.point.y)
        if here in self.stones:
            raise IllegalMove(f"{here} is occupied")
        self.stones[here] = move.color
        captured: list[tuple[int, int]] = []
        for n in self.neighbors(*here):
            if self.stones.get(n) is move.color.other:
                stones, liberties = self.group(*n)
                if not liberties:
                    captured.extend(stones)
                    for s in stones:
                        del self.stones[s]
        _, liberties = self.group(*here)
        if not liberties:
            del self.stones[here]
            raise IllegalMove(f"{here} is suicide")
        return captured

    def liberties_at(self, point: Point) -> int:
        return len(self.group(point.x, point.y)[1])
