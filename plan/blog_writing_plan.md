# Blog Writing Plan — Sprint 6 Technical Posts

**Status:** drafts exist, filling in real numbers pending
**Created:** 2026-04-15
**Parent:** `plan/sprint_6_ai_depth.md` §2 Phase 6

Two posts already stubbed under `docs/blog/`. Both need real numbers, a
screenshot or two, honest-failure sections, and a publishing push. This
document captures what to fill where so a future-me (or a subagent) can
finish in one sitting.

---

## 0. Why these posts exist

These are resume anchors for backend + LLM-algorithm interviews. The posts
must:

- **Prove the work is real** — specific numbers, commit SHAs, code snippets,
  one screenshot of eval output per post.
- **Show technical judgement** — explain why each decision was made and what
  alternatives were rejected.
- **Be honest about limits** — no "we got 100% everything". Reviewers who
  can code will sniff out glossed numbers in three seconds.
- **Read in 5–7 minutes** — target 1500 words each.

Current length: `rag-hybrid-retrieval-evolution.md` ~750 words,
`lora-intent-classifier.md` ~850 words. Need ~600 more words each.

---

## 1. Post 1 — `docs/blog/rag-hybrid-retrieval-evolution.md`

### Final structure (sections that already exist, what to do with each)

| § | Section                | Status  | Action                                    |
|---|------------------------|---------|-------------------------------------------|
| 1 | Starting point (cosine)| good    | keep                                      |
| 2 | Step 1 — BM25          | good    | keep                                      |
| 3 | Step 2 — Qdrant        | good    | keep                                      |
| 4 | Step 3 — RRF fusion    | good    | keep                                      |
| 5 | Step 4 — cross-encoder | good    | keep                                      |
| 6 | **Measuring it**       | thin    | **fill with numbers below**               |
| 7 | What I didn't chase    | thin    | add: rerank A/B on larger set not run yet |
| 8 | Next                   | good    | add Sprint 7 link / teaser                |

### Numbers to drop into §6 "Measuring it"

From running `uv run pytest eval/ -m eval -s` on commit `da022ad`:

| Metric             | Value  | Gate   | Dataset                              |
|--------------------|--------|--------|--------------------------------------|
| Hit@5              | 0.900  | ≥ 0.80 | 50 labelled search queries           |
| MRR                | 0.803  | ≥ 0.60 | 50 labelled search queries           |
| nDCG@5             | 0.795  | ≥ 0.65 | 50 labelled search queries           |

Live smoke on `/api/ai/search?q=spicy%20noodles&limit=5` (JWT as `demo_s6`,
reranker on):

```
Sichuan Beef Noodles  score=0.9909   rid=1
Dan Dan Noodles       score=0.9527   rid=1
Wonton Noodle Soup    score=0.0959   rid=3
Sichuan Dumplings     score=0.0328   rid=2
Hummus                score=0.0155   rid=9
```

> Notice the top-2 dominance: 0.99 / 0.95 then a cliff to 0.10. That
> shape is the cross-encoder fingerprint. Pure RRF fusion (no rerank)
> keeps scores clustered in a narrow band near 0 — see the commit
> `0317aca` baseline screenshot.

Other live signals to cite:

- Cache hit rate 0.50 after two identical search requests (from
  `GET /api/ai/stats` as admin). Prove the 5-minute TTL + LRU is alive.
- Total LLM calls during the demo: 3; estimated cost $0.00 because the
  MiniMax proxy strips usage counters (good honest caveat for §6).

### Failure / honest-limit bullets for §7

- Rerank v.s. RRF has **not** been measured on a larger gold set.
  Current eval size (50) is not enough to resolve a 15 % MRR lift. Flagged
  as Sprint 7 work.
- BM25 tokenizer is intentionally naive (`re.split(\W+)`). On a ≥ 10 k
  menu it would lose to a proper IDF-weighted index with stemming.
- Qdrant runs single-node on localhost. Production would need at least
  replicated snapshots and a CI job that restores + re-ingests before
  every green deploy.
- Embedding model: `bge-small-zh-v1.5` was chosen for bilingual and
  speed. On a pure-English menu `bge-base-en-v1.5` would probably win a
  few points. Not swapped because the corpus is small enough that the
  difference is unmeasurable here.

### Code snippets to paste (keep under 15 lines each)

**RRF fusion kernel** — quote from `ai_service/src/fos_ai/services/hybrid_search.py`:

