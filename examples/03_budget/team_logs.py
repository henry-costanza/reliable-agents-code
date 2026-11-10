"""Chapter 3: three of Brindle's team logs, and two ways to read them.

Each log is generated from a fixed seed, about 128,000 characters, so the
same code always gives the same logs and a cassette can store fingerprints.
"""

import random

LOGS = ("billing", "support", "sales")
QUESTION = (
    "Which of the logs billing, support and sales mentions "
    "Atlas Dental most often? Reply with the log name only."
)
SYSTEM = "You answer questions about Brindle's team logs. Use the tools."

CUSTOMERS = ("Atlas Dental", "Juniper Florists", "Halcyon Yoga", "Mosaic Tiles",
             "Tundra Outfitters", "Lantern Books")
THINGS = ("invoice template", "dunning emails", "tax settings",
          "payment reminders", "CSV export", "onboarding notes",
          "plan limits", "webhook settings")
VERBS = ("reviewed", "rewrote", "simplified", "moved", "documented", "paused")
WHEN = ("on Monday", "after the retro", "before the freeze", "last sprint",
        "this week", "after lunch")


def build_log(team: str, chars: int = 128_000) -> str:
    rng = random.Random(f"log-{team}")
    lines, total = [], 0
    while total < chars:
        line = (f"The {team} team {rng.choice(VERBS)} the {rng.choice(THINGS)} "
                f"for {rng.choice(CUSTOMERS)} {rng.choice(WHEN)}.")
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def mentions(team: str, customer: str = "Atlas Dental") -> int:
    return build_log(team).count(f"for {customer}")


def truth() -> str:
    """The log that mentions Atlas Dental most often."""
    return max(LOGS, key=mentions)
