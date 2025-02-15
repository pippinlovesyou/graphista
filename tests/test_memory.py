# tests/test_memory.py

import os
import json
import pytest
from pathlib import Path
from graphrouter import Query
from memory import Memory

# Skip integration test if no OpenAI API key is set
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
pytestmark = pytest.mark.skipif(
    not OPENAI_API_KEY, 
    reason="OPENAI_API_KEY not set; skipping integration test."
)

def test_memory_full_integration(tmp_path: Path):
    """
    Full integration test for the Memory class.

    This test:
      1. Creates a temporary ontology and extraction rules configuration.
      2. Instantiates a Memory object (with a local JSON backend).
      3. Ingests a document containing natural language describing a person and a company.
      4. Uses the `ask` method to verify that the extracted information is retrievable.
      5. Uses the `retrieve` method to get nodes based on a keyword.
      6. Executes a custom Query to retrieve Company nodes.
      7. Ingests a CSV file via `ingest_file`.
      8. Calls `visualize` and then `close`.
    """
    # --- STEP 1: Prepare configuration files for ontology and extraction rules ---
    ontology_dict = {
        "node_types": {
            "Person": {
                "properties": {"name": "str", "role": "str", "age": "int", "embedding": "list"},
                "required": ["name"]
            },
            "Company": {
                "properties": {"name": "str", "industry": "str", "embedding": "list"},
                "required": ["name"]
            },
            "Document": {
                "properties": {"content": "str"},
                "required": ["content"]
            }
        },
        "edge_types": {
            "WORKS_AT": {
                "properties": {"since": "str", "role": "str", "known_for": "str"},
                "required": []
            }
        }
    }
    extraction_rules = {
        "extractable_types": {
            "Person": {
                "target_schema": {"name": "str", "role": "str", "embedding": "list"}
            },
            "Company": {
                "target_schema": {"name": "str", "industry": "str", "embedding": "list"}
            }
        },
        "relationship_types": ["WORKS_AT"],
        "trigger_conditions": {"required_properties": ["content"]}
    }

    # Write these configurations to temporary JSON files
    ontology_path = tmp_path / "ontology.json"
    extraction_path = tmp_path / "extraction.json"
    ontology_path.write_text(json.dumps(ontology_dict))
    extraction_path.write_text(json.dumps(extraction_rules))

    # Set a temporary file for the local database
    db_path = str(tmp_path / "graph.json")

    # --- STEP 2: Initialize Memory ---
    memory = Memory(
        backend="local",
        ontology_config=str(ontology_path),
        extraction_rules=str(extraction_path),
        auto_embedding=True,
        llm_config={
            "api_key": OPENAI_API_KEY,
            "model_name": "gpt-4o",  # Use a lightweight model if available
            "temperature": 0.0,
            "max_tokens": 1000
        },
        db_path=db_path
    )

    # --- STEP 3: Ingest a natural language document ---
    doc_text = (
        "John Doe is a brilliant software engineer at Innotech. "
        "He is known for his innovative coding and leadership skills. "
        "Innotech is a rising tech company specializing in innovative solutions."
    )
    doc_id = memory.ingest(doc_text)
    assert doc_id is not None, "Document ingestion failed."

    # --- STEP 4: Ask a natural language question ---
    answer = memory.ask("Who is the software engineer mentioned in the document?")
    print("Answer from ask():", answer)
    final_answer = answer.get("final_answer", "")
    assert "John Doe" in final_answer, "Expected 'John Doe' to be mentioned in the final_answer."

    # --- STEP 5: Retrieve memories based on a keyword ---
    memories = memory.retrieve("tech")
    print("Results from retrieve():", json.dumps(memories, indent=2))
    assert any(
        "content" in node["properties"] and "tech" in node["properties"]["content"].lower()
        for node in memories
    ), "No memories found containing the keyword 'tech'."

    # --- STEP 6: Run a custom query ---
    q = Query()
    q.filter(Query.label_equals("Company"))
    companies = memory.query(q)
    print("Company nodes from query():", companies)
    assert any(
        "Innotech" in node["properties"].get("name", "")
        for node in companies
    ), "Expected to find a Company node named 'Innotech'."

    # --- STEP 7: Ingest a CSV file ---
    csv_file = tmp_path / "test.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        f.write("content\n")
        f.write("Alice is a data scientist at DataCorp.\n")
    file_node_id = memory.ingest_file(str(csv_file))
    assert file_node_id is not None, "File ingestion failed."

    # --- STEP 8: Visualize and Close ---
    memory.visualize()
    memory.close()
