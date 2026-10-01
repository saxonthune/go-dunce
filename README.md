# go-dunce

Reviews your Go games. It downloads games from [OGS](https://online-go.com),
finds your costliest moves with [KataGo](https://github.com/lightvector/KataGo),
has an LLM explain each one in plain language, and writes a study plan based on
the mistakes that recur across games. Try this example prompt:

> Read my game at https://online-go.com/game/12345678. Was the bottom group
> alive after move 44?

KataGo decides which moves were mistakes and what should have been played. The
LLM only explains the engine's findings and groups them into themes, because
LLMs misread Go positions when they work from the board alone.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
scripts/install-katago.sh          # OpenCL build; BACKEND=eigenavx2 for CPU only
```

The default LLM backend runs the `claude` CLI, so a Claude subscription is
enough. To use the Anthropic API instead, pass `--llm anthropic-api` and set
`ANTHROPIC_API_KEY`.

## Use

```sh
.venv/bin/go-dunce run https://online-go.com/review/<id> https://online-go.com/game/<id>
.venv/bin/go-dunce run --all                  # every game already downloaded
.venv/bin/go-dunce run --all --until select   # engine work only, no LLM calls
```

For a review, the review's owner is taken to be the learner. For a game, pass
`--player <OGS username>`; without it, both sides are reviewed.

Results go to `output/report.md` (the study plan) and `output/<game>/review.md`
(each game's mistakes with boards and explanations).

Three more commands support reviewing games in conversation with an agent:

- `go-dunce inspect <game> --boards 12,29` prints each move's points lost and
  the engine's choice, and draws the board after the listed moves.
- `go-dunce comment <game> <draft.json>` stores an agent's commentary on a game
  (`GameCommentary` in the contracts).
- `go-dunce history` prints all stored commentary, oldest game first, so a new
  agent can see where the learner is. See `AGENTS.md`.

## Steps and contracts

Each step reads the documents before it and writes one JSON document. The
shapes are pydantic models in `src/go_dunce/contracts.py`; the interfaces are
in `src/go_dunce/stages/__init__.py`.

| Step | Default implementation | Writes |
| --- | --- | --- |
| fetch | `OgsFetcher` | `input/<game>.source.json` (`SourceGame`), plus the SGF and raw OGS JSON |
| parse | `SgfParser` | `output/<game>/game.json` (`GameRecord`) |
| analyze | `KataGoAnalyzer` | `output/<game>/analysis.json` (`GameAnalysis`) |
| select | `ThresholdSelector` | `output/<game>/mistakes.json` (`MistakeSet`) |
| render | `AsciiRenderer` | `output/<game>/renders.json` (`RenderSet`) |
| explain | `CoachExplainer` | `output/<game>/explanations.json` (`ExplanationSet`), and `explain.prompt.md` |
| summarize | `CoachSummarizer` | `output/study-plan.json` (`StudyPlan`) |

Every document records `produced_by`: the implementation and settings that
wrote it. On each run, a step whose document is missing, or whose
`produced_by` differs from the configured step, is redone, along with every
step after it. Everything else is read from disk. `--force` redoes all steps.

Points use `x` (column from the left) and `y` (row from the top), both from 0.
Engine scores and winrates are always from Black's side.

### Swapping a step

Write a class that satisfies the step's protocol and register it in
`src/go_dunce/cli.py` (`RENDERERS`, `EXPLAINERS`, `SUMMARIZERS`). For example,
an image renderer would return `RenderedPosition`s with
`media_type="image/png"` and base64 `content`. The `anthropic-api` backend
already sends image parts to the model; the `claude-cli` backend accepts text
only.

The explainer's themes come from the fixed `Theme` list in the contracts, so
the summary step can count them across games.

## Layout

`input/`, `output/`, and `engines/` are gitignored. Downloaded games stay in
`input/` so they remain available if they leave OGS.

## License

[GNU Affero General Public License v3.0](LICENSE) or later.
