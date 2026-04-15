# Sprint 6 — AI Depth: RAG v2 + Eval Harness + LoRA + Observability

**Status:** planned
**Created:** 2026-04-15
**Branch:** `feature/rest-api` (or new `feature/ai-depth`)
**Entry gate:** Sprint 5 closed (chat agent + SSE + eval harness v1 green)
**Goal:** 把"会调 LLM API 的应用工程"升级成"面试能讲算法深度的 AI 工程"。面向**后端 + LLM 算法/应用**岗位的简历加分项。
**Exit:** RAG 从朴素 embedding 升级为 hybrid+rerank；eval 覆盖 200+ case 并产出 metrics 报告；一个 LoRA 适配器在 HuggingFace 可复现；LLM 调用全链路可观测（token/latency/cost/cache）。

---

## 0. Scope

### In scope

| ID | Feature | Layer | Interview Hook |
|----|---------|-------|----------------|
| F1 | 向量库接入（Qdrant 本地 docker，持久化菜单+评论） | Python | "为什么不用 numpy 内存向量？扩展性、元数据过滤" |
| F2 | Hybrid search：BM25（rank_bm25）+ dense embedding | Python | "稀疏+稠密互补，BM25 抓关键词，dense 抓语义" |
| F3 | Cross-encoder rerank（bge-reranker-base via API or local inference） | Python | "两阶段检索：召回 top-50 → rerank top-10" |
| F4 | Chunking 策略实验：固定/语义/菜品卡片结构化 | Python | "RAG 质量 80% 取决于 chunking" |
| F5 | Eval harness v2：200+ 标注 case，分 search/recommend/parse/chat 四套 | Python | "Recall@k / MRR / nDCG / 人工 LLM-as-judge" |
| F6 | Regression gate：CI 运行 eval，指标下降超阈值阻断合并 | CI | "防止 prompt 调参回归" |
| F7 | LoRA 微调意图分类器（Qwen2.5-0.5B-Instruct → 意图 9 类） | Python | "数据构造 + LoRA 秩/学习率消融 + 推送 HF" |
| F8 | LoRA 适配器服务化：FastAPI endpoint 加载 adapter 做意图路由 | Python | "微调模型 vs prompt few-shot 成本对比" |
| F9 | 可观测性：OpenTelemetry 埋点 LLM 调用（tokens/latency/cost/provider） | Python | "生产 LLM 系统的 SRE 视角" |
| F10 | Prompt cache 命中率统计 + LRU cache for parser/search queries | Python | "Anthropic prompt caching + 业务层 query cache" |
| F11 | 技术博客 2 篇（RAG 实战 + LoRA 实战）发到个人站/知乎 | docs | 简历锚点 |

### Out of scope（明确不做）

- ❌ 自建推理（vLLM/TGI）——保持 API 调用
- ❌ 全量模型训练、预训练、继续预训练
- ❌ 分布式训练、多卡、DeepSpeed/FSDP
- ❌ 论文从零复现——直接用 sentence-transformers/bge 现成模型
- ❌ RLHF/DPO——仅 SFT LoRA
- ❌ 多模态（视觉菜品识别）——留待未来
- ❌ Agent 记忆长期化（向量化对话历史）——Sprint 7 再议

---

## 1. Design Decisions

### D1. 向量库选择 — Qdrant
- **选 Qdrant 不选 Milvus/Weaviate**：docker 单容器起、REST+gRPC、元数据过滤语法清晰、社区活跃、面试常被问到
- **集合设计**：
  - `menu_items`：菜品粒度，payload = `{restaurant_id, cuisine, price, tags}`
  - `reviews`：评论粒度（后续加入），payload = `{restaurant_id, rating, date}`
- **embedding 模型**：`BAAI/bge-small-zh-v1.5`（已在 Sprint 4 使用）或切换到 `bge-m3`（多语言+长文）

### D2. Hybrid search 融合 — RRF (Reciprocal Rank Fusion)
- 简单、无需调权重、工业界常用
- BM25 top-50 + dense top-50 → RRF → top-20 候选给 rerank
- 公式：`score(d) = Σ 1/(k + rank_i(d))`, k=60

### D3. Rerank — bge-reranker-base（本地）
- 模型 ~280MB，CPU 推理即可（top-20 候选延迟 <500ms）
- 保持"API 调用"原则的边界：embedding/rerank 是**小模型本地跑**，生成仍是 API
- 这样面试能讲"生成用 API 降成本，检索用本地模型降延迟"

### D4. Eval harness v2 数据
- **Search set**：100 query，每个标注 top-3 相关菜品 id → Recall@5, MRR
- **Recommend set**：50 user profile，标注 5 个偏好菜品 → nDCG@10
- **Parse set**：50 NL 订单，标注结构化 JSON → exact match + field F1
- **Chat set**：30 多轮对话，用 Claude-as-judge 评 helpfulness/correctness 0-5 分
- 数据来源：手工造 60% + LLM 生成候选人工标注 40%

