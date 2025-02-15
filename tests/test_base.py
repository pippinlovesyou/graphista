"""
Tests for the base GraphDatabase class functionality.
"""
import pytest
from graphrouter import GraphDatabase, LocalGraphDatabase

def test_graph_database_instantiation():
    """Test that we can instantiate a concrete implementation."""
    db = LocalGraphDatabase()
    assert isinstance(db, GraphDatabase)
    assert not db.connected

def test_connection_management(local_db):
    """Test connection management."""
    assert local_db.connected
    local_db.disconnect()
    assert not local_db.connected

def test_ontology_validation(local_db, sample_ontology):
    """Test ontology validation."""
    local_db.set_ontology(sample_ontology)
    
    # Valid node
    assert local_db.validate_node('Person', {'name': 'John', 'age': 30})
    
    # Invalid node (missing required property)
    assert not local_db.validate_node('Person', {'age': 30})
    
    # Valid edge
    assert local_db.validate_edge('FRIENDS_WITH', {'since': '2023-01-01', 'strength': 5})
    
    # Invalid edge (missing required property)
    assert not local_db.validate_edge('FRIENDS_WITH', {'strength': 5})
