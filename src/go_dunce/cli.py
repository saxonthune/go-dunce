from __future__ import annotations

import argparse
from pathlib import Path

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
    parser.add_argument("games", nargs="*", help="OGS game or review URLs, or game:<id> / review:<id>")
    parser.add_argument("--all", action="store_true", help="also include every game already in the input directory")
    parser.add_argument("--player", help="your OGS username; defaults to the review owner")
    parser.add_argument("--until", choices=[s.value for s in Step], default=Step.SUMMARIZE.value, help="last step to run")
    parser.add_argument("--force", action="store_true", help="redo every step even if its output is current")
    parser.add_argument("--visits", type=int, default=400, help="KataGo search visits per position")
    parser.add_argument("--max-mistakes", type=int, default=6, help="mistakes kept per game")
    parser.add_argument("--renderer", choices=RENDERERS, default="ascii")
    parser.add_argument("--explainer", choices=EXPLAINERS, default="coach")
    parser.add_argument("--summarizer", choices=SUMMARIZERS, default="coach")
    parser.add_argument("--llm", choices=BACKENDS, default="claude-cli")
    parser.add_argument("--model", help="model for the LLM backend")
    parser.add_argument("--input-dir", type=Path, default=ROOT / "input")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    parser.add_argument("--engine-dir", type=Path, default=ROOT / "engines")
    args = parser.parse_args()

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
