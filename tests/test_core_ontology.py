"""
Tests for core_ontology.py
"""
import pytest
from graphrouter.core_ontology import create_core_ontology, extend_ontology
from graphrouter.ontology import Ontology
from graphrouter.errors import InvalidNodeTypeError, InvalidPropertyError

def test_core_ontology_creation():
    """Test creation of core ontology with basic types."""
    ontology = create_core_ontology()
    
    # Test basic node types existence
    assert "DataSource" in ontology.node_types
    assert "File" in ontology.node_types
    assert "Row" in ontology.node_types
    assert "Log" in ontology.node_types
    assert "SearchResult" in ontology.node_types
    assert "Webhook" in ontology.node_types
    
    # Test required properties
    assert "name" in ontology.node_types["DataSource"]["required"]
    assert set(["file_name", "path"]) == set(ontology.node_types["File"]["required"])
    assert "timestamp" in ontology.node_types["Log"]["required"]
    
    # Test edge types
    assert "HAS_FILE" in ontology.edge_types
    assert "HAS_ROW" in ontology.edge_types
    assert "HAS_LOG" in ontology.edge_types
    assert "HAS_WEBHOOK" in ontology.edge_types
    assert "HAS_SYNC" in ontology.edge_types

def test_core_ontology_property_validation():
    """Test property validation in core ontology."""
    ontology = create_core_ontology()
    
    # Valid node properties
    valid_file = {
        "file_name": "test.csv",
        "path": "/data/test.csv",
        "uploaded_time": 1234567890.0,
        "mime_type": "text/csv"
    }
    assert ontology.validate_node("File", valid_file)
    
    # Invalid node properties (missing required)
    with pytest.raises(InvalidPropertyError):
        ontology.validate_node("File", {"file_name": "test.csv"})
    
    # Invalid property type
    with pytest.raises(InvalidPropertyError):
        ontology.validate_node("Log", {
            "timestamp": "not a float",
            "type": "test"
        })

def test_extend_ontology_with_dict():
    """Test extending core ontology with dictionary."""
    base = create_core_ontology()
    extensions = {
        "node_types": {
            "Article": {
                "properties": {
                    "title": "str",
                    "content": "str",
                    "published": "bool"
                },
                "required": ["title", "content"]
            }
        },
        "edge_types": {
            "REFERENCES": {
                "properties": {
                    "context": "str"
                },
                "required": []
            }
        }
    }
    
    extended = extend_ontology(base, extensions)
    
    # Verify original types remain
    assert "DataSource" in extended.node_types
    assert "HAS_FILE" in extended.edge_types
    
    # Verify new types added
    assert "Article" in extended.node_types
    assert "REFERENCES" in extended.edge_types
    
    # Test new type validation
    valid_article = {
        "title": "Test Article",
        "content": "Content here",
        "published": True
    }
    assert extended.validate_node("Article", valid_article)

def test_extend_ontology_with_ontology():
    """Test extending core ontology with another ontology."""
    base = create_core_ontology()
    
    extension = Ontology()
    extension.add_node_type(
        "CustomNode",
        {"name": "str", "value": "int"},
        ["name"]
    )
    extension.add_edge_type(
        "CUSTOM_EDGE",
        {"weight": "float"},
        ["weight"]
    )
    
    extended = extend_ontology(base, extension)
    
    # Verify combined types
    assert "CustomNode" in extended.node_types
    assert "CUSTOM_EDGE" in extended.edge_types
    assert extended.node_types["CustomNode"]["required"] == ["name"]
    
    # Test validation with new types
    valid_node = {"name": "test", "value": 42}
    assert extended.validate_node("CustomNode", valid_node)
    
    valid_edge = {"weight": 0.5}
    assert extended.validate_edge("CUSTOM_EDGE", valid_edge)

def test_core_ontology_edge_validation():
    """Test edge validation in core ontology."""
    ontology = create_core_ontology()
    
    # Valid edge properties
    valid_edge = {"timestamp": 1234567890.0}
    assert ontology.validate_edge("HAS_FILE", valid_edge)
    
    # Optional timestamp
    assert ontology.validate_edge("HAS_FILE", {})
    
    # Invalid property type
    with pytest.raises(InvalidPropertyError):
        ontology.validate_edge("HAS_ROW", {
            "row_number": "not an int"
        })
