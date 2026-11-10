"""Chapter 2: the haystack is deterministic, and the needle sits where asked."""

import re

import pytest
from haystack import (
    ANSWER,
    DISTRACTORS,
    NEEDLE,
    PARAPHRASE,
    build_haystack,
    count_truth,
    grade,
    grade_count,
)


def test_same_arguments_give_the_same_document():
    assert build_haystack(20_000, 0.5, True) == build_haystack(20_000, 0.5, True)
    assert build_haystack(20_000, 0.5, True, seed=1) != build_haystack(20_000, 0.5, True)


def test_length_is_close_to_the_target():
    for chars in (16_000, 128_000):
        assert chars <= len(build_haystack(chars, 0.5, False)) <= chars * 1.02


@pytest.mark.parametrize("position", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_needle_appears_once_where_asked(position):
    text = build_haystack(50_000, position, False)
    assert text.count(NEEDLE) == 1
    where = text.index(NEEDLE) / len(text)
    assert abs(where - position) < 0.02


def test_distractors_appear_only_when_asked():
    plain = build_haystack(50_000, 0.5, False)
    noisy = build_haystack(50_000, 0.5, True)
    assert not any(d in plain for d in DISTRACTORS)
    assert all(noisy.count(d) == 1 for d in DISTRACTORS)
    assert noisy.count(NEEDLE) == 1


def test_the_only_numbers_are_the_needle_and_distractors():
    numbers = set(re.findall(r"\d+", build_haystack(100_000, 0.5, True)))
    assert numbers == {ANSWER, "7314", "7431", "3741", "1734"}


def test_paraphrase_shares_few_words_with_the_needle():
    words = lambda s: {w.strip("?.,").lower() for w in s.split()}  # noqa: E731
    question = words(PARAPHRASE.split("?")[0])
    assert question & words(NEEDLE) == {"orion", "bakery"}


def test_count_truth_counts_every_matching_sentence():
    text = build_haystack(128_000, 0.5, False)
    truth = count_truth(text)
    assert truth == len(re.findall(r"The security team audited ", text))
    assert 5 <= truth <= 40  # enough to count, not a number to guess


def test_count_truth_grows_with_length():
    counts = [count_truth(build_haystack(chars, 0.5, False)) for chars in (16_000, 128_000, 512_000)]
    assert counts == sorted(counts) and counts[0] < counts[-1]


@pytest.mark.parametrize(
    ("answer", "truth", "verdict"),
    [("12", 12, "right"), ("There are 12.", 12, "right"), ("11", 12, "wrong"), ("none", 12, "wrong")],
)
def test_count_grading(answer, truth, verdict):
    assert grade_count(answer, truth) == verdict


@pytest.mark.parametrize(
    ("answer", "verdict"),
    [
        ("7341", "right"),
        ("The key is 7341.", "right"),
        ("7314", "distractor"),
        ("Either 7341 or 7314", "distractor"),
        ("I could not find it.", "wrong"),
        ("1234", "wrong"),
    ],
)
def test_grading(answer, verdict):
    assert grade(answer) == verdict
