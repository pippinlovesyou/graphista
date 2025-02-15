# Data Ingestion Pipeline

The Data Ingestion Pipeline is a lightweight, automated system designed to load and process data from various sources into your graph database. It leverages LLM-powered extraction to automatically deduplicate, parse, and store structured information based on your defined ontology. This pipeline is ideal for quickly integrating data from CSVs, webhooks, and other sources, while also preparing the data for further LLM‑powered reasoning and graph operations.

**Note:** Some features—such as real-time webhook sync and batch operations—are experimental and not fully tested. Mentions of composio authentication/download and search integration have been removed.

---

## Overview

The ingestion engine offers:

- **One-Line Ingestion:** Quickly load data files (e.g. CSVs) with a single command.
- **LLM-Powered Extraction:** Automatically extract entities and relationships from raw text.
- **Built-in Deduplication:** Prevent duplicate nodes by comparing incoming data against existing records.
- **CSV Auto-parsing:** Automatically process and map CSV columns to your ontology.
- **Webhook and Scheduled Syncs:** Basic support for real-time data updates and periodic synchronization.

---

## Features

- **Simple API:** Easily ingest files with a single method call.
- **Automatic Extraction:** Uses LLM integration to extract structured data based on your configured rules.
- **Configurable Deduplication:** Leverages both fuzzy matching and vector similarity (if enabled) to prevent duplicates.
- **Flexible Configuration:** Supports inclusion and exclusion of specific columns, as well as advanced settings for real-time ingestion.
- **Security:** Built-in input validation and sanitization ensures that only properly formatted data is stored.

---

## Quick Start

### Basic File Upload

To get started with a simple CSV ingestion, use the following code:

~~~python
from ingestion_engine import IngestionEngine

# Initialize the ingestion engine with auto-extraction enabled
engine = IngestionEngine(
    auto_extract_structured_data=True,
    extraction_rules={"include_columns": ["id", "name", "role"]}
)

# Upload and process a CSV file from the HR system
file_node_id = engine.upload_file("data.csv", data_source_name="HR_System", parse_csv=True)
print("Uploaded file node ID:", file_node_id)
~~~

This single command:
- Loads the CSV.
- Auto-parses the data.
- Applies extraction rules to transform raw data into structured nodes and relationships.

---

## Usage Details

### File Upload

The primary method is `upload_file()`, which can automatically:
- Parse CSV files.
- Extract relevant fields based on your extraction rules.
- Deduplicate entries by comparing with existing graph nodes.

~~~python
# Auto-parses CSVs, extracts data, and deduplicates records.
file_node_id = engine.upload_file("data.csv", data_source_name="HR_System", parse_csv=True)
~~~

### Webhook Handling

For basic real-time updates, the ingestion engine can process incoming webhook data:

~~~python
# Process incoming webhook data
result = engine.handle_webhook(webhook_data, data_source_name="GitHub")
print("Webhook processing result:", result)
~~~

### Scheduled Syncs

You can configure the engine to perform periodic data synchronization:

~~~python
# Schedule data syncs every hour (experimental feature)
engine = IngestionEngine(schedule_interval=3600)
engine.run()
~~~

---

## Configuration

The ingestion engine is highly configurable. Here’s an example of advanced configuration:

~~~python
engine = IngestionEngine(
    auto_extract_structured_data=True,
    extraction_rules={
        "include_columns": ["id", "name", "role"],
        "exclude_columns": ["debug"]
    },
    deduplicate_search_results=True,  # Enable advanced deduplication (experimental)
    schedule_interval=3600,             # Run sync every hour (experimental)
    llm_integration=my_llm_client       # Pass your LLM client instance for extraction
)
~~~

**Key Configuration Options:**

- **auto_extract_structured_data:** Automatically trigger LLM extraction.
- **extraction_rules:** Define which columns to include/exclude and map to your ontology.
- **deduplicate_search_results:** Enable or disable advanced deduplication logic.
- **schedule_interval:** Set the frequency (in seconds) for scheduled data syncs.
- **llm_integration:** Provide your configured LLM client to power data extraction.

---

## Data Flow

1. **Data Ingestion:** Data is introduced via file upload, webhook, or scheduled sync.
2. **LLM Processing:** The LLM-powered extraction engine parses and converts raw text into structured nodes and edges.
3. **Graph Storage:** Structured data is stored in the graph database with proper relationships.
4. **Deduplication:** Automatic checks prevent duplicate nodes from being created.

---

## Security Features

- **Input Validation:** All data is validated before processing.
- **Sanitization:** Properties are cleaned to avoid injection or format errors.
- **Rate Limiting:** Ingestion requests can be throttled to prevent overload.
- **Webhook Authentication:** (Note: Basic implementation; further enhancements are planned.)

---

## Under Development (🚧)

- **Pattern Matching:** Advanced graph pattern algorithms are in progress.
- **Batch Operations:** Enhanced batch processing for bulk data ingestion (experimental).
- **Additional Data Source Integrations:** Support for more file types and data streams.
- **Real-time Webhook Sync:** Further improvements are planned.

For more usage examples and detailed documentation, please refer to the [GraphRouter Documentation](../docs/README.md).

---

## Conclusion

The Data Ingestion Pipeline is designed to be simple yet powerful, enabling you to bring in data from various sources, process it intelligently with LLMs, and store it reliably in your graph database. Its flexibility and ease of configuration make it a robust solution for dynamic, LLM-powered knowledge management.
