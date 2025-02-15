"""
Tests for the LocalGraphDatabase implementation with advanced query features.
Now with debug prints to help identify root causes of failures.
"""
import pytest
from graphrouter import LocalGraphDatabase, Query
from graphrouter.query import AggregationType
from graphrouter.errors import ConnectionError
from graphrouter.ontology import Ontology  # Assuming Ontology class is available


def test_advanced_query_operations(local_db, sample_ontology):
    """Test advanced query operations including path finding and aggregations."""
    print("\n[DEBUG] Starting test_advanced_query_operations...")

    # Set ontology
    local_db.set_ontology(sample_ontology)
    print("[DEBUG] Ontology set:", sample_ontology.to_dict())

    # Create test data - social network
    alice = local_db.create_node('Person', {'name': 'Alice', 'age': 30})
    bob = local_db.create_node('Person', {'name': 'Bob', 'age': 25})
    charlie = local_db.create_node('Person', {'name': 'Charlie', 'age': 35})
    david = local_db.create_node('Person', {'name': 'David', 'age': 28})
    print("[DEBUG] Created nodes:", alice, bob, charlie, david)

    # Create relationships
    edge1 = local_db.create_edge(alice, bob, 'friends_with', {'since': '2023-01'})
    edge2 = local_db.create_edge(bob, charlie, 'works_with', {'department': 'IT'})
    edge3 = local_db.create_edge(charlie, david, 'friends_with', {'since': '2023-02'})
    print("[DEBUG] Created edges:", edge1, edge2, edge3)

    # Test path finding
    query = Query()
    query.find_path('Person', 'Person', ['friends_with', 'works_with'], min_depth=1, max_depth=2)
    paths = local_db.query(query)

    print("[DEBUG] Path query results =>", paths)   # DEBUG PRINT
    assert len(paths) > 0, "[DEBUG ASSERT] Expected at least one path, got zero!"

    # Verify path from Alice to Charlie exists
    path_exists = any(
        p['start_node']['properties']['name'] == 'Alice' and
        p['end_node']['properties']['name'] == 'Charlie'
        for p in paths
    )
    print("[DEBUG] path_exists from Alice->Charlie?", path_exists)
    assert path_exists, "[DEBUG ASSERT] Did not find an expected path from Alice to Charlie!"

    # Test relationship filtering
    query = Query()
    query.find_path('Person', 'Person', ['friends_with'])
    query.filter_relationship(
        lambda r: r.get('properties', {}).get('since', '').startswith('2023')
    )
    results = local_db.query(query)
    print("[DEBUG] Relationship filtering =>", results)
    assert len(results) > 0, "[DEBUG ASSERT] Expected friends_with edges with 'since' in 2023"

    for r in results:
        assert r['relationships']
        rel_label = r['relationships'][0]['label']
        print("[DEBUG] rel_label =>", rel_label)
        assert rel_label == 'friends_with'

    # Test aggregations
    query = Query()
    query.filter(Query.label_equals('Person'))
    query.aggregate(AggregationType.AVG, 'age', 'avg_age')
    query.aggregate(AggregationType.COUNT, alias='total_people')
    results = local_db.query(query)
    print("[DEBUG] Aggregation results =>", results)
    assert len(results) == 1
    aggs = results[0]
    print("[DEBUG] Aggregation row =>", aggs)
    assert abs(aggs['avg_age'] - 29.5) < 0.01, f"[DEBUG ASSERT] avg_age mismatch => {aggs['avg_age']}"
    assert aggs['total_people'] == 4, f"[DEBUG ASSERT] total_people mismatch => {aggs['total_people']}"


def test_query_stats(local_db):
    """Test query execution statistics."""
    for i in range(5):
        local_db.create_node('TestNode', {'index': i})

    query = Query()
    query.filter(Query.label_equals('TestNode'))
    results = local_db.query(query)
    print("\n[DEBUG] Query Stats => Results =>", results)

    stats = query.collect_stats()
    print("[DEBUG] Stats =>", stats)
    assert stats['nodes_scanned'] == 5
    assert stats['execution_time'] > 0
    assert stats['memory_used'] > 0


