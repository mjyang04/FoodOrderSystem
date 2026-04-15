# From naive embeddings to hybrid + rerank: a food-ordering RAG evolution

This post is the retrieval half of the Sprint 6 AI-depth work on
FoodOrderSystem. It walks through how the menu search inside the AI service
went from a 40-line cosine top-k over an in-memory tensor to a two-stage
retrieval pipeline — BM25 plus dense embeddings fused with Reciprocal Rank
Fusion, followed by an optional cross-encoder reranker — and what each step
cost, measured against a labelled 50-case search eval set.

## Starting point: cosine top-k

The first working version in Sprint 4 was the simplest thing that could
possibly work: encode the whole menu once at startup with a multilingual
MiniLM, stack the vectors into a single `torch.Tensor`, and at query time
compute a dot product and take the top-k. It fit in one file
(`ai_service/src/fos_ai/services/search.py`) and gave genuinely good results
on paraphrased queries — "something spicy with peanuts" would surface Kung
Pao Chicken without any keyword match. That was the win.

The failures were predictable and concentrated on short, literal queries.
Menu searches are weird compared to document search: users type dish names
("mapo tofu"), partial brand names, or typo'd fragments, and dense embeddings
are not calibrated for three-token queries. Rare ingredients and numbers
(`"extra cheese"`, `"12 inch"`) got lost in the average-pooled vector.
Typos crossed the similarity threshold and returned nonsense. The eval harness
made this visible — Recall@5 on the 50 labelled cases was fine on paraphrase
queries and bad on literal ones.

## Step 1: add BM25

BM25 is the boring, correct fix for literal matching. I added `rank_bm25` as
a dependency and built an in-memory index over `food_name + description`.
Tokenization is deliberately stupid — lowercase, split on `\W+`, drop empties:

```python
_TOKEN_RE = re.compile(r"\W+")

def tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN_RE.split(text.lower()) if tok]
```

For a 70-item menu there's no reason to get fancy. No stemming, no stopword
lists, no language-specific tokenizer. The BM25 index is cached on the corpus
object and rebuilt only when the corpus itself is replaced. It adds about
100 microseconds per query on CPU. The small-menu caveat is real though — BM25
quality depends on document length statistics, and a one-sentence food
description is a degenerate case; at scale I'd bring in proper tokenization
and stopwords.

## Step 2: dense embeddings over Qdrant

Moving the dense side into Qdrant was not about performance — at 70 rows an
in-memory tensor is faster than a network round-trip — but about the shape
of the code. Qdrant gives me a collection with typed payload (`restaurant_id`,
`cuisine`, `price`) so later filtering can push down into the vector store
instead of being a Python post-filter. An `ingest_menu_to_qdrant.py` script
reads MySQL, encodes with the same MiniLM, and upserts. Tests use Qdrant's
in-memory mode (`:memory:`) so the test suite stays hermetic.

## Step 3: RRF fusion

Reciprocal Rank Fusion is the ten-line solution that made this worth doing.
For each ranking, every document at position `rank` contributes
`1 / (k + rank)` to its fused score, and you sum across rankings:

```python
def _rrf_fuse(rankings, k=60):
    totals: dict[int, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _score) in enumerate(ranking, start=1):
            totals[doc_id] = totals.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(totals.items(), key=lambda kv: -kv[1])
```

`k=60` is the paper default and I didn't touch it. The point of RRF is that
it requires no per-query tuning, no weight calibration, no score
normalisation — the BM25 scores and the cosine scores live in different
ranges but only their ranks matter. Easy to implement, easy to defend in a
code review.

## Step 4: cross-encoder rerank

The last stage is `BAAI/bge-reranker-base` wrapped as a `CrossEncoder`. This
is the textbook recall-then-precision pattern: RRF gives you top-20 that's
likely-relevant, the cross-encoder re-scores those 20 by actually attending
over the query-document pair and returns top-10. The tradeoff is concrete:
the model is ~280 MB on first download and adds roughly 100 ms per query on
CPU. For an interactive search path, that's a real cost, which is why it
ships behind `RERANK_ENABLED=false`. The eval hooks are wired up on both
sides of the flag so the MRR gain is measurable on demand.

## Measuring it

The whole point of building this ladder was being able to prove each rung was
worth it. The eval harness (`ai_service/eval/`) holds 50 labelled search
cases and runs Hit@5, MRR, nDCG@10 under `pytest -m eval`. A nightly CI job
(`.github/workflows/ai-eval.yml`) blocks PRs on regression.

## What I didn't chase

A few honest trade-offs. RRF k=60 is a defensible default but almost certainly
not optimal for this corpus; I didn't sweep it. The reranker gain on the
current 50-case eval is a single data point and needs more cases before I'd
publish a number. Chunking strategies (F4 in the original Sprint 6 plan) were
deferred because menu items are already one-sentence documents — chunking
only starts paying off on reviews, which aren't ingested yet.

## Next

Sprint 7 candidates: tuning RRF with labelled pairs, a learned reranker that
replaces the cross-encoder for the specific food domain, multi-vector payload
(separate embeddings for name vs description vs tags) to let Qdrant do
hybrid scoring natively, and ingesting user reviews as a second collection
so the RAG has something longer than one sentence to work with.

Repo references: `ai_service/src/fos_ai/services/hybrid_search.py` (fusion),
`ai_service/src/fos_ai/ml/reranker.py` (cross-encoder), and
`ai_service/scripts/ingest_menu_to_qdrant.py` (data loader).

— Mingjia Yang, 2026-04
