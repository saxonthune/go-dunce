# Agent notes

This repository reviews a Go learner's games. Besides running the pipeline,
agents here review games with the learner in conversation.

## Before reviewing a game

Run `.venv/bin/go-dunce history`. It prints the commentary stored for every
game reviewed so far, oldest first: what decided each game, what it showed
about the learner's level, and the recurring themes. Use it to judge what the
learner already knows and which advice has already been given.

## Reviewing a game

1. `.venv/bin/go-dunce run game:<id> --player <OGS username> --until select`
   runs the engine steps without LLM calls. The learner's username is in any
   earlier `output/*/game.json` (the side named by `player`).
2. `.venv/bin/go-dunce inspect ogs-<id> --boards 12,29` prints every move with
   points lost and the engine's choice, then the board after each listed move,
   with every chain that has two liberties or fewer.
3. After discussing the game, store a commentary: write a JSON file matching
   `GameCommentary` in `src/go_dunce/contracts.py` (`game_id` and `written_on`
   may be left out), then run
   `.venv/bin/go-dunce comment ogs-<id> <draft.json>`. Storing again replaces
   the earlier commentary for that game.

Commentary lives in `output/<game>/commentary.json`, which is gitignored, so it
exists only on this machine.
