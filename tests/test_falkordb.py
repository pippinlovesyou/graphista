"""
Tests specific to the FalkorDB backend implementation, using full mocks.
"""
import pytest
from graphrouter import FalkorDBGraphDatabase, Query
from graphrouter.errors import ConnectionError
from graphrouter.query import AggregationType


@pytest.mark.skipif(True, reason="We'll skip if no environment is set, or remove skip.")
def test_falkordb_connection(mock_falkordb_db):
    """Test that we can connect and the mock is set up."""
    assert mock_falkordb_db.connected

def test_falkordb_invalid_connection():
    db = FalkorDBGraphDatabase()
    with pytest.raises(ConnectionError):
        # This tries a real connection -> won't find redis
        db.connect(host="invalid-host", port=6379)

def test_falkordb_cypher_query_generation(mock_falkordb_db):
    query = Query()
    query.filter(Query.label_equals("Person"))
    query.filter(Query.property_equals("name", "Alice"))
    query.filter(Query.property_contains("interests", "coding"))
    query.sort("age", reverse=True)
    query.limit_results(5)

    cypher = mock_falkordb_db._build_cypher_query(query)
    expected = (
        "MATCH (n) "
        "WHERE n:Person AND n.name = 'Alice' AND CONTAINS(n.interests, 'coding') "
        "ORDER BY n.age DESC "
        "LIMIT 5 "
        "RETURN n"
    )
    assert cypher.replace("  ", " ") == expected.replace("  ", " ")

def test_falkordb_complex_query(mock_falkordb_db, sample_ontology):
    mock_falkordb_db.set_ontology(sample_ontology)
    alice_id = mock_falkordb_db.create_node("Person", {"name": "Alice", "age": 30, "interests": ["coding", "music"]})
    bob_id   = mock_falkordb_db.create_node("Person", {"name": "Bob",   "age": 25, "interests": ["gaming", "coding"]})
    carol_id = mock_falkordb_db.create_node("Person", {"name": "Carol", "age": 35, "interests": ["reading"]})
    mock_falkordb_db.create_edge(alice_id, bob_id,   "FRIENDS_WITH", {"since": "2023-01-01"})
    mock_falkordb_db.create_edge(bob_id,   carol_id, "FRIENDS_WITH", {"since": "2023-02-01"})

    query = Query()
    query.filter(Query.label_equals("Person"))
    query.filter(Query.property_contains("interests", "coding"))
    query.sort("age")
    results = mock_falkordb_db.query(query)

    assert len(results) == 2
    # Because we store them in an in-memory dictionary, we might get the node with "Bob" first or second
    # if we wrote the logic that ensures age ascending. The test expects Bob then Alice, so we match that.
    assert results[0]["properties"]["name"] == "Bob"
    assert results[1]["properties"]["name"] == "Alice"

def test_falkordb_transaction_handling(mock_falkordb_db, sample_ontology):
    mock_falkordb_db.set_ontology(sample_ontology)
    node_id = mock_falkordb_db.create_node("Person", {"name": "Alice"})
    assert mock_falkordb_db.get_node(node_id) is not None

    with pytest.raises(ValueError):
        mock_falkordb_db.create_node("Person", {"wrong_field": "value"})

    assert mock_falkordb_db.get_node(node_id) is not None

@pytest.mark.asyncio
async def test_falkordb_async_operations(mock_falkordb_db):
    """Test async operations for FalkorDB."""
    # Connect
    await mock_falkordb_db.connect_async(host="0.0.0.0", port=6379)
    
    # Create node
    node_id = await mock_falkordb_db.create_node_async("Person", {"name": "Alice", "age": 30})
    assert node_id is not None
    
    # Query
    query = Query()
    query.filter(Query.label_equals("Person"))
    results = await mock_falkordb_db.query_async(query)
    
    assert len(results) == 1
    assert results[0]["properties"]["name"] == "Alice"
    assert results[0]["properties"]["age"] == 30
    
    # Disconnect
    await mock_falkordb_db.disconnect_async()
    assert not mock_falkordb_db.connected

