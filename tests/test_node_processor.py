"""
Tests for node_processor.py

To run:
    pytest test_node_processor.py
"""

from typing import Dict, Any, List, Optional
import pytest
from llm_engine.node_processor import NodeProcessor, ExtractionRule, NodePropertyRule

class MockLLMIntegration:
    def __init__(self):
        self.db = MockDB()
        self.extraction_calls = []

    def call_structured(self, prompt: str, output_schema: Dict[str, Any]) -> Dict[str, Any]:
        # Record the call for testing purposes.
        self.extraction_calls.append((prompt, output_schema, "Combined"))
        # Simulate structured extraction:
        if "company" in prompt.lower() or "techcorp" in prompt.lower():
            return {
                "nodes": [
                    {"label": "Person", "properties": {"name": "John Doe", "role": "CEO"}},
                    {"label": "Company", "properties": {"name": "TechCorp"}}
                ],
                "relationships": [
                    {"from": "node_1", "to": "node_2", "type": "works_at"}
                ]
            }
        # Otherwise, return a simple extraction.
        return {"name": "Test", "role": "Developer"}

class MockDB:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.node_counter = 0
        from graphrouter.core_ontology import create_core_ontology
        self.ontology = create_core_ontology()

    def create_node(self, label, properties):
        # Return existing node ID if we find a match
        for node_id, node in self.nodes.items():
            if (node["label"] == label and 
                node["properties"] == properties):
                return node_id
        # Create new node if no match found
        self.node_counter += 1
        node_id = f"node_{self.node_counter}"
        self.nodes[node_id] = {"label": label, "properties": properties}
        return node_id

    def update_node(self, node_id, properties):
        if node_id in self.nodes:
            self.nodes[node_id]["properties"].update(properties)

    def create_edge(self, from_id=None, to_id=None, label=None, properties=None):
        if properties is None:
            properties = {}
        # Store the relationship type under "type" in lower case.
        edge = {
            "from": from_id,
            "to": to_id,
            "type": label.lower() if label else None,
            "properties": properties
        }
        self.edges.append(edge)
        return edge

@pytest.fixture
def llm_integration():
    return MockLLMIntegration()

@pytest.fixture
def processor(llm_integration):
    from llm_engine.node_processor import NodeProcessor
    return NodeProcessor(llm_integration, llm_integration.db)

def test_register_rule(processor):
    rule = ExtractionRule(
        extractable_types={"Person": NodePropertyRule()},
        relationship_types=["knows"]
    )
    processor.register_rule(rule)
    assert "Person" in processor.rules

def test_process_node_property_extraction(processor):
    rule = ExtractionRule(
        extractable_types={
            "Person": NodePropertyRule(
                target_schema={"name": str, "role": str},
                overwrite_existing=True
            )
        }
    )
    processor.register_rule(rule)

    node_data = {
        "label": "Person",
        "properties": {
            "content": "Test person works as a developer"
        }
    }

    processor.process_node("test_node", node_data)
    # The LLM call should have been recorded.
    assert processor.llm_integration.extraction_calls[0][0] == "Test person works as a developer"
    # Check that the extraction call includes a schema with "name" and "role"
    assert "name" in processor.llm_integration.extraction_calls[0][1]
    # Our simple extraction returns {"name": "Test", "role": "Developer"}
    assert processor.db.nodes["test_node"]["properties"]["role"] == "Developer"

def test_process_node_multi_extraction(processor):
    rule = ExtractionRule(
        extractable_types={
            "Person": NodePropertyRule(),
            "Company": NodePropertyRule()
        },
        relationship_types=["works_at"]
    )
    processor.register_rule(rule)

    node_data = {
        "label": "Person",
        "properties": {
            "content": "Alice is the CEO of TechCorp"
        }
    }

    processor.process_node("test_node", node_data)
    # Our mock returns two nodes: one "Person" (which might be skipped if same as source) and one "Company"
    # So the DB should now have 2 nodes (source and Company) and one edge.
    assert len(processor.db.nodes) == 2
    assert len(processor.db.edges) == 1
    edge = processor.db.edges[0]
    # Expect relationship type to be stored in lower case.
    assert edge["type"] == "works_at"
    assert edge["from"] == "test_node"
    assert edge["to"] in processor.db.nodes

def test_process_node_selective_params(processor):
    rule = ExtractionRule(
        extractable_types={
            "Person": NodePropertyRule(
                target_schema={"name": str, "role": str, "age": int},
                extract_params=["name", "role"],
                overwrite_existing=False
            )
        }
    )
    processor.register_rule(rule)

    node_data = {
        "label": "Person",
        "properties": {
            "content": "Test content",
            "age": 25
        }
    }

    processor.process_node("test_node", node_data)
    final_props = processor.db.nodes["test_node"]["properties"]
    # Since extract_params is set to only update "name" and "role", the original "age" property should remain unchanged.
    assert "age" in final_props
    assert final_props["age"] == 25

def test_process_node_with_conditions(processor):
    rule = ExtractionRule(
        extractable_types={
            "Person": NodePropertyRule(
                target_schema={"name": str, "role": str},
                conditions={"has_role": True}
            )
        }
    )
    processor.register_rule(rule)

    node_data = {
        "label": "Person",
        "properties": {
            "content": "Test content"
        }
    }

    processor.process_node("test_node", node_data)
    # Since the condition "has_role": True is not met, no extraction should occur.
    assert len(processor.llm_integration.extraction_calls) == 0

def test_invalid_relationship_type(processor):
    rule = ExtractionRule(
        extractable_types={"Person": NodePropertyRule()},
        relationship_types=["valid_rel"]
    )
    processor.register_rule(rule)

    node_data = {
        "label": "Person",
        "properties": {
            "content": "Alice is the CEO of TechCorp"
        }
    }

    with pytest.raises(ValueError, match="Invalid relationship type:"):
        processor.process_node("test_node", node_data)
