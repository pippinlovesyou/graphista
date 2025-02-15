"""
test_tool_integration.py

Unit tests for tool_integration.py
"""

import pytest
from unittest.mock import MagicMock

# Adjust import paths to match your layout
from llm_engine.tool_integration import LLMToolIntegration
from llm_engine.litellm_client import LiteLLMClient, LiteLLMError
from graphrouter import GraphDatabase, Query


class MockGraphDatabase(GraphDatabase):
    """A mock GraphDatabase for testing (fills in abstract methods)."""
    def connect(self, **kwargs) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> bool:
        self.connected = False
        return True

    async def _create_node_async_impl(self, label: str, properties: dict) -> str:
        """Async version just calls sync version for testing."""
        return self._create_node_impl(label, properties)

    async def _query_async_impl(self, query: Query) -> list:
        """Async version just calls sync version for testing."""
        return self._query_impl(query)

    def _create_node_impl(self, label, properties):
        # Return a dummy ID
        return f"{label}_123"

    def _get_node_impl(self, node_id):
        # Return dummy data to simulate a node
        if "Person" in node_id:
            return {
                "label": "Person",
                "properties": {
                    "name": "Alice",
                    "description": "Some info",
                    "embedding": None
                }
            }
        return None

    def _update_node_impl(self, node_id, properties):
        return True

    def _delete_node_impl(self, node_id):
        return True

    def _create_edge_impl(self, from_id, to_id, label, properties):
        return "edge_123"

    def _get_edge_impl(self, edge_id):
        return None

    def _update_edge_impl(self, edge_id, properties):
        return True

    def _delete_edge_impl(self, edge_id):
        return True

    def _batch_create_nodes_impl(self, nodes):
        return [f"{n['label']}_{i}" for i, n in enumerate(nodes)]

    def _batch_create_edges_impl(self, edges):
        return [f"edge_{i}" for i, e in enumerate(edges)]

    def _query_impl(self, query: Query):
        # Return a small set of mock nodes for testing
        return [
            {"id": "Person_1", "label": "Person", "properties": {"name": "Alice"}},
            {"id": "Person_2", "label": "Person", "properties": {"name": "Bob", "embedding": [0.1, 0.2]}},
        ]


@pytest.fixture
def mock_db():
    """Fixture to provide a connected mock GraphDatabase."""
    db = MockGraphDatabase()
    db.connect()
    return db


@pytest.fixture
def mock_llm_client():
    """
    Provide a mock LiteLLMClient.
    We'll patch methods in tests if needed,
    or just return a default MagicMock-based approach.
    """
    client = LiteLLMClient(api_key="FAKE_KEY")  # real init
    # Overwrite internal method calls with MagicMocks
    client.get_embedding = MagicMock()
    client.call_structured = MagicMock()
    return client


def test_embed_node_if_needed_no_auto_embed(mock_db, mock_llm_client):
    """
    If auto_embed = False, embed_node_if_needed should do nothing.
    """
    integration = LLMToolIntegration(db=mock_db, llm_client=mock_llm_client, auto_embed=False)
    integration.embed_node_if_needed("Person_1")
    # get_embedding should not be called at all
    mock_llm_client.get_embedding.assert_not_called()


def test_embed_node_if_needed_success(mock_db, mock_llm_client):
    """
    If auto_embed=True and node has fields to embed, we call get_embedding
    and store the result in the node.
    """
    mock_llm_client.get_embedding.return_value = [0.42, 0.43, 0.44]
    integration = LLMToolIntegration(db=mock_db, llm_client=mock_llm_client, auto_embed=True)
    integration.embed_node_if_needed("Person_1")
    mock_llm_client.get_embedding.assert_called_once()


def test_auto_embed_new_nodes(mock_db, mock_llm_client):
    """
    auto_embed_new_nodes should embed all nodes that do not already have an embedding,
    if label_filter matches.
    """
    mock_llm_client.get_embedding.return_value = [0.9, 0.8, 0.7]
    integration = LLMToolIntegration(db=mock_db, llm_client=mock_llm_client, auto_embed=True)
    integration.auto_embed_new_nodes(label_filter="Person")

    # We expect DB query() to return 2 "Person" nodes:
    #   1) Person_1 => no embedding => embed
    #   2) Person_2 => has embedding => skip
    mock_llm_client.get_embedding.assert_called_once()


def test_structured_extraction_for_node_ok(mock_db, mock_llm_client):
    """
    structured_extraction_for_node should call call_structured,
    then create a new node with merged properties, then embed if auto_embed=True.
    """
    mock_llm_client.call_structured.return_value = {"age": 30, "nicknames": ["Aly"], "hobby": "cooking"}
    integration = LLMToolIntegration(db=mock_db, llm_client=mock_llm_client, auto_embed=True)
    node_id = integration.structured_extraction_for_node(
        text="She is 30, loves cooking and is sometimes called Aly.",
        schema={"age": 0, "nicknames": [], "hobby": ""},
        node_label="Person",
        default_properties={"country": "USA"}
    )
    assert node_id == "Person_123"  # from mock_db's create_node_impl

    # Check that call_structured was called
    mock_llm_client.call_structured.assert_called_once()
    mock_llm_client.get_embedding.assert_called_once()


def test_structured_extraction_for_node_error(mock_db, mock_llm_client):
    """
    If the call_structured call raises LiteLLMError, we should raise ValueError in the method.
    """
    mock_llm_client.call_structured.side_effect = LiteLLMError("Bad parse")

    integration = LLMToolIntegration(db=mock_db, llm_client=mock_llm_client, auto_embed=True)
    with pytest.raises(ValueError) as excinfo:
        integration.structured_extraction_for_node(
            text="some text",
            schema={"foo": "bar"},
            node_label="Person"
        )
    assert "LLM extraction error: Bad parse" in str(excinfo.value)
    mock_llm_client.get_embedding.assert_not_called()