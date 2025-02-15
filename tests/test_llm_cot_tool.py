"""
tests/test_llm_cot_tool.py

Integration tests for the SmartRetrievalTool using your real LLM integration and embedding.
This test requires a valid OPENAI_API_KEY environment variable.
It creates a real LocalGraphDatabase pre-populated with sample Article nodes,
instantiates a real LiteLLMClient, and runs the SmartRetrievalTool.
"""

import os
import json
import pytest
import csv
from datetime import datetime
from graphrouter import LocalGraphDatabase, Ontology, Query
from llm_engine.litellm_client import LiteLLMClient
from llm_engine.llm_cot_tool import SmartRetrievalTool

# Skip test if no OPENAI_API_KEY is available.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
pytestmark = pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set; skipping integration test.")

# --- Helper: create a CSV file in the temporary directory ---
def create_csv_file(tmp_path, filename, rows):
    file_path = tmp_path / filename
    with open(file_path, mode="w", newline='', encoding="utf-8") as csvfile:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"[DEBUG] CSV file created at: {file_path}", flush=True)
    return str(file_path)

# --- Fixture: Set up a LocalGraphDatabase pre-populated with Article nodes. ---
@pytest.fixture
def populated_db(tmp_path):
    db = LocalGraphDatabase()
    db.connect(db_path=str(tmp_path / "graph.json"))
    ontology = Ontology()
    ontology.add_node_type("Article", {"title": "str", "tags": "list", "embedding": "list"}, required=["title"])
    db.set_ontology(ontology)
    # Create two Article nodes using the real embedding via LiteLLMClient.
    llm_client = LiteLLMClient(
        api_key=OPENAI_API_KEY,
        model_name="text-embedding-ada-002",
        temperature=0.0
    )
    emb1 = llm_client.get_embedding("Breaking News: AI Revolution")
    emb2 = llm_client.get_embedding("Sports Highlights")
    db.create_node("Article", {"title": "Breaking News: AI Revolution", "tags": ["news", "ai"], "embedding": emb1})
    db.create_node("Article", {"title": "Sports Highlights", "tags": ["sports"], "embedding": emb2})
    yield db
    db.disconnect()

# --- Fixture: Combined ontology for the SmartRetrievalTool. ---
@pytest.fixture
def combined_ontology():
    ontology_dict = {
        "node_types": {
            "Article": {"properties": {"title": "str", "tags": "list", "embedding": "list"}, "required": ["title"]},
            "Person": {"properties": {"name": "str", "role": "str", "embedding": "list"}, "required": ["name"]},
            "Company": {"properties": {"name": "str", "embedding": "list"}, "required": ["name"]},
            "Document": {"properties": {"content": "str"}, "required": ["content"]}
        },
        "edge_types": {
            "WORKS_AT": {"properties": {"since": "str"}, "required": ["since"]}
        }
    }
    return ontology_dict

# --- Fixture: Instantiate a real LiteLLMClient. ---
@pytest.fixture
def real_llm_client():
    client = LiteLLMClient(
        api_key=OPENAI_API_KEY,
        model_name="gpt-4o-mini",
        temperature=0.0,
        max_tokens=150
    )
    print("[DEBUG] Real LiteLLMClient instantiated.", flush=True)
    return client

# --- Fixture: Instantiate the SmartRetrievalTool. ---
@pytest.fixture
def smart_tool(populated_db, combined_ontology, real_llm_client):
    # Convert the combined ontology dict into an Ontology instance.
    ontology_instance = Ontology.from_dict(combined_ontology)
    tool = SmartRetrievalTool(
        llm_client=real_llm_client,
        db=populated_db,
        ontology=ontology_instance,
        max_iterations=5
    )
    print("[DEBUG] SmartRetrievalTool instantiated.", flush=True)
    return tool

# --- Test the SmartRetrievalTool run() method. ---
def test_smart_retrieval_tool_run(smart_tool):
    question = "Retrieve articles tagged with news about AI."
    print("[DEBUG] Running SmartRetrievalTool with question:", question, flush=True)
    result = smart_tool.run(question)
    print("[DEBUG] SmartRetrievalTool raw result:", json.dumps(result, indent=2), flush=True)

    # Check that the result contains a non-empty final_answer.
    assert "final_answer" in result, "final_answer key missing in tool output."
    final_answer = result["final_answer"]
    print("[DEBUG] Final Answer:", final_answer, flush=True)
    assert isinstance(final_answer, str) and final_answer.strip() != "", "final_answer is empty."

    # Check that the result contains a non-empty chain_of_thought.
    assert "chain_of_thought" in result, "chain_of_thought key missing in tool output."
    chain = result["chain_of_thought"]
    print("[DEBUG] Chain of Thought (truncated):", flush=True)
    for entry in chain:
        # Truncate any very long numeric arrays (e.g. embeddings) for debug printing.
        if "embedding" in entry:
            truncated_entry = entry.replace("embedding", "embedding: [truncated]")
            print(truncated_entry, flush=True)
        else:
            print(entry, flush=True)
    assert isinstance(chain, list), "chain_of_thought should be a list."
    assert len(chain) >= 1, "Expected at least one iteration in chain_of_thought."

    # Verify that no iteration indicates an immediate failure.
    for entry in chain:
        assert "LLM call failed" not in entry, f"LLM call failed in chain: {entry}"

    # Check that each chain entry contains required substrings.
    for i, entry in enumerate(chain, start=1):
        assert f"Iteration {i}:" in entry, f"Iteration marker missing in chain entry: {entry}"
        assert "Thought:" in entry, f"'Thought:' missing in chain entry: {entry}"
        assert "Action:" in entry, f"'Action:' missing in chain entry: {entry}"
        assert "Action Input:" in entry, f"'Action Input:' missing in chain entry: {entry}"

    print("[DEBUG] Test smart_retrieval_tool_run passed successfully.", flush=True)
