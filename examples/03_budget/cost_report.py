"""Chapter 3: what each step of a run cost, and where its tokens came from."""

from agentkit import OPUS_5_5, Prices, RunResult


# --8<-- [start:attribute]
def attribute(
    result: RunResult, prices: Prices = OPUS_5_5
) -> list[dict]:
    """Per step: input tokens carried from the step before, tokens
    the step added, output tokens, and cost in dollars."""
    rows, carried = [], 0
    for step, usage in enumerate(result.step_usage, 1):
        rows.append({
            "step": step,
            "input": usage.input_tokens,
            "carried": min(carried, usage.input_tokens),
            "added": max(usage.input_tokens - carried, 0),
            "output": usage.output_tokens,
            "cost": round(prices.cost(usage), 4),
        })
        # The next request resends this request and its reply.
        carried = usage.input_tokens + usage.output_tokens
    return rows
# --8<-- [end:attribute]


def table(rows: list[dict]) -> str:
    lines = ["step   input  carried   added  output     cost"]
    for r in rows:
        lines.append(f"{r['step']:>4} {r['input']:>7,} {r['carried']:>8,} {r['added']:>7,} "
                     f"{r['output']:>7,} ${r['cost']:>7.4f}")
    total = sum(r["cost"] for r in rows)
    lines.append(f"{'':>38}${total:>7.4f}")
    return "\n".join(lines)
