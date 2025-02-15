"""
Pytest configuration and fixtures.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
import redis

from graphrouter import (
    LocalGraphDatabase,
    Neo4jGraphDatabase,
    FalkorDBGraphDatabase,
    Ontology
)
from graphrouter.errors import ConnectionError

@pytest.fixture
def test_db_path(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_graph.json")


@pytest.fixture
def local_db(test_db_path):
    """Provide a local graph database instance."""
    db = LocalGraphDatabase()
    db.connect(test_db_path)
    yield db
    db.disconnect()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture
def neo4j_db():
    """Provide a Neo4j database instance."""
    db = Neo4jGraphDatabase()
    # Use environment variables for connection details
    uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    username = os.environ.get('NEO4J_USER', 'neo4j')
    password = os.environ.get('NEO4J_PASSWORD', 'password')

    db.connect(uri, username, password)
    yield db

    # Clean up the database
    if db.connected and db.driver:
        with db.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        db.disconnect()


@pytest.fixture
def sample_ontology():
    """Provide a sample ontology for testing."""
    ontology = Ontology()
    # Person nodes: 'name' is required, 'age', 'email' optional
    ontology.add_node_type(
        'Person',
        {'name': 'str', 'age': 'int', 'email': 'str'},
        required=['name']
    )

    # FRIENDS_WITH edges: 'since' is required, 'strength' optional
    ontology.add_edge_type(
        'FRIENDS_WITH',
        {'since': 'str', 'strength': 'int'},
        required=['since']
    )

    # WORKS_WITH edges: 'department' is required
    ontology.add_edge_type(
        'WORKS_WITH',
        {'department': 'str'},
        required=['department']
    )

    return ontology


@pytest.fixture
def mock_falkordb_db():
    """
    Provide a FalkorDB database instance fully mocked so no real Redis connection is made.
    We patch both redis.ConnectionPool and redis.Redis, then store node/edge data in memory
    for create/get logic.
    """
    # Our in-memory store for node/edge data
    # This will mimic numeric IDs, node/edge creation, etc.
    inmem_nodes = {}
    inmem_edges = {}
    next_id = 0  # we'll increment for each created node/edge

    def fake_execute_graph_query(query_str, *args, **kwargs):
        nonlocal next_id
        # We can do minimal string checks:
        # CREATE (n:Person {name: 'Alice'}) RETURN ID(n)
        # or MATCH (n) WHERE ID(n) = 1 RETURN n
        # or etc.

        # parse an ID if "WHERE ID(n) = X" is found:
        import re

        # if it's a CREATE node
        if "CREATE (n:" in query_str and "RETURN ID(n)" in query_str:
            # We'll increment next_id for the new node
            new_id = next_id
            next_id += 1
            # We store minimal info in inmem_nodes
            # Let's parse the label from "CREATE (n:LABEL"
            m_label = re.search(r"CREATE \(n:(\w+)", query_str)
            label = m_label.group(1) if m_label else "Unknown"

            # parse properties after { ... }
            m_props = re.search(r"\{(.*?)\}", query_str)
            props_text = m_props.group(1) if m_props else ""
            # Convert "name: 'Alice', age: 30" into a dict
            # We'll do a naive parse:
            props_dict = {}
            pairs = re.split(r",\s*", props_text)
            for pair in pairs:
                # e.g. "name: 'Alice'"
                sub = pair.split(":", 1)
                if len(sub) == 2:
                    k = sub[0].strip()
                    v = sub[1].strip().strip("'")
                    # if v is numeric, try int
                    if v.isdigit():
                        v = int(v)
                    props_dict[k] = v

            inmem_nodes[new_id] = {
                "id": str(new_id),
                "label": label,
                "properties": props_dict
            }
            # The return shape is typically [ header, [ row1, row2, ... ] ]
            # row1 = [ [ str(new_id) ] ] or something
            return [[], [[ [str(new_id)] ]]]

        # if it's a MATCH for a single node
        if "MATCH (n) WHERE ID(n)" in query_str and "RETURN n" in query_str:
            # parse the ID
            m_id = re.search(r"ID\(n\) = (\d+)", query_str)
            if not m_id:
                return [[], []]
            match_id = int(m_id.group(1))
            if match_id not in inmem_nodes:
                return [[], []]
            node_data = inmem_nodes[match_id]
            # shape is [[], [ [ { 'id': match_id, 'labels': [...], 'properties': {...}} ] ] ]
            # We'll mimic RedisGraph's "dictionary" structure
            cell_dict = {
                "id": match_id,
                "labels": [node_data["label"]],
                "properties": node_data["properties"]
            }
            return [[], [[[cell_dict]]]]

        # if it's CREATE (a)-[r:LABEL {props}]->(b) RETURN ID(r)
        if "CREATE (a)-[r:" in query_str and "RETURN ID(r)" in query_str:
            # parse the from_id, to_id from "WHERE ID(a) = X AND ID(b) = Y"
            m = re.search(r"WHERE ID\(a\) = (\d+) AND ID\(b\) = (\d+)", query_str)
            if not m:
                return [[], []]
            from_id = int(m.group(1))
            to_id = int(m.group(2))
            if from_id not in inmem_nodes or to_id not in inmem_nodes:
                return [[], []]

            # parse the label from "CREATE (a)-[r:LABEL ..."
            m_label = re.search(r"\[r:(\w+)", query_str)
            edge_label = m_label.group(1) if m_label else "UnknownEdge"

            # parse the edge properties
            m_props = re.search(r"\{(.*?)\}", query_str)
            props_text = m_props.group(1) if m_props else ""
            props_dict = {}
            pairs = re.split(r",\s*", props_text)
            for pair in pairs:
                sub = pair.split(":", 1)
                if len(sub) == 2:
                    k = sub[0].strip()
                    v = sub[1].strip().strip("'")
                    if v.isdigit():
                        v = int(v)
                    props_dict[k] = v

            new_eid = next_id
            next_id += 1
            inmem_edges[new_eid] = {
                "label": edge_label,
                "properties": props_dict,
                "from_id": str(from_id),
                "to_id": str(to_id)
            }
            return [[], [[ [str(new_eid)] ]]]

        # if it's MATCH ()-[r]->() WHERE ID(r) = X RETURN r
        if "MATCH ()-[r]->() WHERE ID(r) = " in query_str and "RETURN r" in query_str:
            m_id = re.search(r"ID\(r\) = (\d+)", query_str)
            if not m_id:
                return [[], []]
            edge_id = int(m_id.group(1))
            if edge_id not in inmem_edges:
                return [[], []]
            edge_data = inmem_edges[edge_id]
            cell_dict = {
                "type": edge_data["label"],
                "properties": edge_data["properties"],
                "src_node": int(edge_data["from_id"]),
                "dst_node": int(edge_data["to_id"])
            }
            return [[], [[[cell_dict]]]]

        # If updating or deleting, we can just return success or something
        if "SET" in query_str or "DELETE" in query_str:
            # Usually, this returns something
            return [[], [[[1]]]]  # e.g., 1 row changed

        # If we're running a UNION ALL for batch creation
        if "CREATE (n:" in query_str and "UNION ALL" in query_str:
            # We'll parse each "CREATE (n:LABEL" line
            lines = query_str.split("UNION ALL")
            result_rows = []
            for line in lines:
                # each line is like "CREATE (n:Person { ... }) RETURN ID(n)"
                new_id = next_id
                next_id += 1
                # parse label, parse props, store in inmem_nodes
                m_label = re.search(r"\(n:(\w+)", line)
                label = m_label.group(1) if m_label else "Unknown"
                m_props = re.search(r"\{(.*?)\}", line)
                props_text = m_props.group(1) if m_props else ""
                props_dict = {}
                pairs = re.split(r",\s*", props_text)
                for pair in pairs:
                    sub = pair.split(":", 1)
                    if len(sub) == 2:
                        k = sub[0].strip()
                        v = sub[1].strip().strip("'")
                        if v.isdigit():
                            v = int(v)
                        props_dict[k] = v
                inmem_nodes[new_id] = {
                    "id": str(new_id),
                    "label": label,
                    "properties": props_dict
                }
                result_rows.append([[str(new_id)]])
            return [[], result_rows]

        if "CREATE (a)-[r:" in query_str and "UNION ALL" in query_str:
            # batch create edges
            lines = query_str.split("UNION ALL")
            result_rows = []
            for line in lines:
                # parse from_id, to_id, label, properties
                m = re.search(r"WHERE ID\(a\) = (\d+) AND ID\(b\) = (\d+)", line)
                if not m:
                    continue
                from_id = int(m.group(1))
                to_id = int(m.group(2))
                # parse label
                m_label = re.search(r"\[r:(\w+)", line)
                edge_label = m_label.group(1) if m_label else "UnknownEdge"

                # parse props
                m_props = re.search(r"\{(.*?)\}", line)
                props_text = m_props.group(1) if m_props else ""
                props_dict = {}
                pairs = re.split(r",\s*", props_text)
                for pair in pairs:
                    sub = pair.split(":", 1)
                    if len(sub) == 2:
                        k = sub[0].strip()
                        v = sub[1].strip().strip("'")
                        if v.isdigit():
                            v = int(v)
                        props_dict[k] = v
                new_eid = next_id
                next_id += 1
                inmem_edges[new_eid] = {
                    "label": edge_label,
                    "properties": props_dict,
                    "from_id": str(from_id),
                    "to_id": str(to_id)
                }
                result_rows.append([[str(new_eid)]])
            return [[], result_rows]

        # fallback if unhandled
        return [[], []]

    # We'll patch redis.ConnectionPool and redis.Redis so no real network calls occur
    patch_pool = patch('redis.ConnectionPool', autospec=True)
    patch_redis = patch('redis.Redis', autospec=True)

    with patch_pool as mock_pool_cls, patch_redis as mock_redis_cls:
        mock_pool = mock_pool_cls.return_value
        mock_redis = mock_redis_cls.return_value

        # We can override the client ping so it doesn't fail
        mock_redis.ping.return_value = True
        # and if anything calls execute_command(...) outside the code, we can pass
        mock_redis.execute_command.side_effect = lambda *args, **kwargs: [[], []]

        db = FalkorDBGraphDatabase()
        db.connect(host="0.0.0.0", port=6379)  # We'll not truly connect

        # Now monkeypatch the db's _execute_graph_query to use our fake in-memory logic
        db._execute_graph_query = fake_execute_graph_query

        yield db

        db.disconnect()


@pytest.fixture(params=['local', 'neo4j', 'mock_falkordb'])
def graph_db(request, local_db, neo4j_db, mock_falkordb_db):
    """Provide database instances for testing."""
    if request.param == 'local':
        return local_db
    elif request.param == 'neo4j':
        return neo4j_db
    return mock_falkordb_db
