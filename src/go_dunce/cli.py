from __future__ import annotations

import argparse
from pathlib import Path

from . import commentary
from .inspect_game import inspect
from .llm import BACKENDS
from .pipeline import Runner, Step, Steps, Workspace
from .stages.analyze_katago import KataGoAnalyzer
from .stages.explain_coach import CoachExplainer
from .stages.fetch_ogs import OgsFetcher
from .stages.parse_sgf import SgfParser
from .stages.render_ascii import AsciiRenderer
from .stages.select_threshold import ThresholdSelector
from .stages.summarize_coach import CoachSummarizer

ROOT = Path(__file__).resolve().parents[2]

RENDERERS = {"ascii": AsciiRenderer}
EXPLAINERS = {"coach": CoachExplainer}
SUMMARIZERS = {"coach": CoachSummarizer}


def main() -> None:
    parser = argparse.ArgumentParser(prog="go-dunce", description="Review Go games with KataGo and an LLM.")
    parser.add_argument("--input-dir", type=Path, default=ROOT / "input")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    parser.add_argument("--engine-dir", type=Path, default=ROOT / "engines")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run the pipeline on games")
    run.add_argument("games", nargs="*", help="OGS game or review URLs, or game:<id> / review:<id>")
    run.add_argument("--all", action="store_true", help="also include every game already in the input directory")
    run.add_argument("--player", help="your OGS username; defaults to the review owner")
    run.add_argument("--until", choices=[s.value for s in Step], default=Step.SUMMARIZE.value, help="last step to run")
    run.add_argument("--force", action="store_true", help="redo every step even if its output is current")
    run.add_argument("--visits", type=int, default=400, help="KataGo search visits per position")
    run.add_argument("--max-mistakes", type=int, default=6, help="mistakes kept per game")
    run.add_argument("--renderer", choices=RENDERERS, default="ascii")
    run.add_argument("--explainer", choices=EXPLAINERS, default="coach")
    run.add_argument("--summarizer", choices=SUMMARIZERS, default="coach")
    run.add_argument("--llm", choices=BACKENDS, default="claude-cli")
    run.add_argument("--model", help="model for the LLM backend")

    look = commands.add_parser("inspect", help="print an analyzed game's move table and boards")
    look.add_argument("game_id", help="e.g. ogs-91159108")
    look.add_argument("--boards", default="", help="comma-separated move counts to draw the board after, e.g. 8,16,29")

    comment = commands.add_parser("comment", help="store an agent's commentary on an analyzed game")
    comment.add_argument("game_id")
    comment.add_argument("draft", type=Path, help="JSON file matching GameCommentary; game_id and written_on may be left out")

    commands.add_parser("history", help="print every stored commentary, oldest game first")

    args = parser.parse_args()
    if args.command == "run":
        _run(parser, args)
    elif args.command == "inspect":
        boards = [int(n) for n in args.boards.split(",") if n.strip()]
        print(inspect(args.output_dir, args.game_id, boards))
    elif args.command == "comment":
        print(f"wrote {commentary.save(args.output_dir, args.game_id, args.draft)}")
    elif args.command == "history":
        print(commentary.history_markdown(commentary.load_all(args.output_dir)))


def _run(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    refs = list(args.games)
    if args.all:
        refs += [f"game:{p.name.removeprefix('ogs-').removesuffix('.source.json')}" for p in sorted(args.input_dir.glob("ogs-*.source.json"))]
    refs = list(dict.fromkeys(refs))
    if not refs:
        parser.error("name at least one game, or pass --all")

    until = Step(args.until)
    needs_llm = list(Step).index(until) >= list(Step).index(Step.EXPLAIN)
    llm = BACKENDS[args.llm](args.model) if needs_llm else None
    args.input_dir.mkdir(exist_ok=True)
    args.output_dir.mkdir(exist_ok=True)

    steps = Steps(
        fetcher=OgsFetcher(args.input_dir),
        parser=SgfParser(args.input_dir, args.player),
        analyzer=KataGoAnalyzer(args.engine_dir, args.visits),
        selector=ThresholdSelector(args.max_mistakes),
        renderer=RENDERERS[args.renderer](),
        explainer=EXPLAINERS[args.explainer](llm) if llm else None,
        summarizer=SUMMARIZERS[args.summarizer](llm) if llm else None,
    )
    Runner(steps, Workspace(args.input_dir, args.output_dir), until, args.force).run(refs)


if __name__ == "__main__":
    main()