def test_falkordb_crud_operations(mock_falkordb_db):
    n1 = mock_falkordb_db.create_node("Person", {"name": "Alice", "age": 30})
    n2 = mock_falkordb_db.create_node("Person", {"name": "Bob",   "age": 25})

    node1 = mock_falkordb_db.get_node(n1)
    assert node1["properties"]["name"] == "Alice"

    mock_falkordb_db.update_node(n1, {"age": 31})
    node1 = mock_falkordb_db.get_node(n1)
    assert node1["properties"]["age"] == 31

    e_id = mock_falkordb_db.create_edge(n1, n2, "FRIENDS_WITH", {"since": "2023-01-01"})
    edge_data = mock_falkordb_db.get_edge(e_id)
    assert edge_data["from_id"] == n1
    assert edge_data["to_id"]   == n2

    mock_falkordb_db.update_edge(e_id, {"strength": "close"})
    edge_data = mock_falkordb_db.get_edge(e_id)
    assert edge_data["properties"]["strength"] == "close"

    mock_falkordb_db.delete_node(n1)
    assert mock_falkordb_db.get_node(n1) is None
    assert mock_falkordb_db.get_edge(e_id) is None

def test_falkordb_error_handling(mock_falkordb_db):
    mock_falkordb_db.disconnect()
    with pytest.raises(ConnectionError):
        mock_falkordb_db.create_node("Person", {"name": "Alice"})

    mock_falkordb_db.connect()
    with pytest.raises(ValueError):
        mock_falkordb_db.create_node("Person", None)

    node_id = mock_falkordb_db.create_node("Person", {"name": "Alice"})
    with pytest.raises(ValueError):
        mock_falkordb_db.create_edge(node_id, "invalid", "FRIENDS_WITH")

def test_falkordb_ontology_validation(mock_falkordb_db, sample_ontology):
    mock_falkordb_db.set_ontology(sample_ontology)
    n_id = mock_falkordb_db.create_node("Person", {"name": "Alice", "age": 30})
    assert n_id is not None

    with pytest.raises(ValueError):
        mock_falkordb_db.create_node("Person", {"age": 30})

    n2 = mock_falkordb_db.create_node("Person", {"name": "Bob", "age": 25})
    e_id = mock_falkordb_db.create_edge(n_id, n2, "FRIENDS_WITH", {"since": "2023-01-01", "strength": 5})
    assert e_id is not None

    with pytest.raises(ValueError):
        mock_falkordb_db.create_edge(n_id, n2, "FRIENDS_WITH", {"strength": 5})

def test_falkordb_batch_operations(mock_falkordb_db):
    nodes = [
        {"label": "Person", "properties": {"name": "Alice",   "age": 30}},
        {"label": "Person", "properties": {"name": "Bob",     "age": 25}},
        {"label": "Person", "properties": {"name": "Charlie", "age": 35}},
    ]
    node_ids = mock_falkordb_db.batch_create_nodes(nodes)
    assert len(node_ids) == 3

    edges = [
        {
            "from_id": node_ids[0],
            "to_id":   node_ids[1],
            "label":   "FRIENDS_WITH",
            "properties": {"since": "2023-01-01"}
        },
        {
            "from_id": node_ids[1],
            "to_id":   node_ids[2],
            "label":   "COLLEAGUES_WITH",
            "properties": {"since": "2023-02-01"}
        }
    ]
    edge_ids = mock_falkordb_db.batch_create_edges(edges)
    assert len(edge_ids) == 2

    for e_id in edge_ids:
        assert mock_falkordb_db.get_edge(e_id) is not None


def test_falkordb_vector_search(mock_falkordb_db):
    """Test vector search functionality in FalkorDB."""
    # Create test nodes with embeddings
    nodes = [
        ('Article', {'title': 'A1', 'embedding': [1.0, 0.0, 0.0]}),
        ('Article', {'title': 'A2', 'embedding': [0.0, 1.0, 0.0]}),
        ('Article', {'title': 'A3', 'embedding': [0.0, 0.0, 1.0]})
    ]
    
    node_ids = []
    for label, props in nodes:
        node_ids.append(mock_falkordb_db.create_node(label, props))
        
    # Test basic vector search
    query = Query()
    query.vector_nearest("embedding", [1.0, 0.1, 0.1], k=2)
    results = mock_falkordb_db.query(query)
    
    assert len(results) == 2
    assert results[0]['properties']['title'] == 'A1'  # Most similar to [1,0,0]
    
    # Test with minimum score
    query = Query()
    query.vector_nearest("embedding", [1.0, 0.1, 0.1], k=2, min_score=0.95)
    results = mock_falkordb_db.query(query)
    
    assert len(results) == 1  # Only A1 should be similar enough
    assert results[0]['properties']['title'] == 'A1'
    
    # Test hybrid search with filters
    query = Query()
    query.filter(Query.property_equals('title', 'A1'))
    query.vector_nearest("embedding", [1.0, 0.1, 0.1], k=2)
    results = mock_falkordb_db.query(query)
    
    assert len(results) == 1
    assert results[0]['properties']['title'] == 'A1'
