
"""
Tests for console.py functionality
"""
import pytest
from unittest.mock import patch, MagicMock
import os
from graphrouter import Ontology
import console
from ingestion_engine.ingestion_engine import IngestionEngine

@pytest.fixture
def mock_engine():
    with patch('ingestion_engine.ingestion_engine.IngestionEngine') as mock:
        yield mock

@pytest.fixture
def test_ontology():
    return console.setup_ontology()

def test_setup_ontology():
    """Test ontology creation and structure"""
    ontology = console.setup_ontology()
    
    # Verify core types are present
    # Verify core types
    assert "DataSource" in ontology.node_types
    assert "File" in ontology.node_types
    assert "Row" in ontology.node_types
    assert "Log" in ontology.node_types
    
    # Verify properties
    assert "name" in ontology.node_types["DataSource"]["properties"]
    assert "file_name" in ontology.node_types["File"]["properties"]
    assert "SearchResult" in ontology.node_types
    assert "Webhook" in ontology.node_types
    
    # Verify required properties
    assert "name" in ontology.node_types["DataSource"]["required"]
    assert "file_name" in ontology.node_types["File"]["required"]
    
    # Verify relationship types
    assert "HAS_FILE" in ontology.edge_types
    assert "HAS_ROW" in ontology.edge_types
    assert "HAS_LOG" in ontology.edge_types
    assert "HAS_WEBHOOK" in ontology.edge_types
    
    # Verify relationships
    assert "HAS_FILE" in ontology.edge_types
    assert "HAS_ROW" in ontology.edge_types
    assert "HAS_LOG" in ontology.edge_types

def test_engine_initialization(tmp_path, test_ontology):
    """Test IngestionEngine initialization with proper ontology"""
    db_path = str(tmp_path / "test_graph.json")
    
    engine = IngestionEngine(
        router_config={"db_path": db_path},
        default_ontology=test_ontology,
        auto_extract_structured_data=True
    )
    
    assert engine.ontology is not None
    assert engine.db is not None

@patch('builtins.input', side_effect=['7'])  # Simulate selecting "Exit"
def test_main_exit(mock_input, capsys):
    """Test main function exits properly"""
    console.main()
    captured = capsys.readouterr()
    assert "Ingestion Engine Test Console" in captured.out
    assert "Exiting..." in captured.out
