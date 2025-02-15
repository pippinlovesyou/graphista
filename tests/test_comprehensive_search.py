"""
tests/test_comprehensive_search.py

This comprehensive integration test verifies our ingestion/extraction/embedding/vector‐search pipeline.
It:
  1. Creates a CSV file containing a document with multi‑sentence text about a person and a company.
  2. Ingests the CSV by creating a File node and a Document node.
  3. Invokes our real extraction process (via NodeProcessor using your real LLM client)
     so that structured data (Person and Company nodes) are created.
  4. Verifies that auto‑embedding (enabled by your system’s configuration) has been applied.
  5. Runs queries (property‑based and vector search) against the graph.

NOTE: This test requires a valid OPENAI_API_KEY environment variable.
"""

import csv
import os
import pytest
import re
from datetime import datetime
from graphrouter import LocalGraphDatabase, Ontology, Query
from llm_engine.litellm_client import LiteLLMClient
from llm_engine.node_processor import NodeProcessor, ExtractionRule, NodePropertyRule

# Skip integration test if no API key is available.
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
    print(f"[DEBUG] CSV file created at: {file_path}")
    return str(file_path)

# --- Fixture: Set up a LocalGraphDatabase with a simple ontology ---
@pytest.fixture
def test_db(tmp_path):
    db = LocalGraphDatabase()
    db.connect(db_path=str(tmp_path / "graph.json"))
    ontology = Ontology()
    ontology.add_node_type("Document", {"content": "str"}, required=["content"])
    ontology.add_node_type("Person", {"name": "str", "role": "str", "embedding": "list"}, required=["name"])
    ontology.add_node_type("Company", {"name": "str", "embedding": "list"}, required=["name"])
    ontology.add_node_type("File", {"name": "str", "source_id": "str", "upload_time": "str", "processed": "bool"}, required=["name"])
    # Add edge types so that edge validation passes.
    # WORKS_AT: defined with a schema but no required properties.
    ontology.add_edge_type("WORKS_AT", {"since": "str"}, required=[])
    # HAS_CONTENT: defined with an empty schema.
    ontology.add_edge_type("HAS_CONTENT", {}, required=[])
    db.set_ontology(ontology)
    print("[DEBUG] Ontology has been set on the database.")
    yield db
    db.disconnect()
    print("[DEBUG] Database disconnected.")