def test_pagination(local_db):
    """Test query pagination."""
    node_ids = []
    for i in range(10):
        node_id = local_db.create_node('TestNode', {'index': i})
        node_ids.append(node_id)
    print("\n[DEBUG] Created 10 'TestNode's =>", node_ids)

    # Test first page
    query = Query()
    query.filter(Query.label_equals('TestNode'))
    query.sort('index')
    query.paginate(page=1, page_size=3)
    results = local_db.query(query)
    print("[DEBUG] pagination(page=1,size=3) =>", results)
    assert len(results) == 3
    assert results[0]['properties']['index'] == 0
    assert results[2]['properties']['index'] == 2

    # Test second page
    query = Query()
    query.filter(Query.label_equals('TestNode'))
    query.sort('index')
    query.paginate(page=2, page_size=3)
    results = local_db.query(query)
    print("[DEBUG] pagination(page=2,size=3) =>", results)
    assert len(results) == 3
    assert results[0]['properties']['index'] == 3
    assert results[2]['properties']['index'] == 5


def test_vector_search(local_db):
    """Test vector search functionality."""
    nodes = [
        ('Article', {'title': 'A1', 'embedding': [1.0, 0.0, 0.0]}),
        ('Article', {'title': 'A2', 'embedding': [0.0, 1.0, 0.0]}),
        ('Article', {'title': 'A3', 'embedding': [0.0, 0.0, 1.0]})
    ]
    for label, props in nodes:
        local_db.create_node(label, props)

    # Test basic vector search
    query = Query()
    query.vector_nearest("embedding", [1.0, 0.1, 0.1], k=2)
    results = local_db.query(query)
    print("\n[DEBUG] vector_search results =>", results)
    assert len(results) == 2
    assert results[0]['properties']['title'] == 'A1'

    # Test with minimum score
    query = Query()
    query.vector_nearest("embedding", [1.0, 0.1, 0.1], k=2, min_score=0.95)
    results = local_db.query(query)
    print("[DEBUG] vector_search (min_score=0.95) =>", results)
    assert len(results) == 1
    assert results[0]['properties']['title'] == 'A1'

    # Test hybrid search (property filter + vector search)
    # The vector search should respect the property filter
    query = Query()
    query.vector_nearest("embedding", [1.0, 0.1, 0.1], k=2)
    query.filter(Query.property_equals('title', 'A1'))  # Changed order to apply filter after vector search
    results = local_db.query(query)
    print("[DEBUG] vector_search with property filter =>", results)
    assert len(results) == 1
    assert results[0]['properties']['title'] == 'A1'


def test_query_operations(local_db):
    """Test query operations."""
    print("\n[DEBUG] Starting test_query_operations...")
    local_db.create_node('Person', {'name': 'Alice', 'age': 30})
    local_db.create_node('Person', {'name': 'Bob', 'age': 25})
    local_db.create_node('Person', {'name': 'Charlie', 'age': 35})

    # Test query filters
    query = Query()
    query.filter(Query.label_equals('Person'))
    query.filter(Query.property_equals('age', 30))
    results = local_db.query(query)
    print("[DEBUG] People with age=30 =>", results)
    assert len(results) == 1
    assert results[0]['properties']['name'] == 'Alice'

    # Test sorting
    query = Query()
    query.filter(Query.label_equals('Person'))
    query.sort('age', reverse=True)
    results = local_db.query(query)
    print("[DEBUG] People sorted by age desc =>", [r['properties'] for r in results])
    assert len(results) == 3
    assert results[0]['properties']['name'] == 'Charlie'
    assert results[2]['properties']['name'] == 'Bob'

    # Test limit
    query = Query()
    query.filter(Query.label_equals('Person'))
    query.sort('age')
    query.limit_results(2)
    results = local_db.query(query)
    print("[DEBUG] People sorted asc limit=2 =>", [r['properties'] for r in results])
    assert len(results) == 2
    assert results[0]['properties']['name'] == 'Bob'


def test_persistence(local_db, test_db_path):
    """Test database persistence."""
    node_id = local_db.create_node('Person', {'name': 'Alice'})
    print("\n[DEBUG] Created node =>", node_id)

    local_db.disconnect()
    local_db.connect(test_db_path)
    node = local_db.get_node(node_id)
    print("[DEBUG] After reconnect => node:", node)
    assert node['properties']['name'] == 'Alice'


