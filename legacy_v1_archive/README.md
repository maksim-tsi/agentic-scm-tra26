# Agentic Logistics Framework for TRA 2026

This repository contains the full implementation of the LLM-powered Multi-Agent System (MAS) for logistics decision support, as developed for our publication at the **Transport Research Arena (TRA) 2026** conference.

## 1. Abstract

The digitalization of Supply Chain Management faces a paradox: Large Language Models (LLMs) offer unprecedented reasoning capabilities but are notoriously unreliable for the precise quantitative analysis and real-time data retrieval that underpins logistics. This project presents a resilient and scalable Multi-Agent System designed to solve this challenge. The architecture combines a dynamic, Aime-inspired agent orchestrator with a hybrid layer of reliable, self-contained tools. By leveraging state-of-the-art patterns like Tool RAG and just-in-time agent instantiation, the system can solve complex, multi-modal logistics problems that are intractable for monolithic LLM approaches.

## 2. System Architecture

Our framework is a modular, multi-layered system designed for robustness and scalability.

 <!-- We will create a simple diagram for this -->

**The architecture consists of four primary layers:**

1.  **Orchestration Layer (LangGraph):** The central nervous system of the MAS. It implements the `Dynamic Planner` and manages the overall state and task execution via a cyclical graph.
2.  **Dynamic Agent Layer (LangGraph):** Contains the `Actor Factory` which instantiates temporary, single-purpose `Dynamic Actors` on demand. It uses a **Tool RAG** mechanism to equip these agents with only the most relevant tools for their assigned subtask.
3.  **Hybrid Tool Service Layer (n8n, Gradio, Cloud Run):** A distributed library of self-contained tools, each exposed as a stable API endpoint. Each tool is built on the platform best suited for its function (e.g., n8n for integrations, Gradio for ML models).
4.  **Observability Layer (LangSmith):** Provides end-to-end tracing and debugging for the entire system, ensuring we can monitor, evaluate, and refine agent behavior.

## 3. Repository Structure

This repository is organized to separate concerns and ensure clarity.

```
.
├── n8n-workflows/              # Exported JSON files for all n8n tools and workflows
│   ├── tool-query-web-for-port-info.json
│   └── ...
├── knowledge-base/             # Data sources for our tools
│   ├── logistics_datapoints.json
│   └── ...
├── specifications/             # Formal technical specifications for each tool (Markdown)
│   ├── MAS-TOOL-005-Query_Web_For_Port_Info.md
│   └── ...
├── scripts/                    # Helper scripts (e.g., for data processing, vector DB population)
├── .gitignore
└── README.md
```

-   **`n8n-workflows/`**: Contains the exported JSON definitions of our n8n tools. These can be directly imported into an n8n instance.
-   **`knowledge-base/`**: Stores the raw data used by our tools, such as the structured datapoint definitions.
-   **`specifications/`**: Contains the detailed technical design documents for each component, serving as the formal documentation for our research.
-   **`scripts/`**: Any supporting code, such as Python scripts for embedding and populating the Qdrant vector store.
  **`scripts/`**: Any supporting code, such as Python scripts for integrating with Airtable or other data processing tasks.

## 4. Getting Started

### Prerequisites

-   A running **n8n** instance (self-hosted via Docker is recommended, version >1.105.4).
-   **API Keys** for the following services:
    -   Google Gemini
    -   Tavily AI
  -   Access to an **Airtable** base (for storing and retrieving structured logistics datapoints, as per [ADR-001](architecture-decisions/001-database-for-structured-datapoints.md)).
  -   (Qdrant may be considered for future semantic search tools, but Airtable is the primary database for the MVP.)
## 5. Architecture Decision: Database for Structured Datapoints

As documented in [ADR-001](architecture-decisions/001-database-for-structured-datapoints.md), we have chosen **Airtable** as the primary database for storing and retrieving structured logistics datapoints. Airtable offers:

- Best-in-class metadata filtering and keyword search
- A user-friendly interface for managing ~1,400 datapoints
- First-class integration with n8n via a native node
- A generous free tier suitable for MVP development

Qdrant and other databases may be considered for future, production-scale iterations, especially if semantic search becomes a higher priority.

### Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/maksim-tsi/agentic-logistics-tra2026.git
    cd agentic-logistics-tra2026
    ```

2.  **Configure n8n Credentials:**
    -   In your n8n instance, navigate to the "Credentials" section.
    -   Create new credentials for "Google Gemini" and a generic "Header Auth" credential for Tavily AI, pasting in your API keys. Make sure to note the internal IDs.

3.  **Import the Workflow:**
    -   In n8n, go to "Workflows" and click "Import from File".
    -   Select a workflow from the `n8n-workflows/` directory (e.g., `tool-query-web-for-port-info.json`).
    -   n8n will prompt you to associate the required credentials. Select the ones you just created.

## 5. Usage

To test the `Query_Web_For_Port_Info` tool, you can use a `curl` command to call its webhook endpoint.

1.  Activate the imported workflow in n8n.
2.  Copy the "Test" webhook URL from the `Webhook` node.
3.  Execute the following command, replacing the URL and API key with your own:

```bash
curl --request POST \
  --url 'https://your-n8n-instance.com/webhook-test/your-webhook-path' \
  --header 'Content-Type: application/json' \
  --header 'X-API-KEY: your_secret_key' \
  --data '{
    "port_code": "SGSIN",
    "query": "What are the latest customs requirements for importing electronics?"
  }'
```

## 6. Associated Publication

The concepts, architecture, and results of this implementation are detailed in our upcoming publication for the Transport Research Arena 2026.

**To Cite This Work:**

> M. Ilin and D. Pavlyuk. (2026). *[Placeholder Title: An Agentic Framework for Resilient Logistics Decision Support]*. In Proceedings of the 11th Transport Research Arena (TRA 2026). Budapest, Hungary.

## 7. License

This project is licensed under the MIT License - see the `LICENSE` file for details.
