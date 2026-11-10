"""Chapter 6: chunk the help center, rank chunks with BM25, search it.

Both search tools use the same BM25 scorer. They differ in what a chunk
is and what a result tells the model: the naive one cuts fixed-size
pieces and returns them bare; the better one cuts by section, keeps each
section's title and date, and leaves archived articles out.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

from help_center import ARTICLES, Article

from agentkit import Tool

WORD = re.compile(r"[a-z0-9$.,]+")
STOP = frozenset("a an and are be can do does for how i in is it my of "
                 "on or the to we what when with you your".split())


def words(text: str) -> list[str]:
    tokens = (w.strip(".,") for w in WORD.findall(text.lower()))
    return [w for w in tokens if w and w not in STOP]


# --8<-- [start:bm25]
class BM25:
    """BM25: rank texts by how well they match a query."""

    def __init__(self, texts: list[str], k1=1.2, b=0.75) -> None:
        self.docs = [Counter(words(t)) for t in texts]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / len(self.docs)
        self.df = Counter(w for d in self.docs for w in d)
        self.k1, self.b, self.n = k1, b, len(self.docs)

    def score(self, query: str, i: int) -> float:
        doc, norm = self.docs[i], self.lengths[i] / self.avg
        total = 0.0
        for w in set(words(query)):
            idf = math.log(1 + (self.n - self.df[w] + 0.5)
                           / (self.df[w] + 0.5))
            tf = doc[w]
            total += idf * tf * (self.k1 + 1) / (
                tf + self.k1 * (1 - self.b + self.b * norm))
        return total
# --8<-- [end:bm25]

    def top(self, query: str, k: int) -> list[int]:
        scored = [(self.score(query, i), i) for i in range(self.n)]
        return [i for s, i in sorted(scored, key=lambda p: (-p[0], p[1]))[:k] if s > 0]


@dataclass(frozen=True)
class Chunk:
    article: str
    label: str  # what the result shows above the text
    text: str


# --8<-- [start:chunkers]
def fixed_chunks(size: int = 400) -> list[Chunk]:
    """Every article, cut every `size` characters, archived or not."""
    chunks = []
    for a in ARTICLES:
        for start in range(0, len(a.body), size):
            piece = a.body[start:start + size]
            chunks.append(Chunk(a.id, f"[{a.id}]", piece))
    return chunks


def section_chunks() -> list[Chunk]:
    """One chunk per section of each current article, labelled with
    the article's title, the section's heading and the date."""
    return [Chunk(a.id, f"[{a.id}] {a.title} > {heading} "
                        f"(updated {a.updated})", text)
            for a in ARTICLES if not a.archived
            for heading, text in sections(a)]
# --8<-- [end:chunkers]


def sections(article: Article) -> list[tuple[str, str]]:
    parts = article.body.split("## ")[1:]
    return [(p.split("\n", 1)[0], p.split("\n", 1)[1].strip()) for p in parts]


class Index:
    def __init__(self, chunks: list[Chunk], with_labels: bool) -> None:
        self.chunks = chunks
        texts = [f"{c.label}\n{c.text}" if with_labels else c.text for c in chunks]
        self.bm25 = BM25(texts)

    def hits(self, query: str, k: int = 3) -> list[Chunk]:
        return [self.chunks[i] for i in self.bm25.top(query, k)]

    def search(self, query: str, k: int = 3) -> str:
        hits = self.hits(query, k)
        if not hits:
            return "No results."
        return "\n\n".join(f"{c.label}\n{c.text.strip()}" for c in hits)


NAIVE_INDEX = Index(fixed_chunks(), with_labels=False)
SECTION_INDEX = Index(section_chunks(), with_labels=True)

QUERY = {"type": "object",
         "properties": {"query": {"type": "string", "minLength": 2}},
         "required": ["query"], "additionalProperties": False}

# --8<-- [start:tools]
NAIVE_SEARCH = Tool(
    "search_help", "Search the help center.", QUERY,
    NAIVE_INDEX.search,
)
GOOD_SEARCH = Tool(
    "search_help_center",
    "Search Brindle's current help center articles by keywords. "
    "Returns up to three sections, best match first, each headed "
    "by its article id, title, section and date. Results are the "
    "closest matches by wording, not guaranteed answers: if none of "
    "them answers the question, the help center does not cover it.",
    QUERY,
    SECTION_INDEX.search,
)
# --8<-- [end:tools]


def whole_help_center() -> str:
    """Every article, archived ones marked, for a prompt with no search."""
    return "\n\n".join(
        f"# [{a.id}] {a.title} (updated {a.updated}"
        f"{', ARCHIVED' if a.archived else ''})\n{a.body.strip()}"
        for a in ARTICLES
    )


# --8<-- [start:recall]
def found(index: Index, question, queries: list[str], k: int) -> bool:
    """Did any of the agent's queries return a chunk of the right
    article that holds the answer? No model call needed."""
    return any(c.article == question.source
               and re.search(question.fact, c.text, re.I)
               for q in queries for c in index.hits(q, k))
# --8<-- [end:recall]
