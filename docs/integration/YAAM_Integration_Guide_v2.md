# TRA Integration Guide: YAAM Semantic Gateway v2

**Target Audience:** Development team of `agentic-scm-tra26` (The LangGraph Orchestrator).
**Status:** Active / Production-Ready

## 1. Overview: The "Spinal Cord" Paradigm
YAAM v2 acts as a **Semantic Gateway**. The TRA Orchestrator (The Brain) should **NOT** generate vector embeddings or Cypher queries. 
TRA simply sends Natural Language intents and raw text artifacts. YAAM handles all internal routing, LLM translations, graph extractions, and indexing across Redis, Postgres, Qdrant, Neo4j, and Typesense.

## 2. Connection & Telemetry (CRITICAL)

### Base URL
All endpoints are prefixed with: `/v2/memory`

### Distributed Tracing (OpenTelemetry)
To maintain the "Fidelity Trace" across the TRA and YAAM boundary in Arize Phoenix, **TRA must inject the W3C trace context header into every request**. YAAM natively extracts this to link its internal LLM/Database spans to your agent's reasoning loop.

**Required Header:**
* `traceparent`: e.g., `00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01`

*(Note: The `metadata.trace_id` field has been deprecated in v2 schemas. Use HTTP headers).*

## 3. API Endpoints & Contracts

Every request requires a `session_id` to strictly isolate Multi-Agent executions, and an `agent_id` for provenance tracking.

### L1: Active Context (Turns)
**Purpose:** Ephemeral scratchpad for intermediate agent reasoning.
* **POST** `/v2/memory/l1/turns`
  ```json
  {
    "session_id": "string",
    "turn_id": "string",
    "role": "system | user | assistant",
    "content": "string"
  }
  ```

### L2: Working Memory (Facts)
**Purpose:** Shared whiteboard for agents within the same session.
* **POST** `/v2/memory/l2/facts`
  ```json
  {
    "session_id": "string",
    "task_id": "string",
    "agent_id": "string",
    "action": "store | retrieve", 
    "content": "Fact text (Required if action=store)"
  }
  ```
  *(Returns a list of facts if action=retrieve).*

### L3: Episodic Memory (Assimilate & Query)
**Purpose:** Long-term vector and knowledge graph storage. YAAM handles entity extraction and embedding generation internally.
* **POST** `/v2/memory/l3/assimilate`
  ```json
  {
    "session_id": "string",
    "agent_id": "string",
    "text_to_assimilate": "Raw natural language text/event",
    "domain_tags": ["string"]
  }
  ```
* **POST** `/v2/memory/l3/query`
  ```json
  {
    "session_id": "string",
    "agent_id": "string",
    "nl_query": "Natural language question",
    "top_k": 3,
    "filters": {}
  }
  ```
  *(Returns an array of results, each containing a `provenance` block specifying which agent originally assimilated the knowledge).*

### L4: Semantic Memory (Finalize)
**Purpose:** Storing the final verified artifact of the MAS consensus for full-text search.
* **POST** `/v2/memory/l4/finalize`
  ```json
  {
    "task_id": "string",
    "session_id": "string",
    "title": "Consensus Report Title",
    "final_artifact": "The complete markdown/text artifact",
    "consensus_metadata": { "votes": 3, "disagreements": "none" }
  }
  ```

## 4. Error Handling Expectations
When calling YAAM v2, the TRA HTTP client should be prepared to handle:
* **HTTP 502 Bad Gateway:** YAAM's internal LLM failed (e.g., OpenRouter timeout during Cypher generation). TRA agents should catch this and trigger a retry/backoff mechanism.
* **HTTP 501 Not Implemented:** The specific backend database (e.g., Qdrant/Neo4j) is not spun up or configured in the YAAM `.env`.