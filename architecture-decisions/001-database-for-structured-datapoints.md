# ADR-001: Choice of Database for Structured Logistics Datapoints

**Date:** August 7, 2025
**Status:** Accepted

## 1. Context

Our Multi-Agent System requires a knowledge base to power the `Query_Port_Information` tool. This knowledge base consists of approximately 1,400 highly structured, atomic "datapoints," each a JSON object with rich metadata (e.g., `port_area`, `relevant_entity`, `regulation_category`) and a short, factual text field (`regulation_detail`).

The primary retrieval patterns required by our agent are:
1.  **Faceted Search:** Filtering datapoints based on multiple metadata fields (e.g., "Find all `Requirements` for a `Shipper` at `DEHAM`").
2.  **Keyword Search:** Finding datapoints that contain specific terms (e.g., "VGM").

The chosen solution must be cloud-hosted, offer a generous free tier for MVP development, and provide a simple, first-class integration with our n8n-based tool implementation.

## 2. Decision Drivers

-   **Simplicity and Speed of Implementation:** The solution should minimize development overhead and allow for rapid prototyping.
-   **Alignment with Primary Use Case:** The database must excel at metadata filtering and keyword search, as these are the core retrieval patterns.
-   **Ease of Data Management:** The process of adding, editing, and reviewing datapoints should be as straightforward as possible.
-   **n8n Integration Quality:** A native, well-supported n8n node is strongly preferred over manual `HTTP Request` node configuration.
-   **Cost-Effectiveness:** The free tier must be sufficient for our initial dataset and development/testing API call volume.

## 3. Considered Options

We evaluated four primary options for the knowledge base backend:

1.  **Qdrant (Vector Database):**
    *   *Pros:* Excellent for pure semantic search. Can pre-filter on metadata payloads.
    *   *Cons:* Its core strength (vector search) is our lowest priority use case. Metadata filtering is less intuitive than in traditional databases. The overhead of embedding short, factual texts may not provide significant value. Requires manual `HTTP Request` configuration in n8n.

2.  **Airtable (Cloud Database/Spreadsheet Hybrid):**
    *   *Pros:* Best-in-class user interface for data management. Excellent, native filtering and keyword search capabilities via its API. Has a first-class, officially supported n8n node. Generous free tier is perfect for our MVP.
    *   *Cons:* Not a traditional relational database. Lacks native semantic search capabilities.

3.  **Supabase (Postgres-as-a-Service):**
    *   *Pros:* The power of a full SQL database for complex filtering. Supports full-text search and can be extended with `pgvector` for semantic search, offering a powerful long-term growth path. Has a first-class n8n node. Generous free tier.
    *   *Cons:* Higher initial setup complexity compared to Airtable. UI is more developer-focused.

4.  **Firebase Firestore (NoSQL Document Database):**
    *   *Pros:* Highly scalable, flexible schema. Very good at filtering on document fields. Has a first-class n8n node. Generous free tier.
    *   *Cons:* Keyword search is less powerful than in Postgres or Airtable without integrating an external indexing service (e.g., Algolia), which adds complexity.

## 4. Decision

We have decided to use **Airtable** as the primary database for storing and retrieving our structured logistics datapoints for the project's MVP phase.

## 5. Rationale

Airtable provides the optimal balance of simplicity, power, and cost for our immediate needs.

-   **Directly Aligns with Our Needs:** It is exceptionally strong at the metadata filtering and keyword searching that constitute our primary retrieval patterns. Its spreadsheet-like UI makes managing our ~1,400 datapoints far simpler than any other option.
-   **Fastest Time-to-Value:** The combination of a user-friendly data interface and a first-class, native n8n node means we can implement our structured knowledge retrieval path faster and with less code than any alternative. This allows us to focus our efforts on the agent's logic rather than on database plumbing.
-   **Sufficiently Powerful for the MVP:** While it lacks the long-term scalability of Supabase, its capabilities and free tier limits are more than sufficient to build, test, and demonstrate our complete MAS for the TRA 2026 publication.

This decision prioritizes development velocity and ease of use for the MVP, while keeping more powerful options like Supabase in consideration for future, production-scale iterations of the system.

## 6. Consequences

-   **Positive:**
    -   Development of the `Query_Port_Information` tool's structured path will be significantly accelerated.
    -   The knowledge base will be easy for non-developers to review and maintain.
    -   The n8n workflow for this path will be simpler and more readable.
-   **Negative:**
    -   We will not have native semantic search capability for the structured path in the MVP. We have deemed this an acceptable trade-off, as our datapoints are atomic and factual, reducing the need for semantic interpretation.
    -   If the project scales beyond Airtable's limits in the future, a migration to a more robust backend like Supabase would be required. This is considered a future task and an acceptable risk for the current research phase.