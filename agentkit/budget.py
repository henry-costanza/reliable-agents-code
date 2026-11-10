"""Token and cost budgets for a run, and the prices that turn tokens into money.

`run_agent(..., budget=Budget(...))` checks the budget after every step and
stops the run, with `RunResult.hit_budget`, after the step that crosses it.
Checking after a step means a run can overshoot by at most one model call;
counting the next request first would catch that call too, at the price of
an extra request per step.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentkit.messages import Usage

__all__ = ["OPUS_5_5", "Budget", "Prices"]


@dataclass(frozen=True)
class Prices:
    """US dollars per million tokens. Cache prices default to the input price."""

    input: float
    output: float
    cache_read: float | None = None
    cache_write: float | None = None

    def cost(self, usage: Usage) -> float:
        read = self.input if self.cache_read is None else self.cache_read
        write = self.input if self.cache_write is None else self.cache_write
        dollars = (
            usage.input_tokens * self.input
            + usage.output_tokens * self.output
            + usage.cache_read_input_tokens * read
            + usage.cache_creation_input_tokens * write
        )
        return dollars / 1_000_000


# Claude Opus 5.5 on Anthropic's pricing page, 30 October 2026: base input,
# output, cache hits and 5-minute cache writes. Prices change; check them.
OPUS_5_5 = Prices(input=4.0, output=20.0, cache_read=0.20, cache_write=5.0)


# --8<-- [start:budget]
@dataclass(frozen=True)
class Budget:
    """Limits for one run; `exceeded` says why usage is over."""

    max_input_tokens: int | None = None
    max_cost: float | None = None  # US dollars; needs prices
    prices: Prices | None = None

    def exceeded(self, usage: Usage) -> str | None:
        tokens = (usage.input_tokens + usage.cache_read_input_tokens
                  + usage.cache_creation_input_tokens)
        limit = self.max_input_tokens
        if limit is not None and tokens > limit:
            return f"{tokens:,} input tokens; the budget is {limit:,}"
        if self.max_cost is not None:
            cost = self.prices.cost(usage)
            if cost > self.max_cost:
                return (f"${cost:.2f} spent; "
                        f"the budget is ${self.max_cost:.2f}")
        return None
# --8<-- [end:budget]

    def __post_init__(self) -> None:
        if self.max_cost is not None and self.prices is None:
            raise ValueError("a cost budget needs prices")
