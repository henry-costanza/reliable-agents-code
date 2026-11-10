# Reliable Agents: the code

This is the companion code for *Reliable Agents* by Henry Costanza: the small `agentkit`
library every chapter builds on, each chapter's examples with their tests,
and the model responses they were recorded with. The book's text is sold
separately and is not in this repository.

## Run everything offline

You need Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

```text
git clone https://github.com/henry-costanza/reliable-agents-code
cd reliable-agents-code
uv sync
uv run pytest
```

Every model call in the examples replays a recorded response from
`fixtures/cassettes/`, so this needs no API key and costs nothing. The
results are the same on every machine and every run.

## Chapters

| # | Chapter | Examples |
| --- | --- | --- |
| 1 | The agent loop | `examples/01_agent_loop/` |
| 2 | Why context is the bottleneck | `examples/02_context/` |
| 3 | The context budget | `examples/03_budget/` |
| 4 | Instructions and project memory files | `examples/04_instructions/` |
| 5 | Tools and MCP | `examples/05_tools/` |
| 6 | Retrieval | `examples/06_retrieval/` |
| 7 | Memory | `examples/07_memory/` |
| 8 | Compaction, subagents and handoffs | `examples/08_compaction/` |
| 9 | A catalog of agent failures | `examples/09_failure_catalog/` |
| 10 | Verification | `examples/10_verification/` |
| 11 | Evaluation | `examples/11_evaluation/` |
| 12 | Deterministic guardrails | `examples/12_guardrails/` |
| 13 | Security | `examples/13_security/` |
| 14 | Observability and cost | `examples/14_observability/` |
| 15 | Multi-agent patterns | `examples/15_multi_agent/` |
| 16 | Capstone: shipping Brindle's desk | `examples/16_capstone/` |

Each chapter ends with an exercise. Its commands work from the root of this
repository, for example:

```text
uv run pytest examples/01_agent_loop
```

## Calling the model yourself

Live calls are optional and cost money. Copy `.env.example` to `.env`, add
your Anthropic API key, and set `AGENTKIT_MODE`:

```text
AGENTKIT_MODE=replay   default; offline, recorded responses
AGENTKIT_MODE=live     calls the model and records nothing
AGENTKIT_MODE=record   calls the model and overwrites the recordings
```

A live run will not match the recordings exactly: models answer differently
from run to run, which is why the book's tests replay recordings.

## Versions

agentkit 0.3.0. Python dependencies are pinned in
`pyproject.toml` to the versions the book was tested with.

## Licence

The code is released under the MIT licence; see `LICENSE`. The recorded
model responses in `fixtures/` may be used under the same terms.
