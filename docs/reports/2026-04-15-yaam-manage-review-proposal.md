# TRA ↔ YAAM Integration Feasibility Study (YAAM as Memory Substrate)

Date: 2026-04-15  
Repo: `agentic-scm-tra26` (TRA)

## 0) Executive Summary

TRA currently has **no usable YAAM “memory substrate” API contract** in-repo (no documented CRUD endpoints for L1–L4, no client code, no env configuration beyond a single `YAAM_AGENT_URL` placeholder). The only existing YAAM integration is a **stub HTTP client** that POSTs arbitrary JSON to `YAAM_AGENT_URL` and expects JSON back. (`src/evaluators/agentic_mas_client.py:13`)

As a result:

- **Feasible today (low certainty):** Integrate TRA with YAAM only as a *black-box agent endpoint* (POST a payload, receive a response) — but this **does not satisfy** the refined architecture where TRA explicitly controls L1/L2/L3/L4 writes with metadata.
- **Feasible with changes (recommended):** Define and implement a **YAAM Memory Gateway API** (or direct-store clients) so TRA can perform explicit L1–L4 CRUD/upsert operations with author metadata, trace context, and deterministic provenance.

This proposal documents (1) what the repo actually contains about YAAM, (2) the minimum YAAM API contract TRA needs, (3) a blueprint for reworking `src/evaluators/agentic_mas_client.py` to run TRA as the Brain (LangGraph orchestrator + tools) while using YAAM as Memory, and (4) a concrete modification plan for trace propagation + JSONL error fallback in the benchmark runner.

---

## 1) YAAM API Contract Available to TRA (Repo Evidence)

### 1.1 What’s present

**(A) A single YAAM endpoint environment variable (`YAAM_AGENT_URL`) is referenced only in a stub evaluator client.**

```py
# src/evaluators/agentic_mas_client.py:19-33
url = os.getenv("YAAM_AGENT_URL")
...
api_key = os.getenv("YAAM_AGENT_API_KEY") or None
timeout_s_raw = os.getenv("YAAM_AGENT_TIMEOUT_S") or "60"
```

**(B) The client is “JSON-over-HTTP POST” with only `Content-Type` + optional `Authorization`.**

```py
# src/evaluators/agentic_mas_client.py:47-55
headers = {"Content-Type": "application/json"}
if self._config.api_key:
    headers["Authorization"] = f"Bearer {self._config.api_key}"
req = urllib.request.Request(self._config.url, data=body, headers=headers, method="POST")
```

There is **no** mention of:
- memory-layer CRUD routes (`/memory/l3/...`)
- a gRPC schema
- layer selection (`L1`/`L2`/`L3`/`L4`)
- author metadata
- trace header injection (`traceparent`)

**(C) `.env.example` does not include any YAAM base URL or memory endpoints.**

It includes OpenRouter + node IPs + service ports, but no `YAAM_*` variables. (`.env.example:1-75`)

**(D) The actual benchmark runner (`scripts/run_orchestrator.py`) does not call YAAM at all.**

It calls OpenRouter (OpenAI SDK) and local deterministic tools. (`scripts/run_orchestrator.py:214-266`)

### 1.2 What’s absent (important)

Within this repository, I found **no** documentation or code establishing a YAAM memory CRUD contract:

- no endpoints like `POST /memory/l3/entities`
- no “memory record” schema
- no direct client to Redis/Postgres/Qdrant/Neo4j/Typesense
- no “YAAM Memory Gateway” base URL, auth scheme, or versioning

### 1.3 Feasibility conclusion (Step 1)

Based on current repo contents, **TRA cannot currently implement “Brain controls L1–L4 writes via YAAM”** because the required YAAM API surface is not defined here.

To proceed, you need one of these integration paths:

1) **YAAM Memory Gateway API (preferred):** YAAM exposes explicit memory CRUD/upsert endpoints per layer (HTTP or gRPC), and TRA uses a typed client.
2) **Direct-store integration:** TRA connects directly to Redis/Postgres/Qdrant/Neo4j/Typesense (bypassing a YAAM service), using env vars already present for ports/IPs (but this changes what “YAAM” means operationally).