```python
# Reciprocal Rank Fusion — no weight tuning, industry default.
K = 60
scores: dict[int, float] = {}
for rank, fid in enumerate(bm25_ranked, start=1):
    scores[fid] = scores.get(fid, 0.0) + 1.0 / (K + rank)
for rank, (fid, _s, _payload) in enumerate(dense_ranked, start=1):
    scores[fid] = scores.get(fid, 0.0) + 1.0 / (K + rank)
top = sorted(scores.items(), key=lambda x: -x[1])[:limit]
```

**Two-stage invocation** — quote from `services/search.py`:

```python
candidates = hybrid_search(query, corpus, embedder, vector_store,
                            limit=rerank_candidates)  # top-50
if reranker is not None:
    return reranker.rerank(query, candidates, top_k=limit)  # top-10
return candidates[:limit]
```

---

## 2. Post 2 — `docs/blog/lora-intent-classifier.md`

### Final structure

| § | Section                | Status   | Action                                     |
|---|------------------------|----------|--------------------------------------------|
| 1 | Why LoRA               | good     | keep                                       |
| 2 | Choosing the base      | good     | keep                                       |
| 3 | Data synthesis         | good     | keep                                       |
| 4 | Training recipe        | good     | add real 9-minute wall-clock on M5 Pro    |
| 5 | **Three-way comparison** | 3 TBDs | fill LoRA row now; Haiku rows: see §3 below|
| 6 | The fallback strategy  | good     | add source-hot-swap demo (see below)      |
| 7 | Honest limitations     | good     | emphasise val=1.00 is synthetic-only       |
| 8 | Reproduce              | good     | update git hash to current head            |

### Numbers to drop into §4 "Training recipe"

From commit `da022ad`, `training/fos_ai_training/intent/output/r8/`:

- Wall clock: **9 minutes** on M5 Pro, 48 GB unified memory, MPS backend,
  float32, `PYTORCH_ENABLE_MPS_FALLBACK=1`.
- 94 training steps (504 samples / batch 4 / grad_accum 4 × 3 epochs).
- Per-step: ~5.5 s including forward + backward + optimizer.
- Adapter: 18 MB on disk. Full output dir (adapter + checkpoints +
  tokenizer): 213 MB.
- Trainable params: 4 399 104 / 498 431 872 = **0.88 %**.
- Final `train_loss` 0.50, final `eval_loss` 0.98.

### Three-way comparison table (§5) — fill what we have, flag what we don't

| Setting                           | Accuracy       | p95 latency | Cost / 1k calls |
|-----------------------------------|----------------|-------------|-----------------|
| Zero-shot, Claude Haiku 4.5       | TBD            | ~ 1200 ms   | $0.08 (est.)    |
| Few-shot (4 ex), Claude Haiku 4.5 | TBD            | ~ 1400 ms   | $0.12 (est.)    |
| LoRA, Qwen2.5-0.5B, local MPS     | 1.00 (synth)   | ~ 300 ms    | $0.00           |

Two TBDs remaining (Haiku rows). How to fill, ~10 min of work:

1. Build a 50-sample labelled eval split from `data.jsonl`
   (deterministic: every 10th row).
2. Zero-shot row: hit `POST /ai/intent` with `INTENT_ADAPTER_PATH=` empty
   and `LLM_PROVIDER=anthropic` pointing at real Claude Haiku. Record
   accuracy + latency from `/api/ai/stats`.
3. Few-shot row: modify `FallbackIntentClassifier` system prompt to
   include 4 examples. Same eval.
4. Paste the numbers back into the table and cite the commit SHA.

**Caveat to add in prose immediately below the table**: "LoRA accuracy is
on synthetic data. On real chat traffic we expect Haiku to recover because
template variance at inference > template variance at training. The
interesting columns are latency and cost — and LoRA wins both by a large
enough margin that the accuracy gap has to be large before fallback wins."

### §6 "Fallback strategy" — add live hot-swap demo

Paste the observed transition:

```bash
# With INTENT_ADAPTER_PATH unset:
$ curl -sX POST http://localhost:8000/ai/intent \
    -H 'X-User-Id: 7' -d '{"text":"cancel order 42"}'
{"label":"cancel","confidence":0.98,"source":"fallback"}

# After setting INTENT_ADAPTER_PATH=/path/to/output/r8 and restarting:
$ curl -sX POST http://localhost:8000/ai/intent \
    -H 'X-User-Id: 7' -d '{"text":"cancel order 42"}'
{"label":"cancel","confidence":0.9999916553497314,"source":"lora"}
```

