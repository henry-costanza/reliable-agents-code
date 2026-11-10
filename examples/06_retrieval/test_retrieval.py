"""Chapter 6: chunking, ranking and grading offline; the recorded runs replayed."""

import json

import pytest
from help_center import ARTICLES, BY_ID, QUESTIONS
from retrieval import (
    BM25, GOOD_SEARCH, NAIVE_INDEX, NAIVE_SEARCH, SECTION_INDEX, fixed_chunks,
    found, section_chunks,
)
from retrieval_experiment import CASSETTE, RESULTS, grade, run, summarize

from agentkit.cassette import ReplayProvider


def test_bm25_prefers_the_text_with_rarer_matching_words():
    bm25 = BM25(["refund window thirty days", "refund refund refund", "seat price"])
    assert bm25.top("refund window", 3) == [0, 1]


def test_fixed_chunks_cover_every_article_including_archived():
    chunks = fixed_chunks()
    assert {c.article for c in chunks} == {a.id for a in ARTICLES}
    assert all(len(c.text) <= 400 for c in chunks)


# --8<-- [start:chunk-test]
def test_section_chunks_keep_their_context_and_skip_archived():
    chunks = section_chunks()
    assert "HC-090" not in {c.article for c in chunks}
    window = next(c for c in chunks if "30 days" in c.text)
    assert window.label == ("[HC-101] Refunds and credits > "
                            "Refund window (updated 2026-09-15)")
# --8<-- [end:chunk-test]


def test_every_answerable_question_has_its_fact_in_its_article():
    import re
    for q in QUESTIONS:
        if q.source:
            assert re.search(q.fact, BY_ID[q.source].body, re.I), q.text


def test_naive_search_can_return_the_archived_policy():
    assert "[HC-090]" in NAIVE_SEARCH.function("refund policy 14 days annual plans")
    assert "HC-090" not in GOOD_SEARCH.function("refund policy 14 days annual plans")


@pytest.mark.parametrize(
    ("n", "answer", "verdict"),
    [(0, "Within 30 days of a charge.\nSource: HC-101", "right"),
     (0, "You have 14 days.\nSource: HC-090", "stale"),
     (0, "Within 30 days.\nSource: HC-090", "wrong source"),
     (0, "I can't find that.\nSource: none", "declined"),
     (10, "The help center does not cover this.\nSource: none", "right"),
     (10, "Yes, we accept Bitcoin.\nSource: HC-101", "made up"),
     (0, "Within 30 days.\n**Source:** HC-101", "right"),
     (0, "HC-101 says 30 days, HC-090 says 14 days.\nSource: HC-101",
      "hedged")],
)
def test_grading(n, answer, verdict):
    assert grade(QUESTIONS[n], answer) == verdict


def test_replay_reproduces_the_recorded_results():
    provider = ReplayProvider(CASSETTE)
    outcomes = run(provider)
    assert provider.unused == 0
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert outcomes == recorded["outcomes"]
    assert summarize(outcomes) == recorded["rows"]


def recorded_runs(arm: str, question: int | None = None) -> list[dict]:
    outcomes = json.loads(RESULTS.read_text(encoding="utf-8"))["outcomes"]
    return [o for o in outcomes if o["arm"] == arm
            and (question is None or o["question"] == question)]


def test_every_naive_run_that_saw_the_archived_policy_failed():
    saw = [o for o in recorded_runs("naive search")
           if any(c.article == "HC-090" for q in o["queries"]
                  for c in NAIVE_INDEX.hits(q, 3))]
    assert len(saw) == 4
    assert all(o["verdict"] in ("hedged", "stale") for o in saw)


# --8<-- [start:recall-test]
def test_five_results_would_have_found_the_missed_section():
    retention = QUESTIONS[7]  # how long are invoices kept?
    for attempt in recorded_runs("section search", question=7):
        queries = attempt["queries"]  # the agent's own, as recorded
        assert not found(SECTION_INDEX, retention, queries, k=3)
        assert found(SECTION_INDEX, retention, queries, k=5)
# --8<-- [end:recall-test]
