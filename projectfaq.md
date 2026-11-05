# FlowDesk — Project FAQ

> Detailed answers to deep technical questions about architecture, design decisions, failure modes, and deployment. All answers are grounded in the actual codebase.

---

## Table of Contents

- [Overview / Walkthrough](#overview--walkthrough)
- [Architecture](#architecture)
- [Why This, Not That](#why-this-not-that)
- [Data & Correctness](#data--correctness)
- [Failure Modes](#failure-modes)
- [Deployment / Ops](#deployment--ops)
- [Hardest Bug](#hardest-bug)

---

## Overview / Walkthrough

### Q: What's the actual customer query lifecycle — user asks something, then what, step by step, until they get an answer?

1. **HTTP Ingress** — The user types a message into the Next.js frontend. The `useStreamedChat` hook sends a `POST /api/chat` request to the Next.js API route, which proxies it to the FastAPI backend at `/chat` (or `/chat/stream` for SSE).

2. **Gateway** — `gateway/main.py` receives the request, parses `query` and `thread_id`, and constructs the initial `SupportState`:
   ```python
   {"messages": [HumanMessage(content=query)], "intent": "", "retrieved_context": [], "confidence": 0.0, "retry_count": 0}
   ```
   It then calls `graph.invoke(state, config={"configurable": {"thread_id": thread_id}})`.

3. **Router Node** — The first node to execute is `route_intent` in `orchestrator/agents/router.py`. It sends the query to **Groq Llama 3.3-70b** with a structured output schema (`IntentClassification`) and gets back one of: `faq`, `action`, `complex`, or `out_of_scope`. This classification is written into `state["intent"]`.

4. **Conditional Edge** — `route_after_router()` in `orchestrator/graph.py` reads `state["intent"]` and routes to the correct next node: `rag_agent`, `action_agent`, or `escalation_agent`.

5. **Agent Execution** (e.g., RAG path):
   - `rag_agent_node` calls `hybrid_search(query, top_k=N)` which runs **dense** (Pinecone) and **sparse** (BM25) searches concurrently, merges results with a weighted average after min-max normalization.
   - The merged candidates are passed to `rerank(query, candidates)` — the cross-encoder scores every `(query, chunk)` pair and returns the top-N by relevance.
   - The reranked chunks are joined into `context_str` and injected into a prompt for the LLM (Groq for short/first-attempt, Gemini for retry/multi-turn).
   - The LLM returns structured output: `{"answer": "...", "confidence": 0.85}`.
   - `compute_unified_confidence()` blends retrieval score + LLM self-confidence + groundedness (token overlap) into a final `confidence` float.

6. **Self-Correction Loop** — `route_after_rag()` checks: `if confidence < 0.6 and retry_count < 2 → return "rag_agent"`. On retry, `top_k` doubles and Gemini is used instead of Groq.

7. **Telemetry** — `log_telemetry()` writes the query, answer, scores, and retrieved chunks to PostgreSQL (Supabase) or SQLite locally.

8. **Response** — The final `AIMessage` bubbles back through LangGraph → gateway → SSE stream → frontend. The gateway's `streaming.py` simulates token-by-token streaming by yielding the answer string in chunks even though the LLM returned it as a complete JSON object (due to structured output / tool-calling constraints).

---

### Q: What "multiple workflows" does it automate — give me 2-3 concrete examples of query types it handles differently?

**Workflow 1: FAQ / Knowledge Base Query (`intent = "faq"`)**
> *"What is your return policy for damaged items?"*

The router classifies this as `faq`. The RAG agent runs hybrid retrieval against the ingested support docs (e.g., `return_refund_policy.md`), reranks the chunks, and generates a grounded answer with citations. If confidence < 0.6, it retries with a wider search window and Gemini. The user gets a precise, document-grounded answer with no human involved.

**Workflow 2: Account Action (`intent = "action"`)**
> *"I need to reset my password."*

The router classifies this as `action`. The Action Agent (`action_agent.py`) bypasses vector retrieval entirely — it pre-loads the relevant policy docs (`password_security.md`, `account_management.md`) at module load time and feeds them directly as context to Groq. The model returns structured step-by-step instructions. This path is faster because it skips the embedding/Pinecone round-trip.

**Workflow 3: Complex / Emotional Escalation (`intent = "complex"`)**
> *"I've been waiting 3 weeks for my refund and nobody is helping me. This is completely unacceptable."*

The router detects frustration/anger signals and classifies this as `complex`. The Escalation Agent logs the conversation reason to the `escalations` table in PostgreSQL and returns a human-handoff response (e.g., "I'm connecting you with a specialist"). No retrieval or generation complexity needed — the system recognizes it can't resolve this autonomously and escalates immediately.

---

## Architecture

### Q: Draw the LangGraph graph for me — what are the nodes, what are the edges, where do decisions/branches happen?

```
                    ┌─────────────────────────────────────────────┐
                    │          LangGraph StateGraph                │
                    │                                             │
   ENTRY ──────────►│  [router]                                   │
                    │      │                                      │
                    │      │  route_after_router()                │
                    │      ├── intent == "faq"      ──►  [rag_agent] ──┐
                    │      ├── intent == "action"   ──► [action_agent] ─┤──► END
                    │      └── intent == "complex"  ──► [escalation_agent] ──► END
                    │                                              │
                    │  [rag_agent] ◄─────────────────────────────┘
                    │      │                                      │
                    │      │  route_after_rag()                   │
                    │      ├── confidence < 0.6 AND retry < 2 ──► [rag_agent] (loop)
                    │      └── otherwise ──────────────────────► END
                    └─────────────────────────────────────────────┘
```

**Nodes:**

| Node | File | Role |
|------|------|------|
| `router` | `orchestrator/agents/router.py` | LLM-powered intent classifier |
| `rag_agent` | `orchestrator/agents/rag_agent.py` | Hybrid retrieval + LLM generation |
| `action_agent` | `orchestrator/agents/action_agent.py` | Direct doc lookup + tool-calling LLM |
| `escalation_agent` | `orchestrator/agents/escalation_agent.py` | Human handoff + DB logging |

**Edges:**
- `START → router` (set via `graph.set_entry_point("router")`)
- `router → {rag_agent | action_agent | escalation_agent}` — **conditional edge** via `route_after_router()`
- `rag_agent → {rag_agent | END}` — **conditional self-loop** via `route_after_rag()`
- `action_agent → END` — unconditional
- `escalation_agent → END` — unconditional

**Decision points:**
1. After `router`: branches on `state["intent"]`
2. After `rag_agent`: branches on `state["confidence"] < 0.6 AND state["retry_count"] < 2`

---

### Q: Why LangGraph over a simple LangChain chain, or just hand-rolled if/else orchestration in Python?

A plain LangChain chain is a linear DAG — input goes in, steps execute left to right, output comes out. There's no native mechanism for:

- **Cycles / self-correction**: The RAG retry loop (`rag_agent → rag_agent`) requires the graph to route back to a node it already visited. A chain cannot do this without explicit external Python while-loops that live outside the abstraction.
- **Shared mutable state**: `SupportState` (`messages`, `intent`, `retrieved_context`, `confidence`, `retry_count`) is typed and persisted across all nodes. Every node reads/writes from one canonical object. In a chain, threading state between steps requires careful return-value plumbing or mutable closure hacks.
- **Persistent conversation memory (Checkpointers)**: LangGraph's `Checkpointer` interface (PostgreSQL in prod, SQLite locally) snapshots graph state after every node, enabling multi-turn conversations keyed by `thread_id`. Reproducing this in hand-rolled Python would require re-implementing a mini state machine with serialization.
- **Deterministic branching**: Customer support needs predictable paths (not open-ended agent reasoning). `add_conditional_edges` encodes the routing logic explicitly in the graph definition, making it inspectable and testable — something hand-rolled if/else collapses into tangled function call stacks.

In short: LangGraph gives you the control of if/else orchestration but with state persistence, cycle support, and structured observability built in.

---

### Q: Is there a supervisor/router agent, or is routing rule-based before agents even get involved?

It's an **LLM-powered router agent** — not rule-based. The `route_intent` function in `orchestrator/agents/router.py` instantiates a Groq Llama 3.3-70b model with `with_structured_output(IntentClassification)` and asks it to classify the intent. The routing decision is made by the LLM, not by regex patterns or keyword matching.

The result (`faq`, `action`, `complex`, `out_of_scope`) is written to `state["intent"]`. Then `route_after_router()` — a pure Python function in `graph.py` — reads that string and returns the next node name. So the *branching mechanism* is a simple Python string comparison, but the *classification* that drives it is an LLM call.

This hybrid approach (LLM classification → deterministic graph edges) is intentional: the LLM provides natural language understanding, but the graph controls what can actually happen next.

---

### Q: What's stored in graph "state" as it moves node to node?

Defined in `orchestrator/state.py`:

```python
class SupportState(TypedDict):
    messages: Annotated[list, operator.add]   # Full conversation history (HumanMessage/AIMessage)
    intent: str                                # "faq" | "action" | "complex" | "out_of_scope"
    retrieved_context: list                    # List of raw text strings from reranked chunks
    retrieved_chunks: list                     # List of {source, score} dicts for telemetry
    confidence: float                          # Unified confidence score [0.0, 1.0]
    retry_count: int                           # Number of RAG retries so far
```

Key details:
- `messages` uses `operator.add` as the reducer — each node appends to the list rather than replacing it, preserving full conversation history.
- `retrieved_context` and `retrieved_chunks` are populated by the RAG agent and can be read by subsequent nodes (though currently only RAG writes to them).
- `confidence` and `retry_count` are the inputs to the self-correction decision.
- The checkpointer serializes this entire dict to the database after each node, enabling conversation resumption across requests.

---

## Why This, Not That

### Q: Why Gemini for one part and Groq for another — what's the actual division of labor?

The split is **latency vs. capability**, and it's enforced at the code level in `rag_agent.py`:

```python
if is_short and not is_multi_turn and retry_count == 0:
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)   # Fast path
else:
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)  # Power path
```

| | Groq (Llama 3.3-70b) | Google Gemini (Flash/Pro) |
|---|---|---|
| **Used for** | Router (all queries), RAG (short, first-attempt), Action agent | RAG (retries, multi-turn, long queries) |
| **Why** | Groq's LPU architecture delivers extreme TTFT (~100-200ms). The router runs on every single query — it must be invisible latency-wise. | Large context window handles the expanded `top_k` retrieval on retry. Strong "second opinion" reasoning for harder queries. |
| **Tradeoff** | Less capable on long-context / complex reasoning | More expensive and slightly slower TTFT |

The router **always** uses Groq because even a 300ms routing delay would be perceptible. Gemini is reserved for cases where accuracy matters more than speed.

---

### Q: Why Pinecone (managed, paid) over a self-hosted vector store for this specific project?

This is documented explicitly in `CHANGELOG.md` (Tradeoff 2):

**The core constraint is Cloud Run's ephemeral, stateless instances.** Cloud Run scales to zero and restarts containers on demand. Local vector stores (FAISS, Chroma) store their index on the container's filesystem, which is **wiped on every scale-to-zero event**. Every cold start would require re-ingesting all documents — adding minutes of startup time and making the system unusable.

Alternatives considered:
- **FAISS**: Free, in-process speed, but stateless — would require persistent volume on Cloud Run (complex orchestration).
- **Qdrant self-hosted**: Would require running a separate always-on instance, adding infra cost and ops overhead.
- **Pinecone Serverless**: Adds ~50–100ms network latency per query, but the index persists forever externally. Cloud Run instances are completely stateless, enabling infinite horizontal scaling with zero storage concerns.

For this project's constraint (serverless deployment, small team, no dedicated infra ops), Pinecone's managed nature was the right tradeoff.

---

### Q: Why hybrid retrieval (vector + keyword) instead of pure vector search — give me a real query type where pure vector search would fail?

**Example: Error code lookup**
> *"I keep getting error ERR-409 when trying to checkout."*

Pure vector search embeds this into a semantic space and finds documents about "checkout errors" or "payment issues" — but it may rank a generic "troubleshooting tips" document higher than the specific `ERR-409` doc if those two chunks happen to be semantically similar (both discuss checkout). The exact string `"ERR-409"` becomes diluted in the embedding.

BM25's TF-IDF scoring gives massive weight to rare, exact tokens like `ERR-409` or product SKUs like `SKU-XR7293`. These tokens appear infrequently in the corpus, so their IDF weight is high — making BM25 precision-recall excellent for exact-match queries.

**Other cases where BM25 catches what vectors miss:**
- Product names with unusual spelling (e.g., `"FlowDesk ProMax v2.1"`)
- Order numbers, tracking IDs, version strings
- Queries with negations that embeddings often ignore (e.g., "not the premium plan")

The merge uses equal `dense_weight=0.5, sparse_weight=0.5`, so a chunk that scores in both methods gets a boosted combined score — high recall across both semantic and lexical query types.

---

### Q: How does reranking work — is it a cross-encoder, an LLM-as-reranker, or a simpler heuristic? What's the latency cost of adding it?

It's a **cross-encoder** (`cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers`), implemented in `retrieval/reranker.py`.

**How it works:** A bi-encoder (like the one used for Pinecone embeddings) encodes query and document *separately* into vectors and compares them. A cross-encoder takes the *concatenated pair* `[query, document]` as a single input and outputs a single relevance score. This joint attention over both texts makes it dramatically more accurate at distinguishing truly relevant chunks from superficially similar ones.

**Why not LLM-as-a-judge?** Passing 20 chunks to an LLM asking "rank these by relevance" would add 1–3 seconds of latency and cost several LLM calls per query. The MiniLM cross-encoder is a ~22M parameter model that runs locally (baked into the Docker image), scoring all candidates in ~50–100ms on CPU. From the CHANGELOG:

> "A Cross-Encoder model is a lightweight neural network trained specifically to score (query, document) pairs. It provides massive relevance improvements with minimal latency overhead."

**Latency cost:** ~50–100ms on CPU for 20 candidates. The model is pre-loaded at container startup (baked into the Docker image during build via `RUN python -c "from sentence_transformers import CrossEncoder..."`), so there's no download overhead at inference time.

---

## Data & Correctness

### Q: Walk me through your PostgreSQL logging schema — what gets logged per query?

Five tables in `db/models.py`:

```
Conversation (id UUID, created_at)
    └─► Message (id, conversation_id, role, content, created_at)
              ├─► RetrievalLog (id, message_id, query, retrieved_chunks JSON, rerank_scores JSON)
              └─► ConfidenceScore (id, message_id, retrieval_score, llm_confidence, groundedness, final_score)

Escalation (id, conversation_id, reason, created_at)
Feedback (id, conversation_id, message_content, response_content, rating ["up"/"down"], created_at)
```

Per query, the system logs:
- The raw user query and the generated answer (in `Message`)
- The exact chunks retrieved and their rerank scores (in `RetrievalLog`)
- The three-component confidence breakdown — `retrieval_score`, `llm_confidence`, `groundedness` — plus the `final_score` (in `ConfidenceScore`)
- If escalated: the reason text (in `Escalation`)
- If user gives feedback: thumbs up/down with the full message/response content (in `Feedback`)

---

### Q: How do you use those logs — is there an actual review/audit process, or is it write-only right now?

**Honestly: the logging infrastructure is write-complete, but the review/audit tooling is currently write-mostly.**

The `evaluation/` directory contains `eval_harness.py` and `eval_retrieval.py` for benchmarking retrieval accuracy, but there's no automated alerting system that triggers on logged low-confidence queries. The `Feedback` table captures explicit user thumbs-up/down signals, which is the most actionable signal — but surfacing it currently requires a manual SQL query.

In production this data would feed:
1. A dashboarding layer (Metabase/Grafana) querying `confidence_scores` for drift detection
2. A human review queue triggered when `final_score < 0.4` — queries where the system was most uncertain
3. Fine-tuning or retrieval improvement cycles using `retrieval_logs` to identify systematic misses

The schema is intentionally designed to support all of the above; the operational workflows to consume it are the next build phase.

---

### Q: Explain your confidence-scoring framework precisely — is it the LLM self-reporting confidence, a separate classifier, or retrieval similarity scores?

Implemented in `evaluation/confidence_scorer.py`, the `compute_unified_confidence()` function blends **three signals**:

1. **`retrieval_score`** — The top reranker score from the cross-encoder, normalized to [0, 1]. This measures: did we actually find something relevant? A score near 0 means the corpus had nothing useful for this query.

2. **`llm_confidence`** — The LLM self-reports a confidence float in its structured output (`RAGResponse.confidence`). This is the least reliable component — LLMs are known to be miscalibrated — but it captures the model's own assessment of whether the context was sufficient to answer the question.

3. **`groundedness`** — A token overlap metric between the generated answer and the retrieved context. If the LLM's answer contains words/phrases absent from the context, the groundedness component pulls `final_score` down. High overlap = answer is grounded; low overlap = suspicious.

These three are combined into a single `final_score` (the exact weighting formula is in `confidence_scorer.py`). The result is what `route_after_rag()` checks against the 0.6 threshold.

The LLM self-reporting alone would be unreliable. The retrieval score alone wouldn't catch a case where docs were retrieved but ignored. The groundedness check is the "hallucination canary" — it's imperfect (synonyms/paraphrases score low unfairly) but provides a signal no other component captures.

---

### Q: Below the confidence threshold — what actually happens? Does it escalate to a human, retry with different retrieval params, or just apologize?

From `orchestrator/graph.py`:

```python
def route_after_rag(state: SupportState) -> str:
    confidence = state.get("confidence", 1.0)
    retry_count = state.get("retry_count", 0)

    if confidence < 0.6 and retry_count < 2:
        return "rag_agent"   # retry with wider search / model switch
    return END
```

**Attempt 1 fails (confidence < 0.6, retry_count = 0):**
- Routes back to `rag_agent`
- `top_k` **doubles** (`retrieval_top_k * 2` in `_perform_retrieval`)
- Model switches from **Groq → Gemini** (larger context window handles the wider retrieval)
- `retry_count` increments to 1

**Attempt 2 fails (confidence < 0.6, retry_count = 1):**
- Routes back to `rag_agent` again
- Same widened search, same Gemini model
- `retry_count` increments to 2

**Attempt 3 (retry_count = 2):**
- Regardless of confidence, `route_after_rag` returns `END`
- The system returns whatever answer it has, even if low-confidence
- The telemetry is logged with the low `final_score` for human review

> **Known gap:** There is currently no automatic human escalation triggered by chronic low confidence. The retry ceiling prevents infinite loops, but the failure mode is "best-effort low-confidence answer + telemetry log" rather than "route to escalation agent." Adding a `→ escalation_agent` branch after 2 failed retries is a planned improvement.

---

## Failure Modes

### Q: Pinecone has a slow response or times out — does the whole pipeline hang, fail gracefully, or fall back to keyword-only?

**It fails gracefully to sparse-only.** In `retrieval/hybrid_retriever.py`:

```python
try:
    dense_results = dense_search(...)
    logger.info("Dense search returned %d results", len(dense_results))
except Exception as e:
    logger.warning("Dense search failed (falling back to sparse-only): %s", e)
    # dense_results remains []
```

If Pinecone times out or throws any exception, `dense_results` stays empty. `merge_and_dedupe([], sparse_results)` is called with only sparse results — BM25 still runs and returns keyword-matched chunks. The system degrades gracefully: accuracy on semantic queries drops, but exact-match and keyword queries still work. The user gets an answer; they just might not know it was sparse-only.

There is **no explicit timeout guard** on the Pinecone call itself — if Pinecone hangs indefinitely rather than throwing, the pipeline would hang too. Adding an `asyncio.wait_for` or `requests.Timeout` around the embedding + Pinecone call is a known gap.

---

### Q: Gemini or Groq has an outage or rate-limits you — what's your fallback? Do you have a secondary model?

**Groq outage:** The router and action agent use Groq exclusively. If Groq is down, both those nodes would throw. There is no automatic failover to a secondary model for the router — it would surface as a 500 error to the user.

**Gemini outage:** The RAG retry path and multi-turn path use Gemini. If Gemini is unavailable during a retry, the retry itself would fail.

**Rate limiting (the real war story):** The most painful failure mode encountered was the **50-second frozen request** (documented in CHANGELOG Issue 8): Gemini Free Tier hit its 20 req/day limit, the `google-genai` SDK silently entered exponential backoff (8s → 16s → 33s → 42s) instead of failing fast, and the user saw a 50-second hang.

**Current mitigation:** Ensuring retrieval succeeds (correct `PINECONE_INDEX_NAME`, BM25 index in image) means Groq answers with high confidence on the first attempt, entirely bypassing the Gemini fallback. The rate-limit issue only manifested because retrieval was broken, forcing constant Gemini retries.

**True fix needed:** An explicit `timeout` on LLM calls and a secondary model registration (e.g., try Groq first, catch `RateLimitError`, try Gemini, catch `RateLimitError`, return graceful degradation message).

---

### Q: The graph enters a loop — do you have a max-iteration guard? What happens if you don't?

**Yes, explicitly.** The self-correction logic has a hard ceiling of 2 retries:

```python
if confidence < 0.6 and retry_count < 2:
    return "rag_agent"
return END
```

After `retry_count = 2`, `route_after_rag` always returns `END` regardless of confidence. The graph **cannot loop more than 3 total RAG executions** (initial + 2 retries). There is no possibility of an infinite RAG cycle.

The router → escalation → router cycle doesn't exist architecturally: `action_agent` and `escalation_agent` both have unconditional edges to `END`. The only node with a self-loop edge is `rag_agent`, and it's guarded.

LangGraph also has a `recursion_limit` parameter (default 25 steps) that would catch any accidental cycles — but in practice the explicit `retry_count < 2` guard fires first.

---

### Q: Cost — every query hits an LLM (maybe twice) plus a reranker — what's your rough cost per query, and how would you cut it 10x?

**Rough cost estimate (current):**

| Component | Per-query cost |
|---|---|
| Groq Llama 3.3-70b (router) | ~$0.00009 (tiny input, ~100 tokens) |
| Gemini embeddings (1 query vector) | ~$0.000025 |
| Cross-encoder reranker | $0 (local CPU inference) |
| Groq Llama 3.3-70b (RAG generation, short path) | ~$0.0003–0.001 |
| PostgreSQL logging write | negligible |
| **Total (happy path, no retry)** | **~$0.0005–0.001** |

Retry path adds another Gemini generation call (~$0.001–0.003 depending on context size).

**How to cut it 10x:**

1. **Cache embeddings**: The same query is often asked repeatedly. Cache the embedding vector keyed by query hash — eliminates the embedding API call for repeat queries.
2. **Cache full responses**: For high-frequency FAQ queries (e.g., "what is your return policy?"), cache the `(query_hash → answer, confidence)` at the gateway level with a TTL. Bypasses all retrieval and LLM calls.
3. **Smaller router model**: Replace Groq Llama 3.3-70b for routing with a fine-tuned classifier (a tiny BERT or even a logistic regression on embeddings) — intent classification doesn't need a 70B model.
4. **Shrink `top_k`**: Currently retrieves more chunks than needed. Tighter `top_k` = fewer tokens in the LLM prompt = lower cost.
5. **Switch to Groq exclusively**: Remove Gemini from the retry path, use Groq for everything. Lower per-token cost, slightly lower quality on complex retries.

---

### Q: Hallucination — retrieval returns nothing relevant but the LLM answers anyway — how does your system prevent or catch that?

Two mechanisms:

1. **Groundedness check in `compute_unified_confidence()`**: The token overlap between the answer and retrieved context is computed. If the LLM generates an answer with words/phrases absent from the context, the groundedness component pulls `final_score` down. A low `final_score` triggers the retry loop.

2. **Prompt engineering with explicit instruction**: The RAG agent's prompt says:
   > *"Answer the user's question based ONLY on the following context. If the context does not contain the answer, say 'I don't know' and give a low confidence score (e.g. 0.0)."*

   If `retrieved_context` is empty or irrelevant, a compliant LLM will return `"I don't know"` with `confidence = 0.0`. That triggers a retry. After 2 retries, if still no context, the system returns `"I don't know"` to the user rather than a hallucinated answer.

**Limitation:** Both mechanisms are heuristic. A confident-sounding hallucination that happens to reuse words from the context would pass the groundedness check. The system reduces hallucination risk; it does not eliminate it.

---

## Deployment / Ops

### Q: Walk me through the actual GitHub Actions pipeline — what triggers on push, what's the build step, how does it reach Cloud Run?

From `.github/workflows/ci-cd.yml`, the pipeline triggers on every push to `main` and runs a **single job** (`build-test-deploy`) with these steps in order:

1. **Checkout** — `actions/checkout@v4`
2. **Install uv** — `pip install uv`
3. **Sync dependencies** — `uv sync --frozen` (installs exact versions from `uv.lock`)
4. **Lint** — `uv run ruff check .` (fails fast on style/type errors)
5. **Test** — `uv run pytest` with dummy API keys injected via env vars (real API calls are mocked/skipped)
6. **Authenticate to GCP** — `google-github-actions/auth@v2` using `GCP_SA_KEY` secret
7. **Set up Cloud SDK** — `google-github-actions/setup-gcloud@v2`
8. **Configure Docker for GCP** — `gcloud auth configure-docker gcr.io`
9. **Build & Push image** — `gcloud builds submit --config cloudbuild.yaml` (Cloud Build builds the multi-stage Dockerfile and pushes to `gcr.io/{PROJECT_ID}/support-gateway`)
10. **Deploy to Cloud Run** — `gcloud run deploy support-gateway` with:
    - `--memory 2Gi` (required for PyTorch/sentence-transformers)
    - `--cpu-boost` (accelerates cold start)
    - `--timeout 120s`
    - `--min-instances 0` (scales to zero)
    - `--max-instances 4`
    - All secrets injected as environment variables

Total pipeline time: ~4–6 minutes (Cloud Build is the longest step).

---

### Q: Cloud Run scales to zero by default — does that hurt here (cold start latency for a customer-facing chat)? How did you handle it?

**Yes, it hurts. Cold starts are the biggest UX risk in this deployment.**

The cold start sequence for this service:
1. Container pulls from GCR (~10–15s)
2. Python imports — including `sentence-transformers` which loads PyTorch (~5–10s)
3. Cross-encoder model loads from the baked-in Docker layer (~2–3s)
4. FastAPI starts, Uvicorn begins listening

Total cold start: **~20–30 seconds** in the worst case. A user hitting a cold instance sees a 20–30 second delay before their first response, which is unacceptable for chat.

**Mitigations applied:**
- `--cpu-boost` flag: Cloud Run temporarily allocates extra CPU during startup to accelerate PyTorch initialization.
- `--timeout 120s`: Gives the container enough time to complete the cold start without the health check killing it.
- Model pre-baking in Dockerfile: `RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"` downloads and caches the model at image build time, eliminating the HuggingFace download at runtime. (Documented in CHANGELOG Issue 2.)

**What wasn't done (known gap):** Setting `--min-instances 1` would keep one instance always warm, eliminating cold starts entirely. It costs ~$10–15/month to keep one 2Gi Cloud Run instance always alive — a reasonable production cost but skipped here since this is a demo deployment.

---

### Q: How do you roll back a bad deploy? Have you actually had to do it?

**Mechanism:** Cloud Run maintains a full revision history. Rolling back is:
```bash
gcloud run services update-traffic support-gateway \
  --to-revisions support-gateway-XXXXXXX=100 \
  --region us-central1
```
Traffic is shifted instantly to the previous revision with zero downtime.

Alternatively, reverting the commit in Git and pushing to `main` triggers the CI/CD pipeline which deploys the reverted code as a new revision.

**Have we needed it?** Not for a traffic-shift rollback, but the equivalent of a rollback was performed several times during the debugging phase (CHANGELOG Issues 1–8) — pushing fix commits and redeploying. The most notable was the **50-second frozen request** (Issue 8), where fixing the `PINECONE_INDEX_NAME` env var and committing `bm25_index.pkl` constituted an "emergency fix" deploy.

---

## Hardest Bug

### Q: What's the single hardest bug you hit building FlowDesk, and how did you track it down?

**The 50-Second Frozen Request (CHANGELOG Issue 8)** — a cascading failure across three completely different systems that was diagnosed entirely from logs.

**Symptom:** Requests to `/api/chat` hung for ~50 seconds and returned poor, hallucinated answers. No exceptions were thrown. No timeouts were raised.

**Root cause — three bugs stacked on top of each other:**

1. **Pinecone 404**: The deployed Cloud Run instance was missing `PINECONE_INDEX_NAME` in its environment variables. It fell back to the default index name `support-docs`, but the actual index was `support-docs-flowdesk`. Every dense search call returned a 404 silently (the exception was caught by the graceful degradation) — `dense_results = []`.

2. **Missing BM25 index**: `bm25_index.pkl` was in `.gitignore`, so it was never committed and never made it into the Docker image. Sparse search also failed silently — `sparse_results = []`.

3. **Gemini SDK infinite retry**: With zero retrieved context, `final_confidence = 0.0`. The self-correction loop triggered, switched to Gemini, and called the Gemini API. The Gemini Free Tier API key had hit its 20 requests/day limit (HTTP 429). The `google-genai` SDK's built-in retry logic caught the 429 and started exponential backoff: 8s → 16s → 33s → 42s — **with no maximum retry limit configured**. This manifested as the service appearing to hang.

**How it was tracked down:** The key insight came from reading Cloud Run structured logs in chronological order. The logs showed:
- `"Dense search failed (falling back to sparse-only)"` — pointed to Pinecone
- `"Sparse search failed"` — pointed to missing BM25 index
- A 50-second gap with no log lines — pointed to the SDK swallowing the 429 silently in a retry loop

**The fix:** Two commits: (1) removed `bm25_index.pkl` from `.gitignore` and committed the file, (2) added `PINECONE_INDEX_NAME=support-docs-flowdesk` to Cloud Run env vars. With retrieval working, Groq answers on the first attempt with high confidence, Gemini never gets invoked, and the 429 retry loop is never entered.

**Why it was hard:** Each of the three bugs was individually explainable and had graceful fallback code. The problem only manifested because all three failed simultaneously — the graceful degradation of the first two pushed load onto the third, which had a latent time-bomb in the SDK's retry behavior. No single component was "broken" in isolation.

It also perfectly illustrates the risk of **silent graceful degradation**: the `except Exception: logger.warning(...)` blocks in the retriever are a double-edged sword. They make the system resilient under partial failures, but they also hide the root cause of cascading failures unless you read every log line in sequence.

---

*Generated from codebase analysis of FlowDesk v2.0.0 — see [README.md](README.md) and [CHANGELOG.md](CHANGELOG.md) for full context.*