def test_crud_operations(local_db):
    """Test basic CRUD operations."""
    node1_id = local_db.create_node('Person', {'name': 'Alice', 'age': 30})
    node2_id = local_db.create_node('Person', {'name': 'Bob', 'age': 25})
    print("\n[DEBUG] Created 2 nodes =>", node1_id, node2_id)

    node1 = local_db.get_node(node1_id)
    print("[DEBUG] node1 =>", node1)
    assert node1['properties']['name'] == 'Alice'
    assert node1['properties']['age'] == 30

    # Update node
    local_db.update_node(node1_id, {'age': 31})
    node1 = local_db.get_node(node1_id)
    print("[DEBUG] updated node1 =>", node1)
    assert node1['properties']['age'] == 31

    # Create edge
    edge_id = local_db.create_edge(node1_id, node2_id, 'friends_with', {'since': '2023-01-01'})
    edge = local_db.get_edge(edge_id)
    print("[DEBUG] created edge =>", edge)
    assert edge['from_id'] == node1_id
    assert edge['to_id'] == node2_id

    # Update edge
    local_db.update_edge(edge_id, {'strength': 'close'})
    edge = local_db.get_edge(edge_id)
    print("[DEBUG] updated edge =>", edge)
    assert edge['properties']['strength'] == 'close'

    # Delete node => also deletes edges
    local_db.delete_node(node1_id)
    print("[DEBUG] after deleting node1 => node:", local_db.get_node(node1_id), "edge:", local_db.get_edge(edge_id))
    assert local_db.get_node(node1_id) is None
    assert local_db.get_edge(edge_id) is None


def test_batch_operations(local_db):
    """Test batch creation operations."""
    nodes = [
        {'label': 'Person', 'properties': {'name': 'Alice', 'age': 30}},
        {'label': 'Person', 'properties': {'name': 'Bob', 'age': 25}},
        {'label': 'Person', 'properties': {'name': 'Charlie', 'age': 35}}
    ]
    node_ids = local_db.batch_create_nodes(nodes)
    print("\n[DEBUG] batch create nodes =>", node_ids)
    assert len(node_ids) == 3

    # Check each node
    for node_id in node_ids:
        print("[DEBUG] checking node =>", node_id, local_db.get_node(node_id))
        assert local_db.get_node(node_id) is not None

    edges = [
        {
            'from_id': node_ids[0],
            'to_id': node_ids[1],
            'label': 'friends_with',
            'properties': {'since': '2023-01-01'}
        },
        {
            'from_id': node_ids[1],
            'to_id': node_ids[2],
            'label': 'colleagues_with',
            'properties': {'since': '2023-02-01'}
        }
    ]
    edge_ids = local_db.batch_create_edges(edges)
    print("[DEBUG] batch create edges =>", edge_ids)
    assert len(edge_ids) == 2

    for edge_id in edge_ids:
        e = local_db.get_edge(edge_id)
        print("[DEBUG] checking edge =>", edge_id, e)
        assert e is not None


def test_error_handling(local_db):
    """Test error handling."""
    local_db.disconnect()
    with pytest.raises(ConnectionError):
        local_db.create_node('Person', {'name': 'Alice'})

    local_db.connect()
    with pytest.raises(ValueError):
        local_db.create_node('Person', None)

    node_id = local_db.create_node('Person', {'name': 'Alice'})
    with pytest.raises(ValueError):
        local_db.create_edge(node_id, 'invalid_id', 'friends_with')


def test_ontology_validation(local_db, sample_ontology):
    """Test ontology validation."""
    print("\n[DEBUG] Starting test_ontology_validation with sample_ontology =>", sample_ontology.to_dict())
    local_db.set_ontology(sample_ontology)

    # Valid node
    node_id = local_db.create_node('Person', {'name': 'Alice', 'age': 30})
    print("[DEBUG] created node =>", node_id)
    assert node_id

    # Invalid node creation => missing 'name'
    with pytest.raises(ValueError):
        print("[DEBUG] Expect ValueError => missing 'name'")
        local_db.create_node('Person', {'age': 30})

    node2_id = local_db.create_node('Person', {'name': 'Bob', 'age': 25})
    print("[DEBUG] created node =>", node2_id)
    edge_id = local_db.create_edge(node_id, node2_id, 'friends_with', {'since': '2023-01-01', 'strength': 5})
    print("[DEBUG] created edge =>", edge_id)
    assert edge_id

    # Invalid edge => missing required property 'since'
    with pytest.raises(ValueError):
        print("[DEBUG] Expect ValueError => missing 'since'")
        local_db.create_edge(node_id, node2_id, 'friends_with', {'strength': 5})


