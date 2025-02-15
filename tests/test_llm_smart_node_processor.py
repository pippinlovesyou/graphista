"""
tests/test_llm_smart_node_processor_advanced.py

Advanced integration tests for the SmartNodeProcessor using a more complex ontology and multiple test scenarios.
Each test case is defined in a JSON-like structure, allowing us to scale up complexity without code repetition.
These tests require a valid OPENAI_API_KEY environment variable.
"""

import os
import json
import pytest
from typing import List, Dict, Any
from graphrouter import LocalGraphDatabase, Ontology, Query
from llm_engine.litellm_client import LiteLLMClient
from llm_engine.llm_smart_node_processor import SmartNodeProcessor

# Skip tests if no OPENAI_API_KEY is available.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
pytestmark = pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set; skipping integration test.")

# Fixture: Create a temporary LocalGraphDatabase with a complex ontology.
@pytest.fixture
def complex_db(tmp_path):
    db = LocalGraphDatabase()
    db_path = str(tmp_path / "complex_graph.json")
    db.connect(db_path=db_path)
    # Define a more complex ontology with multiple node types.
    ontology = Ontology()
    ontology.add_node_type(
        "Person",
        {"name": "str", "role": "str", "embedding": "list", "description": "str"},
        required=["name"]
    )
    ontology.add_node_type(
        "Company",
        {"name": "str", "industry": "str", "location": "str", "embedding": "list"},
        required=["name"]
    )
    ontology.add_node_type(
        "Product",
        {"name": "str", "category": "str", "price": "float", "embedding": "list"},
        required=["name", "price"]
    )
    ontology.add_node_type(
        "Event",
        {"name": "str", "date": "str", "location": "str", "description": "str"},
        required=["name", "date"]
    )
    # Add an edge type "launched" so that relationship creation is valid.
    ontology.add_edge_type("launched", {}, required=[])
    db.set_ontology(ontology)
    yield db
    db.disconnect()

# Fixture: Instantiate a real LiteLLMClient.
@pytest.fixture
def real_llm_client():
    client = LiteLLMClient(
        api_key=OPENAI_API_KEY,
        model_name="gpt-4o",
        temperature=0.0,
        max_tokens=1500
    )
    return client

# Fixture: Instantiate the SmartNodeProcessor with a low chunk threshold for testing.
@pytest.fixture
def smart_processor(complex_db, real_llm_client):
    processor = SmartNodeProcessor(
        llm_client=real_llm_client,
        db=complex_db,
        ontology=complex_db.ontology,
        max_iterations=6,
        max_chunk_tokens=50  # Force chunking in tests
    )
    return processor

# Helper: Create a long content string from a list of sentences.
def create_long_content(sentences: List[str]) -> str:
    return " ".join(sentences)

# Define test cases in a JSON-like structure.
TEST_CASES: List[Dict[str, Any]] = [
    {
        "description": "Exact match update for Person",
        "label": "Person",
        "initial_properties": {"name": "John Doe", "role": "Engineer", "embedding": [], "description": ""},
        "content_sentences": [
            "John Doe is a seasoned software professional.",
            "He has recently been promoted to CEO of Acme Corp.",
            "His leadership has transformed Acme Corp into a market leader.",
            "His previous role as an Engineer is now outdated."
        ],
        "expected_update": {"role": "CEO"},
        "expected_no_duplicate": True
    },
    {
        "description": "Similar name update for Person (fuzzy matching)",
        "label": "Person",
        "initial_properties": {"name": "Jon Doe", "role": "Engineer", "embedding": [], "description": ""},
        "content_sentences": [
            "John Doe, a software architect, has been recognized for his innovative solutions.",
            "His contributions reflect his extensive experience.",
            "He is now taking on larger responsibilities."
        ],
        "expected_update": {"role": "software architect"},
        "expected_name_correction": "John Doe",
        "expected_no_duplicate": True
    },
    {
        "description": "New node creation for Company with complex properties",
        "label": "Company",
        "initial_properties": None,
        "content_sentences": [
            "Acme Corp is a leading technology firm.",
            "It specializes in innovative AI solutions and cloud computing.",
            "It is headquartered in Silicon Valley."
        ],
        "create_properties": {"name": "Acme Corp", "industry": "Technology", "location": "Silicon Valley"},
        "expected_creation": True
    },
    {
        "description": "Chunked update for Product with long description",
        "label": "Product",
        "initial_properties": {"name": "SuperWidget", "category": "Gadgets", "price": 99.99, "embedding": []},
        "content_sentences": [
            "SuperWidget is an innovative gadget that has revolutionized the industry.",
            "It features state-of-the-art technology and an intuitive design.",
            "Customers appreciate its durability and performance.",
            "Recent reviews praise its enhanced features and value for money.",
            "It continues to dominate its market segment."
        ],
        "expected_update": {"category": "Gadgets", "price": 99.99},
        "expected_no_duplicate": True
    }
]

