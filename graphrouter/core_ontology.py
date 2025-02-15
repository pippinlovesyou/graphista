# graphrouter/core_ontology.py
"""
Core ontology definitions for GraphRouter.
"""
from typing import Dict, Any, Union
from .ontology import Ontology

def create_core_ontology() -> Ontology:
    """Create and return the core system ontology."""
    ontology = Ontology()

    # Core node types
    ontology.add_node_type(
        "DataSource",
        {"name": "str", "type": "str"},
        ["name"]
    )

    ontology.add_node_type(
        "File",
        {
            "file_name": "str",
            "path": "str",
            "uploaded_time": "float",
            "mime_type": "str"
        },
        ["file_name", "path"]
    )

    # Use only one definition for "Row" (the more complete version)
    ontology.add_node_type(
        "Row",
        {
            "raw_data": "str",
            "id": "str",
            "name": "str"
        },
        []  # No required fields for CSV rows
    )

    # Use only one definition for "Log" (the more complete version)
    ontology.add_node_type(
        "Log",
        {
            "timestamp": "float",
            "type": "str",
            "message": "str",
            "data": "str",
            "action": "str",
            "params": "str",
            "result": "str",
            "details": "str",
            "data_source": "str"
        },
        ["timestamp"]  # Only timestamp is required
    )

    ontology.add_node_type(
        "SearchResult",
        {
            "content": "str",
            "query_string": "str",
            "score": "float"
        },
        ["content", "query_string"]
    )

    ontology.add_node_type(
        "Webhook",
        {
            "event": "str",
            "payload": "str",
            "timestamp": "float"
        },
        ["event", "timestamp"]
    )

    # Core relationships
    ontology.add_edge_type(
        "HAS_FILE",
        {"timestamp": "float"},
        []  # Make timestamp optional
    )

    ontology.add_edge_type(
        "HAS_ROW",
        {"row_number": "int"},
        []  # Make row_number optional
    )

    ontology.add_edge_type(
        "HAS_LOG",
        {"timestamp": "float"},
        []  # Make timestamp optional
    )

    ontology.add_edge_type(
        "HAS_WEBHOOK",
        {"timestamp": "float"},
        []  # Add webhook relationship
    )

    ontology.add_edge_type(
        "HAS_SYNC",
        {"timestamp": "float"},
        []  # Add sync relationship
    )

    return ontology

def extend_ontology(base_ontology: Ontology, extensions: Union[Dict[str, Any], Ontology]) -> Ontology:
    """Extend the core ontology with custom types."""
    if isinstance(extensions, Ontology):
        # If extensions is an Ontology, merge its types directly
        for node_type, spec in extensions.node_types.items():
            base_ontology.add_node_type(
                node_type,
                spec['properties'],
                spec['required']
            )

        for edge_type, spec in extensions.edge_types.items():
            base_ontology.add_edge_type(
                edge_type,
                spec['properties'],
                spec['required']
            )
    else:
        # Handle dictionary case
        for node_type, spec in extensions.get('node_types', {}).items():
            base_ontology.add_node_type(
                node_type,
                spec.get('properties', {}),
                spec.get('required', [])
            )

        for edge_type, spec in extensions.get('edge_types', {}).items():
            base_ontology.add_edge_type(
                edge_type,
                spec.get('properties', {}),
                spec.get('required', [])
            )

    return base_ontology