Narrate: `source` field is load-bearing — callers can pick a different
path if the fallback is live (retries, confidence-based escalation, A/B
routing). Also note the confidence jump from 0.98 to 0.9999 is a typical
softmax-sharpening pattern after SFT — not evidence of actual accuracy
gain by itself.

### §7 "Honest limitations" — punch it up

- **val_accuracy = 1.00 is a synthetic-data upper bound**, not production
  accuracy. Every validation sample came from the same 5–10 templates that
  seeded training.
- **9 classes are small**. Real chat will have `order modification`,
  `address change`, `split bill`, etc. The classifier has zero signal on
  anything outside the 9 label set — it will confidently emit the nearest
  wrong label.
- **No adversarial data**: typos, code-switching mid-sentence, emoji-heavy
  messages. A real deployment would collect real logs and retrain monthly.
- **Deterministic template generation makes the dev set trivially easy**.
  The honest fix is a real-traffic-labelled 200-sample eval set — called
  out as Sprint 7 work.

---

## 3. How to run the Haiku baseline (to fill the two TBDs in Post 2)

Quick procedure, ~10 minutes. Do this before publishing Post 2.

1. Build eval split:
   ```bash
   cd /Users/mj/FoodOrderSystem/ai_service
   uv run python -c "
   import json
   rows = [json.loads(l) for l in open('training/fos_ai_training/intent/data.jsonl')]
   val = rows[::10]  # every 10th → 50 samples
   json.dump(val, open('training/fos_ai_training/intent/eval_split.json', 'w'),
             ensure_ascii=False, indent=2)
   print(len(val), 'samples')
   "
   ```

2. Zero-shot run — `.env` with `INTENT_ADAPTER_PATH=` blank, restart service:
   ```bash
   uv run python - <<'PY'
   import httpx, json, time
   val = json.load(open('training/fos_ai_training/intent/eval_split.json'))
   hits, latencies = 0, []
   for row in val:
       t0 = time.time()
       r = httpx.post('http://localhost:8000/ai/intent',
                      json={'text': row['text']},
                      headers={'X-User-Id': '7'}).json()
       latencies.append((time.time() - t0) * 1000)
       if r.get('label') == row['label']: hits += 1
   print(f'acc={hits/len(val):.2f}  p95={sorted(latencies)[int(.95*len(latencies))]:.0f}ms')
   PY
   ```

3. Few-shot: edit `FallbackIntentClassifier._build_prompt` (in
   `services/intent_classifier.py`) to include 4 in-context examples —
   one `search`, one `order`, one `cancel`, one `chitchat`. Re-run step 2.

4. LoRA row (already measured): acc=1.00 on synthetic val. Keep that label
   and add a note that numbers were measured on commit `da022ad`.

---

## 4. Publishing sequence

Do the posts in this order:

1. Finish and commit **Post 1** (RAG). It has zero blockers — all numbers
   available today. 30 minutes of writing.
2. Run the Haiku baseline (§3 above), fill the table, then commit
   **Post 2** (LoRA). 45 minutes total.
3. Crosspost:
   - **Personal blog** (Hugo / Jekyll) — primary, SEO, resume link. Add a
     `/blog` route, not inside the repo docs.
   - **知乎**: Chinese translation, post in the 机器学习 + 后端开发
     columns. Drop a pinned comment linking to the English canon.
   - **Medium / dev.to**: verbatim English, for international visibility.
   - **LinkedIn post** per blog — one paragraph hook + link. Target
     technical recruiters + backend/ML hiring managers.
4. Add both URLs to the top of `README.md` under a "Writing" section and
   to LinkedIn featured section. That's the interview anchor.

---

## 5. Writing-craft rules (apply to both posts)

- One decision per paragraph. "We did X because Y, and not Z because W."
- No filler transitions. "Now let's move on to..." gets cut.
- **Every claim backed by either a number or a file path / commit hash**.
- One screenshot per post, maximum. Prose > pictures.
- Read the post out loud before publishing. If you pause, cut the sentence.
- Footer: `— Mingjia Yang, 2026-04` and a link back to the repo at the
  commit the post is pinned to.

---

## 6. Definition of done

- [ ] Post 1 filled with eval numbers (Hit@5/MRR/nDCG) and live smoke output
- [ ] Post 1 §7 failure list updated with three bullets above
- [ ] Post 2 Haiku baseline measured and table filled
- [ ] Post 2 §6 hot-swap demo block inserted
- [ ] Both posts committed with a single `docs(blog): complete both posts`
- [ ] Personal blog live, 知乎 live, LinkedIn posts sent
- [ ] README linked to both URLs
