"""
Tests for ingestion_engine.py

To run:
  pytest test_ingestion_engine.py
"""

import os
import pytest
import time
import json
from unittest.mock import patch, MagicMock
from ingestion_engine.ingestion_engine import IngestionEngine
from graphrouter.query import Query
from graphrouter import LocalGraphDatabase
from datetime import datetime

@pytest.fixture
def engine(tmp_path):
    """
    Creates an instance of the IngestionEngine with a local JSON graph
    for isolated testing.
    """
    # Point to a temp path for the local graph DB
    test_db_file = tmp_path / "test_graph.json"
    router_config = {
        "type": "local",
        "path": str(test_db_file)
    }

    # Test ontology
    test_ontology = {
        "Person": {
            "properties": {
                "name": "string",
                "age": "integer"
            }
        }
    }

    # Fake composio config (for demonstration)
    composio_config = {
        "api_key": "TEST_API_KEY",
        "entity_id": "TestEntity"
    }

    engine = IngestionEngine(
        router_config=router_config,
        composio_config=composio_config,
        default_ontology=test_ontology,
        auto_extract_structured_data=True,
        extraction_rules={
            "include_columns": ["timestamp", "message"]
        },
        deduplicate_search_results=True,
        schedule_interval=None  # We'll not run the loop in tests
    )

    return engine

def test_file_upload_csv(engine, tmp_path):
    # Create a mock CSV
    csv_file = tmp_path / "test.csv"
    with open(csv_file, mode="w", encoding="utf-8") as f:
        f.write("id,name\n1,TestUser\n2,AnotherUser\n")

    file_node_id = engine.upload_file(str(csv_file), "LocalTestSource", parse_csv=True)
    assert file_node_id is not None, "Should create a File node for the CSV"

    # Verify Row nodes were created and linked
    query = engine.db.create_query()
    query.filter(Query.label_equals("Row"))
    rows = engine.db.query(query)
    assert len(rows) == 2, "Should create 2 Row nodes"

    # Verify links to File node
    query = engine.db.create_query()
    query.filter(Query.relationship_exists(file_node_id, "HAS_ROW"))
    links = engine.db.query(query)
    assert len(links) == 2, "Should create 2 HAS_ROW relationships"

def test_file_upload_non_csv(engine, tmp_path):
    # Create a mock text file
    txt_file = tmp_path / "test.txt"
    with open(txt_file, mode="w", encoding="utf-8") as f:
        f.write("Hello, world")

    file_node_id = engine.upload_file(str(txt_file), "LocalTestSource", parse_csv=True)
    assert file_node_id is not None

@patch('llm_engine.node_processor.NodeProcessor')
def test_llm_enrichment(mock_processor, engine):
    mock_llm = MagicMock()
    engine_with_llm = IngestionEngine(
        router_config={"type": "local", "path": "test_graph.json"},
        llm_integration=mock_llm,
        auto_extract_structured_data=True
    )

    # Test node processing with LLM
    data = {
        'name': 'Test Document',
        'content': 'Test content for LLM processing',
        'created_at': datetime.now().isoformat()
    }
    node_id = engine_with_llm.db.create_node('Document', data)

    # Mock the processor response
    mock_processor_instance = mock_processor()
    mock_processor_instance.process_node.return_value = {'enriched_content': 'Processed content'}

    # Verify LLM integration was called
    engine_with_llm.enrich_with_llm(node_id, "test_enrichment", mock_processor_instance)
    assert hasattr(engine_with_llm, "node_processor")
    assert hasattr(engine_with_llm, "enrichment_manager")

    # Verify processor was called correctly
    mock_processor_instance.process_node.assert_called_once()

def test_download_data(engine):
    # We'll mock or stub composio_toolset usage
    # If the real composio is configured, 
    # you'd use something like Action.GITHUB_GET_CONTENTS_OF_A_REPOSITORY etc.
    if not engine.composio_toolset:
        pytest.skip("No composio installed or configured")

    # Example: let’s call the function with a dummy action
    # (In practice, you’d define valid action IDs from Composio)
    data = engine.download_data(action="MOCK_DOWNLOAD_DATA", params={"fake": True})
    # Check that we stored a log node
    assert "result" in data or "fake" in data

def test_sync_data(engine):
    if not engine.composio_toolset:
        pytest.skip("No composio installed or configured")

    # Example usage for syncing
    engine.sync_data("SampleAPI", action="MOCK_SYNC_DATA", params={"page": 1})
    # Potentially check the graph for a "Log" node with 'type=sync' 
    # or something similar.

def test_search_and_store_results(engine):
    query_string = "test query"
    engine.search_and_store_results(query_string)
    # Validate that search results have been stored 
    # as 'SearchResult' nodes in the graph DB
    # If needed, parse the local JSON or run a query using engine.db

def test_handle_webhook(engine):
    webhook_data = {
        "event": "UserSignup",
        "user_id": 123,
        "timestamp": time.time(),
        "debug_info": "Some internal stuff"
    }
    engine.handle_webhook(webhook_data, "WebhookSource")

    # Verify Webhook node creation
    query = engine.db.create_query()
    query.filter(Query.label_equals("Webhook"))
    webhook_nodes = engine.db.query(query)
    assert len(webhook_nodes) == 1, "Should create 1 Webhook node"

    # Verify Log node creation and linking
    query = engine.db.create_query()
    query.filter(Query.label_equals("Log"))
    query.filter(Query.property_equals("type", "webhook_event"))
    log_nodes = engine.db.query(query)
    assert len(log_nodes) == 1, "Should create 1 Log node"