---

## 2) Required YAAM “Memory Gateway” API (Proposed Contract)

This is a *proposal* (not present in repo today) for the **minimum** contract TRA needs to satisfy “TRA controls what gets saved to which layer, with metadata (agent author)”.

### 2.1 Design goals

- **Layer-explicit:** caller chooses L1/L2/L3/L4 explicitly in each request.
- **Upsert-first:** idempotent writes (safe retries).
- **Provenance-rich:** every record includes `task_id`, `run_id`, `agent_author`, `source_kind`, and trace correlation.
- **Queryable:** L3/L4 support retrieving by `task_id`, entity IDs, tags, etc.
- **Retention:** L1 supports TTL; L2/L3/L4 are persistent.

### 2.2 Suggested endpoints (HTTP REST)

**Base:** `YAAM_BASE_URL` (new env var), versioned under `/v1/`.

**L1 (ephemeral / Redis-like):**
- `PUT /v1/memory/l1/kv/{namespace}/{key}` (upsert with TTL)
- `GET /v1/memory/l1/kv/{namespace}/{key}`
- `DELETE /v1/memory/l1/kv/{namespace}/{key}`

**L2 (structured working knowledge / Postgres):**
- `PUT /v1/memory/l2/evidence/{task_id}` (upsert evidence table JSON)
- `GET /v1/memory/l2/evidence/{task_id}`

**L3 (entities/graph/vector / Qdrant/Neo4j):**
- `POST /v1/memory/l3/entities:upsert`
- `POST /v1/memory/l3/relations:upsert`
- `POST /v1/memory/l3/search` (vector + filters)

**L4 (index/search / Typesense):**
- `POST /v1/memory/l4/documents:upsert`
- `POST /v1/memory/l4/search`

### 2.3 Standard metadata header + body fields

**Headers (trace + correlation):**
- `traceparent` / `baggage` (W3C trace context)
- `x-trace-id` (hex trace id convenience)
- `x-tra-task-id`, `x-tra-run-id`, `x-tra-agent-author`

**Body (minimum):**
```json
{
  "task_id": "…",
  "run_id": "…",
  "agent_author": "planner|solver_1|tool_executor|consensus",
  "timestamp_utc": "2026-04-15T…Z",
  "payload": { "...": "..." },
  "tags": ["benchmark", "scm-cert-bench"],
  "provenance": {
    "source_kind": "llm|tool|human|system",
    "source_ref": "openrouter:model_id|tool:alias|…"
  }
}
```

---

## 3) Agentic MAS Client Blueprint (TRA as Brain, YAAM as Memory)

### 3.1 Repo reality check: LangGraph is not currently available

TRA currently does **not** depend on LangGraph/LangChain. (`pyproject.toml:7-20`)

If the refined architecture requires LangGraph, adding dependencies is a prerequisite:
- add `langgraph` (and any required `langchain-*` libs)
- ensure Phoenix/OpenTelemetry instrumentation works with LangGraph (RFC002 explicitly calls out LangGraph metadata patterns). (`docs/rfcs/002-execution-metrics-telemetry.md:96-114`)

### 3.2 How `src/evaluators/agentic_mas_client.py` should change

Current file is an “external agent endpoint” stub (`YAAM_AGENT_URL`) and does not model memory layers. (`src/evaluators/agentic_mas_client.py:35-71`)

Proposed reframe:

- `AgenticMASClient` becomes **TRA’s local executor** (LangGraph graph runner) that calls:
  - the LLM gateway (OpenRouter/OpenAI SDK) for cognition
  - local deterministic tools from `tools.ACTIVE_TOOLS`
  - YAAM Memory Gateway for explicit memory writes

#### Proposed module layout (within `src/`)

- `src/memory/yaam_client.py`
  - `YAAMConfig.from_env()`
  - `YAAMMemoryClient` with typed methods: `l1_put/get`, `l2_upsert_evidence`, `l3_upsert_entity`, `l4_upsert_document`, etc.
  - trace header injection on every request (see §4.1)

- `src/agentic/graph.py`
  - LangGraph definition (`build_graph(...)`)
  - `GraphState` (task row, messages, evidence, entities, tool history, consensus result)

