# Logistics Datapoints Knowledge Base

This directory contains the unified dataset of structured logistics datapoints used by our Multi-Agent System (MAS) for decision support in the TRA 2026 project.

## File: `logistics_datapoints.json`

This file is a single, large JSON array containing 1,346+ datapoint objects. Each object represents a highly structured, atomic datapoint relevant to logistics operations, regulations, and guidelines across major ports and international standards.

### Datapoint Structure
Each datapoint object typically includes the following fields:

- `datapoint_id`: Unique identifier for the datapoint
- `datapoint_type`: Type of datapoint (e.g., Requirement, Guideline)
- `port_area`: The port or region this datapoint applies to (e.g., "Hamburg", "International - IMO")
- `relevant_entity`: The entity affected (e.g., Shipper, Carrier)
- `regulation_category`: High-level category of the regulation or guideline
- `regulation_subcategory`: More specific subcategory, if applicable
- `regulation_detail`: Short, factual description of the requirement or guideline
- `source_document`: Reference to the source regulation or document
- Additional metadata fields as needed

### Usage in the Project
- **Primary Source for Knowledge Tools:** This file is the main data source for tools such as `Query_Port_Information`, enabling faceted and keyword search over logistics requirements and guidelines.
- **Airtable Upload:** For production use, this dataset is uploaded to Airtable, where it can be managed, filtered, and queried via the Airtable API and n8n integration.
- **Data Management:** The JSON format allows for easy editing, validation, and extension. New datapoints can be added by updating the source files in `data/datapoints-raw` and re-running the merge script.

### How to Update
1. Add or edit datapoint files in `data/datapoints-raw/`.
2. Run `scripts/merge_datapoints.py` to regenerate `logistics_datapoints.json`.
3. Upload the updated JSON to Airtable using the Airtable web UI or API.

### Integration
- **n8n:** Use the Airtable node in n8n to query, filter, and retrieve datapoints for agent workflows.
- **Python:** Load and process the JSON file directly for local development or testing.

---
For more details on the architecture and rationale, see [ADR-001](../architecture-decisions/001-database-for-structured-datapoints.md).
