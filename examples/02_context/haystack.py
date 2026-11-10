"""Chapter 2: Brindle's activity log, with one fact hidden in it.

The filler is built from a fixed seed, so the same arguments always give the
same document, and a cassette can store a fingerprint instead of the text.
It contains no digits: the only numbers in a document are the needle's and
the distractors', so an answer can be graded without guessing.
"""

import random
import re

# --8<-- [start:facts]
NEEDLE = "The refund approval code for Orion Bakery is 7341."
QUESTION = (
    "What is the refund approval code for Orion Bakery? "
    "Reply with just the number."
)
ANSWER = "7341"
DISTRACTORS = (
    "The refund approval code for Orin Bakery is 7314.",
    "The refund approval code for Oberon Bakery is 7431.",
    "The credit approval code for Orion Bakery is 3741.",
    "The refund approval code for Orion Bakeries is 1734.",
)
# --8<-- [end:facts]

# Where the distractors go when they are used. None coincides with a needle
# position the experiment tests.
DISTRACTOR_AT = (0.1, 0.4, 0.6, 0.9)

TEAMS = ("platform", "billing", "sales", "mobile", "data", "support", "security", "growth")
CUSTOMERS = ("Atlas Dental", "Juniper Florists", "Halcyon Yoga", "Mosaic Tiles",
             "Tundra Outfitters", "Lantern Books", "Quarry Coffee", "Willow Vets")
THINGS = ("invoice template", "dunning emails", "tax settings", "payment reminders",
          "CSV export", "onboarding notes", "plan limits", "receipt layout",
          "webhook settings", "help article")
VERBS = ("reviewed", "rewrote", "simplified", "moved", "documented", "paused", "renamed",
         "audited", "split", "merged")
WHEN = ("on Monday", "after the retro", "before the freeze", "last sprint", "this week",
        "during the offsite", "after lunch", "ahead of the tax deadline")
WHY = ("to cut noise", "because nobody owned it", "so new hires could follow it",
       "after a customer complaint", "to save a meeting", "because the old one drifted",
       "to match the new naming", "while waiting on legal")


def filler_sentence(rng: random.Random) -> str:
    return (
        f"The {rng.choice(TEAMS)} team {rng.choice(VERBS)} the {rng.choice(THINGS)} "
        f"for {rng.choice(CUSTOMERS)} {rng.choice(WHEN)} {rng.choice(WHY)}."
    )


# --8<-- [start:build]
def build_haystack(
    chars: int, position: float, distractors: bool, seed: int = 0
) -> str:
    """About `chars` characters of filler: the needle at `position`
    (0 is the start, 1 the end), plus distractors if asked."""
    rng = random.Random(seed)
    sentences, total = [], 0
    while total < chars:
        sentence = filler_sentence(rng)
        sentences.append(sentence)
        total += len(sentence) + 1
    inserts = [(position, NEEDLE)]
    if distractors:
        inserts += list(zip(DISTRACTOR_AT, DISTRACTORS))
    # Insert from the back, so earlier positions stay where they were.
    for at, sentence in sorted(inserts, reverse=True):
        sentences.insert(round(at * len(sentences)), sentence)
    starts = range(0, len(sentences), 6)
    paragraphs = [sentences[i : i + 6] for i in starts]
    return "\n\n".join(" ".join(p) for p in paragraphs)
# --8<-- [end:build]


# Harder tasks, from the conditions where the research found degradation.
# --8<-- [start:hard]
# Shares few words with the needle: the model must match meaning.
PARAPHRASE = (
    "Which number lets me send money back to Orion Bakery? "
    "Reply with just the number."
)
# Needs the whole document: every matching sentence counts.
COUNT_QUESTION = (
    "How many times did the security team audit something? "
    "Reply with just the number."
)
# --8<-- [end:hard]
COUNTED = "The security team audited "


def count_truth(document: str) -> int:
    """The right answer to COUNT_QUESTION for this document."""
    return document.count(COUNTED)


def grade_count(answer: str, truth: int) -> str:
    """'right' when the first number in the answer equals the true count."""
    numbers = re.findall(r"\d+", answer)
    if not numbers:
        return "wrong"
    return "right" if int(numbers[0]) == truth else "wrong"


# --8<-- [start:grade]
def grade(answer: str) -> str:
    """'right', 'distractor' (a near-miss number) or 'wrong'."""
    numbers = set(re.findall(r"\d{4}", answer))
    if numbers == {ANSWER}:
        return "right"
    wrong = {d.rstrip(".").split()[-1] for d in DISTRACTORS}
    return "distractor" if numbers & wrong else "wrong"
# --8<-- [end:grade]