def test_batch_validation(local_db, sample_ontology):
    """Test batch operations with ontology validation."""
    local_db.set_ontology(sample_ontology)

    valid_nodes = [
        {'label': 'Person', 'properties': {'name': 'Alice', 'age': 30}},
        {'label': 'Person', 'properties': {'name': 'Bob', 'age': 25}}
    ]
    node_ids = local_db.batch_create_nodes(valid_nodes)
    print("\n[DEBUG] batch_validation => valid node_ids =>", node_ids)
    assert len(node_ids) == 2


@pytest.mark.asyncio
async def test_async_operations(local_db):
    """Test async database operations."""
    print("\n[DEBUG] Starting test_async_operations...")
    await local_db.connect_async("test_async.json")
    assert local_db.connected

    node_id = await local_db.create_node_async('Person', {'name': 'Alice', 'age': 30})
    print("[DEBUG] created async node =>", node_id)
    assert node_id

    query = Query()
    query.filter(Query.label_equals('Person'))
    results = await local_db.query_async(query)
    print("[DEBUG] async query =>", results)
    assert len(results) == 1
    assert results[0]['properties']['name'] == 'Alice'

    success = await local_db.disconnect_async()
    print("[DEBUG] disconnected =>", success)
    assert success
    assert not local_db.connected


@pytest.mark.asyncio
async def test_async_error_handling(local_db):
    """Test async error handling."""
    print("\n[DEBUG] Starting test_async_error_handling...")
    await local_db.disconnect_async()
    with pytest.raises(ConnectionError):
        await local_db.create_node_async('Person', {'name': 'Alice'})

    await local_db.connect_async()
    with pytest.raises(ValueError):
        await local_db.create_node_async('Person', None)


@pytest.mark.asyncio
async def test_async_persistence(local_db, sample_ontology):
    """Test async database persistence."""
    print("\n[DEBUG] Starting test_async_persistence...")
    await local_db.connect_async("test_async.json")
    node_id = await local_db.create_node_async('Person', {'name': 'Alice'})
    print("[DEBUG] created async node =>", node_id)

    await local_db.disconnect_async()
    await local_db.connect_async("test_async.json")

    query = Query()
    query.filter(Query.label_equals('Person'))
    results = await local_db.query_async(query)
    print("[DEBUG] after reconnect =>", results)
    assert len(results) == 1, "[DEBUG ASSERT] Found more than 1 'Alice' or missing node!"
    assert results[0]['properties']['name'] == 'Alice'

    # Set the ontology so that invalid nodes are caught.
    local_db.set_ontology(sample_ontology)

    # Test invalid batch node creation
    invalid_nodes = [
        {'label': 'Person', 'properties': {'name': 'Charlie'}},
        {'label': 'Person', 'properties': {'age': 35}}  # Missing required 'name'
    ]
    with pytest.raises(ValueError):
        print("[DEBUG] Expect ValueError => invalid batch creation")
        local_db.batch_create_nodes(invalid_nodes)

    # Create two valid nodes to use for edge creation
    valid_nodes = [
        {'label': 'Person', 'properties': {'name': 'X', 'age': 20}},
        {'label': 'Person', 'properties': {'name': 'Y', 'age': 22}}
    ]
    node_ids = local_db.batch_create_nodes(valid_nodes)

    # Test valid batch edge creation
    valid_edges = [
        {
            'from_id': node_ids[0],
            'to_id': node_ids[1],
            'label': 'friends_with',
            'properties': {'since': '2023-01-01', 'strength': 5}
        }
    ]
    edge_ids = local_db.batch_create_edges(valid_edges)
    print("[DEBUG] created edges =>", edge_ids)
    assert len(edge_ids) == 1

    # Test invalid batch edge creation
    invalid_edges = [
        {
            'from_id': node_ids[0],
            'to_id': node_ids[1],
            'label': 'friends_with',
            'properties': {'strength': 5}  # Missing required 'since'
        }
    ]
    with pytest.raises(ValueError):
        print("[DEBUG] Expect ValueError => invalid batch edge creation")
        local_db.batch_create_edges(invalid_edges)


def test_monitoring(local_db):
    """Test monitoring functionality (if applicable)."""
    # This test is not detailed here.
    pass