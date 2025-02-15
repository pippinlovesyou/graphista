"""
tests/test_readme_integration.py

This integration test demonstrates the workflow described in the README:
  1. Set up a LocalGraphDatabase.
  2. Define an ontology (with Person, Company, and Document node types plus a WORKS_AT relationship).
  3. Manually create nodes and an edge (e.g. a Person “Alice” who works at “TechCorp”).
  4. Ingest a natural language document that describes another person and company,
     and run the LLM-powered extraction (via NodeProcessor) to automatically create new nodes
     (with auto-embedding applied).
  5. Query the graph to verify that the expected nodes and embeddings exist.
  6. Run a series of natural language queries through the SmartRetrievalTool to simulate a chain-of-thought
     that uses multiple query types.

NOTE: This test requires a valid OPENAI_API_KEY in the environment.
"""

import os
import json
import pytest
from datetime import datetime
from pathlib import Path

# Import our graph components and LLM integration tools
from graphrouter import LocalGraphDatabase, Ontology, Query
from llm_engine.litellm_client import LiteLLMClient
from llm_engine.node_processor import NodeProcessor, ExtractionRule, NodePropertyRule
from llm_engine.llm_cot_tool import SmartRetrievalTool

# Skip the test if no OpenAI API key is available.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
pytestmark = pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set; skipping integration test.")

def test_readme_integration(tmp_path: Path):
    # Set up the local graph database in a temporary file
    graph_file = tmp_path / "graph.json"
    db = LocalGraphDatabase()
    db.connect(db_path=str(graph_file))

    # STEP 2: Define the knowledge structure (ontology)
    ontology = Ontology()
    # Person: name, role, age and an embedding field for vector searches.
    ontology.add_node_type("Person", 
                             {"name": "str", "role": "str", "age": "int", "embedding": "list"}, 
                             required=["name"])
    # Company: name, industry and an embedding field.
    ontology.add_node_type("Company", 
                             {"name": "str", "industry": "str", "embedding": "list"}, 
                             required=["name"])
    # Document: a node to hold natural language paragraphs.
    ontology.add_node_type("Document", {"content": "str"}, required=["content"])
    # Relationship: WORKS_AT (from Person to Company) with properties.
    # UPDATED: no required properties, so that an extracted edge with only "role" passes validation.
    ontology.add_edge_type("WORKS_AT", {"since": "str", "role": "str", "known_for": "str"}, required=[])
    db.set_ontology(ontology)

    # STEP 3: Manually create some initial nodes
    # Create a Company node for TechCorp.
    techcorp_id = db.create_node("Company", {
        "name": "TechCorp",
        "industry": "Technology",
        "embedding": []  # initially empty; will be updated later if auto-embedding is applied
    })
    # Create a Person node for Alice, who works at TechCorp.
    alice_id = db.create_node("Person", {
        "name": "Alice",
        "role": "Engineer",
        "age": 30,
        "embedding": []  # initially empty
    })
    # Create a WORKS_AT edge from Alice to TechCorp.
    db.create_edge(alice_id, techcorp_id, "WORKS_AT", {"since": "2023-01-01"})

    # STEP 4: Ingest a natural language document (simulate data ingestion)
    # This document describes a software engineer and a company.
    document_text = (
        "John Doe is a talented software engineer at Innotech. "
        "He is known for his innovative coding skills and passion for open source. "
        "Innotech is a rising star in the tech industry, focusing on innovative software solutions."
    )
    doc_id = db.create_node("Document", {"content": document_text})

    # STEP 5: Run LLM-powered extraction to automatically create new nodes (with auto-embedding)
    # Instantiate a real LiteLLMClient (using our real OPENAI_API_KEY)
    llm_client = LiteLLMClient(
        api_key=OPENAI_API_KEY,
        model_name="gpt-4o",  # or another model as desired
        temperature=0.0,
        max_tokens=1500
    )
    # Create a NodeProcessor with our LLM client and the current graph database.
    processor = NodeProcessor(llm_client, db)
    # Define extraction rules: extract Person and Company nodes from document content.
    extraction_rule = ExtractionRule(
        extractable_types={
            "Person": NodePropertyRule(target_schema={"name": str, "role": str, "embedding": list}),
            "Company": NodePropertyRule(target_schema={"name": str, "industry": str, "embedding": list})
        },
        relationship_types=["WORKS_AT"],
        trigger_conditions={"required_properties": ["content"]}
    )
    processor.register_rule(extraction_rule)

    # Process extraction on the Document node.
    doc_node = db.get_node(doc_id)
    processor.process_node(doc_id, doc_node)

    # STEP 6: Query the graph to verify that the new nodes (from the extraction) exist.
    # Query for Person node "John Doe"
    query_person = Query()
    query_person.filter(Query.label_equals("Person"))
    query_person.filter(Query.property_equals("name", "John Doe"))
    person_results = db.query(query_person)
    assert len(person_results) >= 1, "Expected at least one Person node for 'John Doe'."
    # Check that the extracted Person node has an embedding.
    john_props = person_results[0]["properties"]
    assert "embedding" in john_props and john_props["embedding"], "Extracted Person node missing embedding."

    # Query for Company node "Innotech"
    query_company = Query()
    query_company.filter(Query.label_equals("Company"))
    query_company.filter(Query.property_equals("name", "Innotech"))
    company_results = db.query(query_company)
    assert len(company_results) >= 1, "Expected at least one Company node for 'Innotech'."
    innotech_props = company_results[0]["properties"]
    assert "embedding" in innotech_props and innotech_props["embedding"], "Extracted Company node missing embedding."

    # STEP 7: Use the SmartRetrievalTool to ask natural language questions that require multi-step reasoning.
    # NOTE: We pass a serializable form of the ontology using to_dict()
    smart_tool = SmartRetrievalTool(
        llm_client=llm_client,
        db=db,
        ontology=ontology.to_dict(),
        max_iterations=5
    )

    # Question 1: Who works at TechCorp? (Should return Alice, as we manually created her)
    result1 = smart_tool.run("Who works at TechCorp?")
    print("Result 1:", json.dumps(result1, indent=2))
    assert "Alice" in result1["final_answer"], "Expected final answer to mention 'Alice'."

    # Question 2: Find the software engineer mentioned in the document.
    result2 = smart_tool.run("Find the software engineer mentioned in the document.")
    print("Result 2:", json.dumps(result2, indent=2))
    assert "John Doe" in result2["final_answer"], "Expected final answer to mention 'John Doe'."

    # Question 3: List all companies mentioned.
    result3 = smart_tool.run("List all companies mentioned.")
    print("Result 3:", json.dumps(result3, indent=2))
    assert "TechCorp" in result3["final_answer"] and "Innotech" in result3["final_answer"], \
        "Expected final answer to list both 'TechCorp' and 'Innotech'."

    # Optionally, print the full graph structure for manual inspection.
    all_nodes = db.query(Query())
    print("Full Graph Nodes:", json.dumps(all_nodes, indent=2))

    # Clean up: disconnect the database.
    db.disconnect()
