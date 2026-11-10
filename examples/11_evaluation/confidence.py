"""Chapter 11: how far a pass rate can be trusted.

Exact arithmetic on the binomial distribution, with no library. Trials of one
task are treated as independent, which is an assumption.
"""

from math import comb


# --8<-- [start:lower]
def lowest_rate(passed: int, trials: int,
                level: float = 0.95) -> float:
    """The lowest true pass rate this score still fits."""
    if passed == 0:
        return 0.0

    def at_least(rate: float) -> float:
        return sum(comb(trials, k) * rate**k
                   * (1 - rate)**(trials - k)
                   for k in range(passed, trials + 1))
    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        if at_least(middle) < 1 - level:
            low = middle
        else:
            high = middle
    return low
# --8<-- [end:lower]


# --8<-- [start:worse]
def chance_of_drop(base: tuple[int, int],
                   new: tuple[int, int]) -> float:
    """Fisher's exact test, one-sided: could chance alone give this drop?"""
    base_pass, base_runs = base
    new_pass, new_runs = new
    passes = base_pass + new_pass
    runs = base_runs + new_runs

    def table(k: int) -> float:
        return (comb(new_runs, k) * comb(base_runs, passes - k)
                / comb(runs, passes))
    return sum(table(k) for k in range(max(0, passes - base_runs),
                                       new_pass + 1))
# --8<-- [end:worse]


# --8<-- [start:compare]
def compare(base: dict[str, tuple[int, int]],
            new: dict[str, tuple[int, int]]) -> dict[str, list[str]]:
    """Blocks are unlikely to be chance. Read the rest by hand."""
    found: dict[str, list[str]] = {"block": [], "read": []}
    for task, score in new.items():
        if score[0] / score[1] >= base[task][0] / base[task][1]:
            continue
        unlikely = chance_of_drop(base[task], score) < 0.05
        found["block" if unlikely else "read"].append(task)
    return found
# --8<-- [end:compare]