### D5. LoRA 任务选择 — 意图分类
**Why intent classification 而不是生成任务？**
- 数据量小（500 样本即可）
- 评测明确（accuracy/F1）
- 面试易讲：对比 prompt zero-shot / few-shot / LoRA 三档准确率和成本
- 9 类意图：`search / recommend / order / status_check / cancel / rating / menu_browse / chitchat / complaint`

**训练栈**：
- 基座：`Qwen/Qwen2.5-0.5B-Instruct`（0.5B 参数，Mac M 系列 MPS 可跑，或 Colab T4 免费）
- 框架：`peft` + `transformers` + `trl`
- 超参：r=8, alpha=16, dropout=0.05, lr=2e-4, 3 epoch
- 产出：HF 仓库 `mjyangnb/fos-intent-classifier-qwen2.5-0.5b-lora`

### D6. 可观测性栈
- **OpenTelemetry Python SDK** → **Jaeger**（docker 本地）或直接 stdout exporter
- 每次 LLM 调用 span 记录：`provider, model, input_tokens, output_tokens, cost_usd, latency_ms, cache_hit, tool_calls`
- 聚合 endpoint：`GET /api/ai/stats` 返回 24h 汇总

---

## 2. Phases

### Phase 1 — Vector DB + Hybrid Search (3-4 days)
- [ ] 1.1 `docker-compose.yml` 加 qdrant service（port 6333）
- [ ] 1.2 `fos_ai/ml/vector_store.py` — Qdrant 客户端封装（upsert/search/filter）
- [ ] 1.3 迁移脚本 `scripts/ingest_menu_to_qdrant.py` — 从 MySQL 读菜品，embedding，写入 Qdrant
- [ ] 1.4 `fos_ai/services/hybrid_search.py` — BM25 索引（内存 rank_bm25）+ dense（qdrant）+ RRF 融合
- [ ] 1.5 替换 `search.py` 后端，保留 API 契约不变
- [ ] 1.6 单测 + 对比 old vs new 在 search eval set 上的 Recall@5

**Exit:** `/api/ai/search` 走 hybrid 链路，eval Recall@5 提升 ≥10%

### Phase 2 — Rerank (2 days)
- [ ] 2.1 `fos_ai/ml/reranker.py` — 封装 `BAAI/bge-reranker-base`（sentence-transformers CrossEncoder）
- [ ] 2.2 `hybrid_search` 加两阶段：召回 50 → rerank 10
- [ ] 2.3 延迟对比 + 开关 config（`RERANK_ENABLED`）
- [ ] 2.4 eval 对比 no-rerank vs rerank MRR

**Exit:** rerank 开启时 MRR 提升 ≥15%，p95 延迟 <800ms

### Phase 3 — Eval Harness v2 (2-3 days)
- [ ] 3.1 目录结构 `ai_service/eval/{datasets,runners,metrics,reports}/`
- [ ] 3.2 标注数据集 4 份 jsonl（search 100, recommend 50, parse 50, chat 30）
- [ ] 3.3 metrics 实现：Recall@k, MRR, nDCG@k, exact_match, field_f1
- [ ] 3.4 LLM-as-judge runner（chat 集）：Claude Haiku 打分，3 次投票取中位数
- [ ] 3.5 `python -m fos_ai.eval.run --suite all` → 生成 markdown 报告到 `eval/reports/YYYY-MM-DD.md`
- [ ] 3.6 CI workflow `.github/workflows/ai-eval.yml` 每夜跑并发评论到 PR

**Exit:** 一条命令出完整报告；CI 回归护栏生效

### Phase 4 — LoRA Intent Classifier (3-4 days)
- [ ] 4.1 `ai_service/training/intent/data.py` — 生成 500 标注样本（300 LLM 生成 + 200 手工）
- [ ] 4.2 `ai_service/training/intent/train.py` — peft+trl LoRA SFT，记录 wandb（或 tensorboard）
- [ ] 4.3 消融表：r={4,8,16}, lr={1e-4,2e-4,5e-4}，报告 val accuracy
- [ ] 4.4 推送到 HuggingFace Hub + model card（README 含训练细节）
- [ ] 4.5 `fos_ai/services/intent_classifier.py` — 加载 adapter 做推理（fastapi 启动时预热）
- [ ] 4.6 `POST /api/ai/intent` endpoint，接入 chat agent 路由前置
- [ ] 4.7 对比表：zero-shot Claude / few-shot Claude / LoRA Qwen0.5B — accuracy、p95 延迟、每千次成本

**Exit:** HF 仓库公开可见，对比表能讲清三档 tradeoff

### Phase 5 — Observability (2 days)
- [ ] 5.1 `fos_ai/obs/tracing.py` — OTel SDK init，stdout + OTLP exporter
- [ ] 5.2 装饰器 `@trace_llm_call` 包裹 `llm_client` 所有调用
- [ ] 5.3 Prompt cache 统计（Anthropic 返回 `cache_read_input_tokens`）写入 span attr
- [ ] 5.4 业务 LRU cache for `parse()` 和 `search()`（键 = hash(query+params)），命中率埋点
- [ ] 5.5 `GET /api/ai/stats` 聚合 endpoint（24h window）
- [ ] 5.6 `docker-compose` 加 jaeger service 可选