@pytest.mark.parametrize("test_case", TEST_CASES)
def test_smart_node_processor_cases(complex_db, smart_processor, test_case: Dict[str, Any]):
    label = test_case["label"]
    description = test_case["description"]

    if test_case.get("initial_properties") is not None:
        node_id = complex_db.create_node(label, test_case["initial_properties"])
    else:
        node_id = "new_" + label

    content = create_long_content(test_case["content_sentences"])
    new_node_data = {
        "label": label,
        "properties": {
            "content": content,
            "name": test_case.get("create_properties", {}).get("name", "")
        }
    }

    result = smart_processor.run(node_id, new_node_data)
    final_node_id = result.get("updated_node_id", node_id)
    print(f"[DEBUG] {description} - Final actions:", result["final_actions"])
    print(f"[DEBUG] {description} - Chain-of-thought:", json.dumps(result["chain_of_thought"], indent=2))

    q = Query()
    q.filter(Query.label_equals(label))
    nodes = complex_db.query(q)
    if test_case.get("expected_no_duplicate", False):
        assert len(nodes) == 1, f"{description}: Expected only one {label} node, but found {len(nodes)}."

    updated_node = complex_db.get_node(final_node_id)
    if test_case.get("expected_creation", False):
        assert updated_node is not None, f"{description}: Expected a new node to be created, but got None."

    if test_case.get("expected_update"):
        expected_role = test_case["expected_update"].get("role")
        if expected_role:
            role = updated_node["properties"].get("role", "").lower()
            if expected_role.lower() == "ceo":
                assert "ceo" in role, f"{description}: Expected role to contain 'CEO', got '{role}'."
            else:
                assert expected_role.lower() in role, f"{description}: Expected role to contain '{expected_role}', got '{role}'."

    if test_case.get("expected_name_correction"):
        expected_name = test_case["expected_name_correction"]
        name = updated_node["properties"].get("name", "")
        assert expected_name == name, f"{description}: Expected name to be corrected to '{expected_name}', got '{name}'."

def test_edge_creation_between_existing_nodes(complex_db, smart_processor):
    """
    Test that when a document describes a relationship between two existing nodes,
    a new edge is created connecting those nodes.
    """
    # Pre-create nodes for Elon Musk (Person) and SpaceX (Company).
    person_id = complex_db.create_node("Person", {"name": "Elon Musk", "role": "CEO", "embedding": [], "description": "Tech visionary"})
    org_id = complex_db.create_node("Company", {"name": "SpaceX", "industry": "Aerospace", "location": "Hawthorne", "embedding": []})

    # Ingest a Document node that describes the relationship.
    doc_text = "Elon Musk launched SpaceX"
    new_node_data = {"label": "Document", "properties": {"content": doc_text}}
    result = smart_processor.run("new_Document", new_node_data)
    print("[DEBUG] Edge Creation Test - Final actions:", result["final_actions"])
    print("[DEBUG] Edge Creation Test - Chain-of-thought:", json.dumps(result["chain_of_thought"], indent=2))

    # Retrieve the edges of the Person node.
    edges = complex_db.get_edges_of_node(person_id)
    found = False
    for edge in edges:
        if edge.get("label") == "launched" and (
            (edge.get("from_id") == person_id and edge.get("to_id") == org_id) or
            (edge.get("from_id") == org_id and edge.get("to_id") == person_id)
        ):
            found = True
            break
    assert found, "Expected edge 'launched' between Elon Musk and SpaceX not found."
