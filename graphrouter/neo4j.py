"""
Neo4j graph database backend implementation.
"""
from typing import Dict, List, Any, Optional, Union, cast
from neo4j import GraphDatabase as Neo4jDriver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError
import asyncio
from timeout_decorator import timeout
from .base import GraphDatabase
from .errors import ConnectionError, QueryError
from .query import Query


class Neo4jGraphDatabase(GraphDatabase):
    """Neo4j graph database implementation."""

    def __init__(self, pool_size: int = 5):
        super().__init__(pool_size=pool_size)
        self.driver: Optional[Union[Neo4jDriver, Any]] = None
        self.uri: Optional[str] = None
        self.auth: Optional[tuple[str, str]] = None

    def connect(self, uri: str, username: str, password: str) -> bool:
        """Connect to Neo4j database.

        Args:
            uri: The Neo4j connection URI (e.g., 'bolt://localhost:7687')
            username: Neo4j username
            password: Neo4j password

        Returns:
            bool: True if connection successful

        Raises:
            ConnectionError: If connection fails
        """
        try:
            self.uri = uri
            self.auth = (username, password)
            self.driver = Neo4jDriver.driver(uri, auth=self.auth)

            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            self.connected = True
            return True
        except AuthError as e:
            raise ConnectionError(f"Authentication failed: {str(e)}")
        except ServiceUnavailable as e:
            raise ConnectionError(f"Neo4j service unavailable: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {str(e)}")

    async def connect_async(self, uri: str, username: str, password: str) -> bool:
        """Async connect to Neo4j database."""
        try:
            self.uri = uri
            self.auth = (username, password)

            # Create async driver
            from neo4j import AsyncGraphDatabase
            self.driver = await AsyncGraphDatabase.driver(uri, auth=self.auth)

            # Test connection
            async with self.driver.session() as session:
                await session.run("RETURN 1")
            self.connected = True
            return True
        except AuthError as e:
            raise ConnectionError(f"Authentication failed: {str(e)}")
        except ServiceUnavailable as e:
            raise ConnectionError(f"Neo4j service unavailable: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j: {str(e)}")

    async def disconnect_async(self) -> bool:
        """Async disconnect from the database."""
        if self.driver:
            await self.driver.close()
            self.driver = None
            self.connected = False
        return True

    def disconnect(self) -> bool:
        """Disconnect from the database."""
        if self.driver:
            self.driver.close()
            self.driver = None
            self.connected = False
        return True

    @property
    def is_connected(self) -> bool:
        """Check if the database is connected."""
        return self.connected

    async def _create_node_async_impl(self, label: str, properties: Dict[str, Any]) -> str:
        """Async implementation of create_node operation."""
        if not self.connected or not self.driver:
            raise ConnectionError("Database not connected")

        async with self.driver.session() as session:
            query = (
                f"CREATE (n:{label} $props) "
                "RETURN id(n) as node_id"
            )
            result = await session.run(query, props=properties)
            record = await result.single()
            return str(record["node_id"])

    async def _query_async_impl(self, query: Query) -> List[Dict[str, Any]]:
        """Async implementation of query operation."""
        if not self.connected or not self.driver:
            raise ConnectionError("Database not connected")

        cypher = self._build_cypher_query(query)
        async with self.driver.session() as session:
            result = await session.run(cypher)
            records = await result.fetch()
            results = []
            for record in records:
                node = record["n"]
                results.append({
                    'id': str(node.id),
                    'label': list(node.labels)[0],
                    'properties': dict(node)
                })
            return results

    def _create_node_impl(self, label: str, properties: Dict[str, Any]) -> str:
        """Implementation of create_node operation."""
        def create_node_op(session: Session, label: str, properties: Dict[str, Any]) -> str:
            query = (
                f"CREATE (n:{label} $props) "
                "RETURN id(n) as node_id"
            )
            result = session.run(query, props=properties)
            record = result.single()
            return str(record["node_id"])

        return self._execute_with_retry(create_node_op, label, properties)

    def create_node(self, label: str, properties: Dict[str, Any] = None) -> str:
        """Create a new node with the given label and properties."""
        if properties is None:
            properties = {}
        return self._create_node_impl(label, properties)

    def _get_node_impl(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Implementation of get_node operation."""
        def get_node_op(session: Session, node_id: str) -> Optional[Dict[str, Any]]:
            query = (
                "MATCH (n) "
                "WHERE id(n) = $node_id "
                "RETURN labels(n) as label, properties(n) as properties"
            )
            result = session.run(query, node_id=int(node_id))
            record = result.single()
            if record:
                return {
                    'label': record["label"][0],
                    'properties': record["properties"]
                }
            return None

        return self._execute_with_retry(get_node_op, node_id)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a node by its ID."""
        return self._get_node_impl(node_id)

    def _update_node_impl(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """Implementation of update_node operation."""
        def update_node_op(session: Session, node_id: str, properties: Dict[str, Any]) -> bool:
            query = (
                "MATCH (n) "
                "WHERE id(n) = $node_id "
                "SET n += $props "
                "RETURN n"
            )
            result = session.run(query, node_id=int(node_id), props=properties)
            return bool(result.single())

        return self._execute_with_retry(update_node_op, node_id, properties)

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """Update a node's properties."""
        return self._update_node_impl(node_id, properties)

    def _delete_node_impl(self, node_id: str) -> bool:
        """Implementation of delete_node operation."""
        def delete_node_op(session: Session, node_id: str) -> bool:
            query = (
                "MATCH (n) "
                "WHERE id(n) = $node_id "
                "DETACH DELETE n"
            )
            session.run(query, node_id=int(node_id))
            return True

        return self._execute_with_retry(delete_node_op, node_id)

    def delete_node(self, node_id: str) -> bool:
        """Delete a node by its ID."""
        return self._delete_node_impl(node_id)

    def _create_edge_impl(self, from_id: str, to_id: str, label: str, properties: Dict[str, Any]) -> str:
        """Implementation of create_edge operation."""
        def create_edge_op(session: Session, from_id: str, to_id: str, label: str, properties: Dict[str, Any]) -> str:
            query = (
                "MATCH (a), (b) "
                "WHERE id(a) = $from_id AND id(b) = $to_id "
                f"CREATE (a)-[r:{label} $props]->(b) "
                "RETURN id(r) as edge_id"
            )
            result = session.run(
                query,
                from_id=int(from_id),
                to_id=int(to_id),
                props=properties or {}
            )
            record = result.single()
            return str(record["edge_id"])

        return self._execute_with_retry(create_edge_op, from_id, to_id, label, properties)

    def create_edge(self, from_id: str, to_id: str, label: str, properties: Optional[Dict[str, Any]] = None) -> str:
        """Create an edge between two nodes."""
        if properties is None:
            properties = {}
        return self._create_edge_impl(from_id, to_id, label, properties)

    def _get_edge_impl(self, edge_id: str) -> Optional[Dict[str, Any]]:
        """Implementation of get_edge operation."""
        def get_edge_op(session: Session, edge_id: str) -> Optional[Dict[str, Any]]:
            query = (
                "MATCH ()-[r]->() "
                "WHERE id(r) = $edge_id "
                "RETURN type(r) as label, properties(r) as properties, "
                "id(startNode(r)) as from_id, id(endNode(r)) as to_id"
            )
            result = session.run(query, edge_id=int(edge_id))
            record = result.single()
            if record:
                return {
                    'label': record["label"],
                    'properties': record["properties"],
                    'from_id': str(record["from_id"]),
                    'to_id': str(record["to_id"])
                }
            return None

        return self._execute_with_retry(get_edge_op, edge_id)

    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an edge by its ID."""
        return self._get_edge_impl(edge_id)

    def _update_edge_impl(self, edge_id: str, properties: Dict[str, Any]) -> bool:
        """Implementation of update_edge operation."""
        def update_edge_op(session: Session, edge_id: str, properties: Dict[str, Any]) -> bool:
            query = (
                "MATCH ()-[r]->() "
                "WHERE id(r) = $edge_id "
                "SET r += $props "
                "RETURN r"
            )
            result = session.run(query, edge_id=int(edge_id), props=properties)
            return bool(result.single())

        return self._execute_with_retry(update_edge_op, edge_id, properties)

    def update_edge(self, edge_id: str, properties: Dict[str, Any]) -> bool:
        """Update an edge's properties."""
        return self._update_edge_impl(edge_id, properties)

    def _delete_edge_impl(self, edge_id: str) -> bool:
        """Implementation of delete_edge operation."""
        def delete_edge_op(session: Session, edge_id: str) -> bool:
            query = (
                "MATCH ()-[r]->() "
                "WHERE id(r) = $edge_id "
                "DELETE r"
            )
            session.run(query, edge_id=int(edge_id))
            return True

        return self._execute_with_retry(delete_edge_op, edge_id)

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge by its ID."""
        return self._delete_edge_impl(edge_id)

    def _query_impl(self, query: Query) -> List[Dict[str, Any]]:
        """Implementation of query operation."""
        def query_op(session: Session, query: Query) -> List[Dict[str, Any]]:
            cypher = self._build_cypher_query(query)
            result = session.run(cypher)

            results = []
            for record in result:
                node = record["n"]
                results.append({
                    'id': str(node.id),
                    'label': list(node.labels)[0],
                    'properties': dict(node)
                })
            return results

        return self._execute_with_retry(query_op, query)

    def query(self, query: Query) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        return self._query_impl(query)

    @timeout(30)  # 30 second timeout for operations
    def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute an operation with retry logic."""
        if not self.connected or not self.driver:
            raise ConnectionError("Database not connected")

        try:
            with self.driver.session() as session:
                return operation(session, *args, **kwargs)
        except ServiceUnavailable:
            # Try to reconnect once
            if self.uri and self.auth:
                self.connect(self.uri, self.auth[0], self.auth[1])
                with self.driver.session() as session:
                    return operation(session, *args, **kwargs)
            raise
        except Exception as e:
            raise QueryError(f"Operation failed: {str(e)}")

    def _batch_create_nodes_impl(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Implementation of batch_create_nodes operation."""
        def batch_create_nodes_op(session: Session, nodes: List[Dict[str, Any]]) -> List[str]:
            queries = []
            params = {}

            for i, node in enumerate(nodes):
                if 'label' not in node or 'properties' not in node:
                    raise ValueError("Invalid node format")

                param_name = f"props_{i}"
                queries.append(f"CREATE (n:{node['label']} ${param_name}) RETURN id(n) as node_id")
                params[param_name] = node['properties'] or {}

            query = " UNION ALL ".join(queries)
            result = session.run(query, params)
            return [str(record["node_id"]) for record in result]

        return self._execute_with_retry(batch_create_nodes_op, nodes)

    def _batch_create_edges_impl(self, edges: List[Dict[str, Any]]) -> List[str]:
        """Implementation of batch_create_edges operation."""
        def batch_create_edges_op(session: Session, edges: List[Dict[str, Any]]) -> List[str]:
            queries = []
            params = {}

            for i, edge in enumerate(edges):
                if not all(k in edge for k in ['from_id', 'to_id', 'label']):
                    raise ValueError("Invalid edge format")

                from_param = f"from_{i}"
                to_param = f"to_{i}"
                props_param = f"props_{i}"

                queries.append(
                    f"MATCH (a), (b) "
                    f"WHERE id(a) = ${from_param} AND id(b) = ${to_param} "
                    f"CREATE (a)-[r:{edge['label']} ${props_param}]->(b) "
                    "RETURN id(r) as edge_id"
                )

                params[from_param] = int(edge['from_id'])
                params[to_param] = int(edge['to_id'])
                params[props_param] = edge.get('properties', {})

            query = " UNION ALL ".join(queries)
            result = session.run(query, params)
            return [str(record["edge_id"]) for record in result]

        return self._execute_with_retry(batch_create_edges_op, edges)
    
    def _build_cypher_query(self, query: Query) -> str:
        """Convert Query object to Cypher query string."""
        parts = ["MATCH (n)"]
        where_clauses = []

        if query.vector_search:
            vector_field = query.vector_search["field"]
            vector = query.vector_search["vector"]
            k = query.vector_search["k"]
            min_score = query.vector_search.get("min_score")

            # Calculate cosine similarity
            similarity_expr = f"gds.similarity.cosine(n.{vector_field}, {vector}) AS similarity"
            parts.append(f"WITH n, {similarity_expr}")

            if min_score is not None:
                where_clauses.append(f"similarity >= {min_score}")

            # Add sorting by similarity
            parts.append("ORDER BY similarity DESC")
            if k:
                parts.append(f"LIMIT {k}")

        for filter_func in query.filters:
            if hasattr(filter_func, 'filter_type'):
                filter_type = getattr(filter_func, 'filter_type')
                if filter_type == 'label_equals':
                    where_clauses.append(f"n:{getattr(filter_func, 'label')}")
                elif filter_type == 'property_equals':
                    where_clauses.append(
                        f"n.{getattr(filter_func, 'property_name')} = {repr(getattr(filter_func, 'value'))}"
                    )
                elif filter_type == 'property_contains':
                    where_clauses.append(
                        f"n.{getattr(filter_func, 'property_name')} CONTAINS {repr(getattr(filter_func, 'value'))}"
                    )

        if where_clauses:
            parts.append("WHERE " + " AND ".join(where_clauses))

        if query.sort_key:
            direction = "DESC" if query.sort_reverse else "ASC"
            parts.append(f"ORDER BY n.{query.sort_key} {direction}")

        if query.limit:
            parts.append(f"LIMIT {query.limit}")

        parts.append("RETURN n")
        return " ".join(parts)