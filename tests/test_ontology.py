"""
Tests for the Ontology management system.
"""
import pytest
from graphrouter import Ontology
from graphrouter.errors import InvalidPropertyError, InvalidNodeTypeError

def test_ontology_creation():
    """Test ontology creation and basic operations."""
    ontology = Ontology()

    # Add node type
    ontology.add_node_type(
        'Person',
        {'name': 'str', 'age': 'int'},
        required=['name']
    )

    # Add edge type
    ontology.add_edge_type(
        'KNOWS',
        {'since': 'str'},
        required=['since']
    )

    # Verify structure
    assert 'Person' in ontology.node_types
    assert 'KNOWS' in ontology.edge_types

def test_node_validation(sample_ontology):
    """Test node validation."""
    # Valid node
    assert sample_ontology.validate_node('Person', {
        'name': 'Alice',
        'age': 30,
        'email': 'alice@example.com'
    })

    # Invalid node (wrong property type)
    with pytest.raises(InvalidPropertyError):
        sample_ontology.validate_node('Person', {
            'name': 'Alice',
            'age': '30'  # Should be int
        })

    # Invalid node (missing required property)
    with pytest.raises(InvalidPropertyError):
        sample_ontology.validate_node('Person', {
            'age': 30
        })

def test_edge_validation(sample_ontology):
    """Test edge validation."""
    # Valid edge
    assert sample_ontology.validate_edge('FRIENDS_WITH', {
        'since': '2023-01-01',
        'strength': 5
    })

    # Invalid edge (missing required property)
    with pytest.raises(InvalidPropertyError):
        sample_ontology.validate_edge('FRIENDS_WITH', {
            'strength': 5
        })

def test_ontology_serialization(sample_ontology):
    """Test ontology serialization."""
    # Convert to dict
    ontology_dict = sample_ontology.to_dict()

    # Create new ontology from dict
    new_ontology = Ontology.from_dict(ontology_dict)

    # Verify structure is preserved
    assert new_ontology.node_types == sample_ontology.node_types
    assert new_ontology.edge_types == sample_ontology.edge_types