- `src/evaluators/agentic_mas_client.py`
  - wiring: load task → run graph → return `EvalResult` or (for RFC002 runner) return `raw_response` + `ExecutionMetrics`

### 3.3 Graph (LangGraph) blueprint: nodes + memory writes

#### State object (minimum)

`GraphState` should include:
- `task: TaskRow` (from `src/orchestrator_native_tool_calling.py:19-25`)
- `messages: list[dict]` (chat history)
- `evidence_table_md: str | None` (L2)
- `entities: list[dict]` (L3 entities + metadata)
- `final_answer: str | None`
- `execution_metrics: ExecutionMetrics` (reuse existing schema)
- `artifacts: dict[str, str]` (paths under `outputs/` if you add dumps)

#### Nodes (example)

1) `init_task`
   - Write L1: raw scenario + prompt (as a single document) with TTL
   - Seed initial system/user messages

2) `extract_evidence` (LLM)
   - Ask model to emit Evidence Table (Markdown or JSON)
   - Write L2: normalized evidence payload (structured JSON preferred)

3) `derive_entities` (LLM or deterministic parser)
   - Convert evidence into entity records (ports, rates, dates, capacities, etc.)
   - Write L3: upsert entities + relations with `agent_author="fact_extractor"`

4) `solve_with_tools` (LLM + native tool calling)
   - Reuse the existing walled-garden tool mechanism:
     - tool schemas from `build_tool_registry(list(tools.ACTIVE_TOOLS))` (`scripts/run_orchestrator.py:214`)
     - strict validation + retry loop is already implemented in `run_task` (`src/orchestrator_native_tool_calling.py:294+`)
   - Save:
     - L1: “tool call transcript” (optional TTL)
     - L3: tool outputs as derived facts with provenance `source_kind="tool"`

5) `consensus` (multi-agent)
   - Run N solver branches (e.g., 3) with different “agent_author” identities
   - Choose final via:
     - simple majority on extracted numeric answer, OR
     - LLM judge node (careful: adds cost/variance)
   - Write L2/L3: consensus decision + rationale with `agent_author="consensus"`

6) `index_final` (optional)
   - Write L4: Typesense doc for retrieval (task_id, entities, final answer, tags)

### 3.4 Tools integration (keep existing “walled garden”)

The repo already has a robust, deterministic tool surface and registry builder:

- Tool registry build: `build_tool_registry(list(tools.ACTIVE_TOOLS))` (`scripts/run_orchestrator.py:214`)
- Strict tool-call execution loop: `run_task(...)` (`src/orchestrator_native_tool_calling.py:294+`)

Recommendation: make the LangGraph “tool node” call into a refactored function extracted from `run_task` so you don’t fork the retry logic.

---

## 4) Resilience & Telemetry Update Plan (Specific Code Changes)

This section is a concrete, file-level plan for:

1) Injecting trace context into external calls (LLM + YAAM)
2) Adding a JSONL fallback mechanism that preserves traceback/error details and any best-effort partial outputs

### 4.1 Inject `trace_id` into all external calls (LLM + YAAM)

#### 4.1.1 LLM calls (OpenRouter via OpenAI SDK)

LLM calls are made in `run_task()`:
- Naive path: `src/orchestrator_native_tool_calling.py:313-317`
- Tools path: `src/orchestrator_native_tool_calling.py:336-342`

The installed OpenAI SDK supports per-request headers (`extra_headers`) (verified via local signature inspection).

**Plan:**

1) Add a helper in `src/orchestrator_native_tool_calling.py`:
   - build a `carrier: dict[str, str]`
   - call `opentelemetry.propagate.inject(carrier)`
   - add `x-trace-id=<32-hex>` from `trace.get_current_span().get_span_context().trace_id` when valid

2) Pass `extra_headers=carrier` into every `openai_client.chat.completions.create(...)` call in `run_task`.

**Concrete edit points:**

- Update `src/orchestrator_native_tool_calling.py:315`:
  - add `extra_headers=_trace_headers()`
- Update `src/orchestrator_native_tool_calling.py:336-342`:
  - add `extra_headers=_trace_headers()`