**Exit:** 能在 stdout/jaeger 看到每次 LLM 调用 span，stats endpoint 返回聚合指标

### Phase 6 — Docs & Blog (1-2 days)
- [ ] 6.1 更新 `README.md` 架构图（加 Qdrant/Reranker/OTel）
- [ ] 6.2 博客 1：《从朴素 embedding 到 hybrid+rerank：一个外卖 RAG 的实战演进》
- [ ] 6.3 博客 2：《用 500 条数据 + LoRA 把 Qwen0.5B 调成意图分类器：成本、延迟、准确率三角权衡》
- [ ] 6.4 `plan/sprint_6_ai_depth.md` 结尾填写"面试话术卡片"（见 §5）

---

## 3. File Layout (additions)

```
ai_service/
  src/fos_ai/
    ml/
      vector_store.py        # Qdrant client wrapper
      reranker.py            # bge-reranker CrossEncoder
    services/
      hybrid_search.py       # BM25 + dense + RRF + rerank
      intent_classifier.py   # LoRA adapter inference
    obs/
      tracing.py             # OpenTelemetry init
      metrics.py             # stats aggregator
    routers/
      intent.py              # POST /api/ai/intent
      stats.py               # GET  /api/ai/stats
  eval/
    datasets/
      search.jsonl           # 100 cases
      recommend.jsonl        # 50
      parse.jsonl            # 50
      chat.jsonl             # 30
    runners/
      search_runner.py
      recommend_runner.py
      parse_runner.py
      chat_runner.py         # LLM-as-judge
    metrics/
      retrieval.py           # recall, mrr, ndcg
      generation.py          # exact_match, f1
    reports/
      2026-04-XX.md
    run.py                   # CLI entry
  training/
    intent/
      data.py
      train.py
      configs/{r4,r8,r16}.yaml
      model_card.md
  scripts/
    ingest_menu_to_qdrant.py
docker-compose.yml            # + qdrant, jaeger
.github/workflows/ai-eval.yml # nightly eval
```

---

## 4. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| LoRA 训练 Mac MPS OOM | M | 先 Colab T4 跑通，再本地尝试；batch=1 + grad accum |
| bge-reranker 本地 CPU 延迟超标 | M | 缓存高频 query；RERANK_ENABLED 开关；top-k 降到 20 |
| Qdrant docker 对齐 schema 返工 | L | Phase 1.2 先定 payload schema 文档再写代码 |
| Eval 标注数据成本 | M | 60% LLM 生成 + 快速人工校验；用 Claude Sonnet 生成候选 |
| HF 推送被限流 | L | 用 `hf_transfer`；提前建仓库 |
| Blog 写作挤占时间 | M | Phase 6 可延后到 Sprint 7，但别跳过——简历锚点 |

---

## 5. Interview Talk-Track Cards（Phase 6 填）

预留 6 张卡片，每张 3-5 句：

1. **项目一句话自我介绍**
2. **为什么用 hybrid search 而不是纯 embedding？**
3. **Rerank 带来多少收益？怎么衡量的？**
4. **LoRA 微调的数据怎么来的？有没有过拟合？**
5. **LLM 调用的成本和延迟怎么监控？**
6. **如果要上线，还差什么？**（→ 引出 Sprint 7 方向）

---

## 6. Done Criteria (Sprint 6 exit checklist)

- [ ] Qdrant 本地 docker 跑通，菜单 70 条 + 未来扩展预留
- [ ] Hybrid+rerank 在 eval search 集 Recall@5 ≥ 基线 +10%，MRR ≥ 基线 +15%
- [ ] eval harness 4 套数据集齐全，`run --suite all` 一键出报告
- [ ] CI 回归护栏绿
- [ ] LoRA 适配器 HF 公开 + 对比表（zero-shot / few-shot / LoRA）写进 README
- [ ] `/api/ai/stats` 能返回真实聚合数据
- [ ] README 架构图更新，2 篇博客链接附上
- [ ] 所有新增代码 pytest 覆盖，C++ ctest 不回归

---

## 7. Estimated Effort

| Phase | Days |
|-------|------|
| 1. Vector DB + Hybrid | 3-4 |
| 2. Rerank | 2 |
| 3. Eval v2 | 2-3 |
| 4. LoRA | 3-4 |
| 5. Observability | 2 |
| 6. Docs & Blog | 1-2 |
| **Total** | **13-17 days** |

按每天 3-4 小时兼顾投入，约 **3-4 周** 完成。

---

## 8. Next after Sprint 6 (preview, not in scope)

- Sprint 7 候选：agent 长期记忆（对话历史向量化）/ 多模态（菜品图检索）/ 在线 A/B 评测
- 简历最后形态：后端（C++ REST）+ AI 应用（RAG + Agent + LoRA）+ 工程（CI eval + OTel）三栖
