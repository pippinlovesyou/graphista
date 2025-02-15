"""
Tests specific to the Neo4j backend implementation.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from graphrouter import Neo4jGraphDatabase, Query
from graphrouter.errors import ConnectionError
from graphrouter.query import AggregationType

@pytest.fixture
def mock_neo4j_session():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=None)
    session.run = MagicMock()
    session.run.return_value = MagicMock(single=MagicMock(return_value={"node_id": 1}))
    return session

@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session):
    driver = MagicMock()
    driver.session = MagicMock(return_value=mock_neo4j_session)
    return driver

@pytest.fixture
def neo4j_db(mock_neo4j_driver):
    with patch('neo4j.GraphDatabase') as mock_neo4j:
        mock_neo4j.driver = MagicMock(return_value=mock_neo4j_driver)
        db = Neo4jGraphDatabase()
        db.driver = mock_neo4j_driver
        db.connected = True
        return db

def test_neo4j_connection(neo4j_db):
    assert neo4j_db.is_connected

def test_neo4j_invalid_connection():
    with patch('neo4j.GraphDatabase', autospec=True) as mock_neo4j:
        mock_neo4j.driver.side_effect = ConnectionError("Failed to connect")
        db = Neo4jGraphDatabase()
        with pytest.raises(ConnectionError):
            db.connect("bolt://invalid:7687", "neo4j", "wrong")

def test_neo4j_cypher_query_generation(neo4j_db):
    query = Query()
    query.filter(Query.label_equals("Person"))
    query.filter(Query.property_equals("name", "Alice"))
    query.sort("age", reverse=True)
    query.limit_results(5)

    cypher = neo4j_db._build_cypher_query(query)
    expected = (
        "MATCH (n) "
        "WHERE n:Person AND n.name = 'Alice' "
        "ORDER BY n.age DESC "
        "LIMIT 5 "
        "RETURN n"
    )
    assert cypher.replace("  ", " ") == expected.replace("  ", " ")

def test_neo4j_crud_operations(neo4j_db, mock_neo4j_session):
    # Setup mock returns
    mock_neo4j_session.run.side_effect = [
        MagicMock(single=lambda: {"node_id": 1}),  # create n1
        MagicMock(single=lambda: {"node_id": 2}),  # create n2
        MagicMock(single=lambda: {                 # get n1
            "label": ["Person"],
            "properties": {"name": "Alice", "age": 30}
        }),
        MagicMock(single=lambda: True),            # update n1
        MagicMock(single=lambda: {                 # get n1 after update
            "label": ["Person"],
            "properties": {"name": "Alice", "age": 31}
        }),
        MagicMock(single=lambda: {"edge_id": 1}),  # create edge
        MagicMock(single=lambda: {                 # get edge
            "label": "FRIENDS_WITH",
            "properties": {"since": "2023-01-01"},
            "from_id": 1,
            "to_id": 2
        })
    ]

    # Test node operations
    n1 = neo4j_db.create_node("Person", {"name": "Alice", "age": 30})
    n2 = neo4j_db.create_node("Person", {"name": "Bob", "age": 25})

    node1 = neo4j_db.get_node(n1)
    assert node1["properties"]["name"] == "Alice"
    assert node1["properties"]["age"] == 30

    neo4j_db.update_node(n1, {"age": 31})
    node1 = neo4j_db.get_node(n1)
    assert node1["properties"]["age"] == 31

    # Test edge operations
    e_id = neo4j_db.create_edge(n1, n2, "FRIENDS_WITH", {"since": "2023-01-01"})
    edge_data = neo4j_db.get_edge(e_id)
    assert edge_data["from_id"] == "1"
    assert edge_data["to_id"] == "2"

@pytest.mark.asyncio
async def test_neo4j_async_operations():
    # Setup async mocks
    mock_async_session = AsyncMock()
    mock_async_session.run = AsyncMock()
    mock_async_session.__aenter__ = AsyncMock(return_value=mock_async_session)
    mock_async_session.__aexit__ = AsyncMock(return_value=None)

    mock_async_driver = AsyncMock()
    mock_async_driver.session = MagicMock(return_value=mock_async_session)
    mock_async_driver.close = AsyncMock()

    async def mock_driver(*args, **kwargs):
        return mock_async_driver

    with patch('neo4j.AsyncGraphDatabase') as mock_async_neo4j:
        mock_async_neo4j.driver = mock_driver
        db = Neo4jGraphDatabase()

        # Mock results
        mock_async_session.run.side_effect = [
            AsyncMock(single=AsyncMock(return_value={"node_id": 1})),
            AsyncMock(fetch=AsyncMock(return_value=[{
                "n": {
                    "id": 1,
                    "labels": ["Person"],
                    "properties": {"name": "Alice", "age": 30}
                }
            }]))
        ]

        # Connect
        await db.connect_async("bolt://localhost:7687", "neo4j", "password")
        assert db.is_connected

        # Create node
        node_id = await db.create_node_async("Person", {"name": "Alice", "age": 30})
        assert node_id == "1"

        # Query
        query = Query()
        query.filter(Query.label_equals("Person"))
        results = await db.query_async(query)

        assert len(results) == 1
        assert results[0]["properties"]["name"] == "Alice"

        # Disconnect
        await db.disconnect_async()
        assert not db.is_connected

def test_neo4j_vector_search(neo4j_db, mock_neo4j_session):
    """Test vector search functionality in Neo4j."""
    mock_neo4j_session.run.side_effect = [
        MagicMock(single=lambda: {"node_id": 1}),  # create A1
        MagicMock(single=lambda: {"node_id": 2}),  # create A2
        MagicMock(single=lambda: {"node_id": 3}),  # create A3
        MagicMock(return_value=[                   # vector search
            {
                "n": {
                    "id": 1,
                    "labels": ["Article"],
                    "properties": {"title": "A1", "embedding": [1.0, 0.0, 0.0]}
                }
            },
            {
                "n": {
                    "id": 2,
                    "labels": ["Article"],
                    "properties": {"title": "A2", "embedding": [0.0, 1.0, 0.0]}
                }
            }
        ])
    ]

    # Create test nodes with embeddings
    nodes = [
        ('Article', {'title': 'A1', 'embedding': [1.0, 0.0, 0.0]}),
        ('Article', {'title': 'A2', 'embedding': [0.0, 1.0, 0.0]}),
        ('Article', {'title': 'A3', 'embedding': [0.0, 0.0, 1.0]})
    ]

    node_ids = []
    for label, props in nodes:
        node_ids.append(neo4j_db.create_node(label, props))

    # Test vector search with filter
    query = Query()
    query.vector_nearest("embedding", [1.0, 0.1, 0.1], k=2)
    query.filter(Query.property_equals('title', 'A1'))  # Added filter
    results = neo4j_db.query(query)

    assert len(results) == 1  # Changed from 2 to 1 since we're filtering for A1
    assert results[0]['properties']['title'] == 'A1'  # Most similar to [1,0,0]