Optional (recommended): also pass OpenAI `metadata={...}` with `task_id`, `run_mode`, `model_id` for provider-side logging.

#### 4.1.2 YAAM calls (Memory Gateway client)

For the current YAAM stub, add trace propagation into request headers:

- `src/evaluators/agentic_mas_client.py:50-55` should include `traceparent`/`baggage` + `x-trace-id`.

**Plan:**
- centralize trace injection in the proposed `src/memory/yaam_client.py`
- use the same `_trace_headers()` helper pattern (or share a utility module)

### 4.2 JSONL Fallback Mechanism (traceback + error + partial raw_response)

#### 4.2.1 Constraint: RFC002 schema is strict

RFC002 specifies the JSONL output schema must have *exactly* the standard keys. (`docs/rfcs/002-execution-metrics-telemetry.md:19-46`)

If downstream tooling depends on this, adding new keys to `outputs/evaluation_results.jsonl` risks breaking consumers.

#### 4.2.2 Proposal: dual JSONL outputs (stable + debug)

Keep:
- `outputs/evaluation_results.jsonl` (RFC002 strict schema; unchanged)

Add:
- `outputs/evaluation_results_debug.jsonl` (new; contains full error/debug info)

**CLI changes (in `scripts/run_orchestrator.py`):**

- Add `--output-jsonl-debug` (default: `outputs/evaluation_results_debug.jsonl`)
- On every task, append a debug row containing:
  - `task_id`, `model_id`, `run_mode`
  - `status`: `OK|ERR`
  - `trace_id` (hex)
  - `error_type`, `error_message`, `traceback`
  - `partial_raw_response` (best-effort)
  - optionally `messages_tail` (last N messages; redact if needed)

**Concrete edit points:**

- In `scripts/run_orchestrator.py:236-253`, in the `except Exception as exc:` block:
  - capture `traceback.format_exc()`
  - do **not** overwrite `raw_response` if a partial exists (see next subsection)
  - append a debug JSONL row with `error_*` fields

#### 4.2.3 Best-effort “partial raw_response”

Today, an exception inside `run_task(...)` yields no partial output to the caller; `scripts/run_orchestrator.py` then forces `raw_response=""`. (`scripts/run_orchestrator.py:248-251`)

To preserve partial outputs, implement one of these:

**Option A (minimal, immediate):**
- In the exception handler, set `partial_raw_response = raw_response` (may be empty often).
- Still valuable because you retain traceback/error details reliably.

**Option B (recommended, modest refactor):**
- Refactor `run_task` to return a richer object:
  - `raw_response`
  - `execution_metrics`
  - `debug_last_assistant_text`
  - `debug_messages_tail`
  - `error_code` (e.g., `MAX_TOOL_CYCLES`, `UNKNOWN_TOOL`, `OPENAI_EXCEPTION`)

This avoids swallowing “last good” assistant content when the loop terminates early (`MAX_TOOL_CYCLES`, unknown tool, etc.).

#### 4.2.4 Bonus resilience (recommended)

`scripts/run_orchestrator.py` currently aborts the whole run if Phoenix tracing init fails. (`scripts/run_orchestrator.py:201-206`)

For unattended runs, consider adding:
- `--no-tracing` flag OR “continue without tracing if init fails”

---

## 5) Action Plan (What to do next)

1) **Decide integration path**
   - If YAAM is a service: implement the YAAM Memory Gateway API (or obtain its existing contract).
   - If YAAM is the storage stack: implement direct clients in TRA and treat YAAM as infra, not an API.

2) **Create typed YAAM client**
   - Add `src/memory/yaam_client.py` with layer-explicit CRUD/upsert methods and trace header propagation.

3) **Introduce LangGraph (if required)**
   - Add dependencies and scaffold `src/agentic/graph.py`.
   - Ensure tracing works with RFC002 semantics (use invocation metadata).

4) **Update benchmark runner telemetry + resilience**
   - Add `extra_headers` trace propagation into LLM calls inside `src/orchestrator_native_tool_calling.py`.
   - Add dual JSONL outputs (RFC002 stable + debug JSONL with traceback/error).