# --- Test: Ingest, extract, auto-embed and then query ---
def test_comprehensive_search_extraction_and_vector_search(test_db, tmp_path):
    """Test comprehensive search extraction and vector search."""
    # Monkey-patch print to hide full embedding lists in debug output.
    import builtins
    original_print = builtins.print

    def safe_print(*args, **kwargs):
        new_args = []
        for arg in args:
            if isinstance(arg, str) and "embedding" in arg:
                # Replace any occurrence of an embedding list [ ... ] with a placeholder.
                # This regex looks for a pattern like: 'embedding': [ ... ]
                arg = re.sub(r"('embedding':\s*)\[[^\]]+\]", r"\1<embedding: ...>", arg)
            new_args.append(arg)
        original_print(*new_args, **kwargs)

    builtins.print = safe_print

    try:
        # 1. Create a CSV file with one document row.
        csv_rows = [
            {
                "content": (
                    "John Doe is a software engineer at TechCorp. "
                    "He loves artificial intelligence and machine learning. "
                    "Contact him at john@techcorp.com."
                )
            }
        ]
        csv_file = create_csv_file(tmp_path, "documents.csv", csv_rows)

        # 2. Simulate ingestion: create a File node and a Document node.
        file_props = {
            "name": os.path.basename(csv_file),
            "source_id": "IngestionTestSource",
            "upload_time": datetime.now().isoformat(),
            "processed": False
        }
        file_node_id = test_db.create_node("File", file_props)
        print(f"[DEBUG] File node created with id: {file_node_id} and properties: {file_props}")

        document_node_ids = []
        with open(csv_file, mode="r", newline='', encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                doc_props = {"content": row["content"]}
                doc_node_id = test_db.create_node("Document", doc_props)
                document_node_ids.append(doc_node_id)
                print(f"[DEBUG] Document node created with id: {doc_node_id} and properties: {doc_props}")

        assert len(document_node_ids) == 1, "Expected one Document node."

        # Print the current state of the database after ingestion:
        print("[DEBUG] Database nodes after ingestion:")
        for nid, node in test_db.nodes.items():
            print(f"    {nid}: {node}")

        # 3. Run extraction on the Document node using our real LLM integration.
        print("[DEBUG] Setting up LiteLLMClient and NodeProcessor...")
        llm_client = LiteLLMClient(
            api_key=OPENAI_API_KEY,
            model_name="gpt-4o-mini",
            temperature=0.0,
            max_tokens=1000
        )
        processor = NodeProcessor(llm_client, test_db)

        # Register extraction rule with unconditional rules (for Document and File) and a Person rule
        rule = ExtractionRule(
            extractable_types={
                "Person": NodePropertyRule(
                    target_schema={"name": str, "role": str, "embedding": list}
                ),
                "Company": NodePropertyRule(
                    target_schema={"name": str, "embedding": list}
                ),
                "Document": NodePropertyRule(
                    target_schema={"content": str},
                    conditions={"always": True}
                ),
                "File": NodePropertyRule(
                    target_schema={"name": str, "processed": bool},
                    conditions={"always": True}
                )
            },
            relationship_types=["WORKS_AT", "HAS_CONTENT"]
        )
        processor.register_rule(rule)
        print("[DEBUG] Extraction rule registered with the following settings:")
        print(f"    Target types: {list(rule.extractable_types.keys())}")
        print(f"    Relationship types: {rule.relationship_types}")

        # Process extraction on the Document node.
        doc_node = test_db.get_node(document_node_ids[0])
        print(f"[DEBUG] Retrieved Document node for extraction: {doc_node}")
        processor.process_node(document_node_ids[0], doc_node)
        print("[DEBUG] Finished processing extraction.")

        # Print the entire state of the database after extraction.
        print("[DEBUG] Database nodes after extraction:")
        for nid, node in test_db.nodes.items():
            print(f"    {nid}: {node}")
        print("[DEBUG] Database edges after extraction:")
        for edge in test_db.edges:
            print(f"    {edge}")

        # 4. Verify that new nodes were created.
        print("[DEBUG] Querying for Person nodes with name 'John Doe'...")
        query_person = Query()
        query_person.filter(Query.label_equals("Person"))
        query_person.filter(Query.property_equals("name", "John Doe"))
        persons = test_db.query(query_person)
        print(f"[DEBUG] Query result for Person nodes: {persons}")
        assert len(persons) >= 1, f"Expected at least one Person node for John Doe, got: {persons}"

        # Verify that the Person node has an embedding.
        person_props = persons[0]["properties"]
        print(f"[DEBUG] Retrieved Person node properties: {person_props}")
        assert "embedding" in person_props, "Person node missing embedding."
        expected_person_embedding = llm_client.get_embedding("John Doe")
        print(f"[DEBUG] Expected embedding for 'John Doe': {expected_person_embedding}")
        print(f"[DEBUG] Actual embedding on Person node: {person_props.get('embedding')}")
        assert person_props["embedding"] == pytest.approx(expected_person_embedding, rel=1e-3), (
            f"Expected Person embedding {expected_person_embedding}, got {person_props['embedding']}"
        )

        # Verify Company node creation.
        print("[DEBUG] Querying for Company nodes with name 'TechCorp'...")
        query_company = Query()
        query_company.filter(Query.label_equals("Company"))
        query_company.filter(Query.property_equals("name", "TechCorp"))
        companies = test_db.query(query_company)
        print(f"[DEBUG] Query result for Company nodes: {companies}")
        assert len(companies) >= 1, f"Expected at least one Company node for TechCorp, got: {companies}"
        company_props = companies[0]["properties"]
        assert "embedding" in company_props, "Company node missing embedding."
        expected_company_embedding = llm_client.get_embedding("TechCorp")
        print(f"[DEBUG] Expected embedding for 'TechCorp': {expected_company_embedding}")
        print(f"[DEBUG] Actual embedding on Company node: {company_props.get('embedding')}")
        assert company_props["embedding"] == pytest.approx(expected_company_embedding, rel=1e-3), (
            f"Expected Company embedding {expected_company_embedding}, got {company_props['embedding']}"
        )

        # 5. Test actual vector search.
        print("[DEBUG] Running vector search query...")
        query_vector = Query()
        query_vector.vector_nearest("embedding", expected_person_embedding, k=3)
        query_vector.filter(Query.label_equals("Person"))
        vec_results = test_db.query(query_vector)
        print(f"[DEBUG] Vector search query result: {vec_results}")
        assert len(vec_results) == 1, f"Expected 1 result after filtering, got {len(vec_results)}"
        print("[DEBUG] Test completed successfully.")
    finally:
        # Restore original print function
        builtins.print = original_print
