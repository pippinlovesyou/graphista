# falkordb.py

import ast
import re
from typing import Dict, List, Any, Optional, cast
from redis import Redis, ConnectionPool
from redis.asyncio import Redis as AsyncRedis, ConnectionPool as AsyncConnectionPool

from .base import GraphDatabase
from .errors import ConnectionError
from .query import Query
from .config import Config


class FalkorDBGraphDatabase(GraphDatabase):
    """FalkorDB graph database implementation using RedisGraph."""

    def __init__(self, pool_size: int = 5):
        super().__init__(pool_size=pool_size)
        self.client: Optional[Redis] = None
        self.async_client: Optional[AsyncRedis] = None
        self.graph_name: str = "graph"
        self.pool: Optional[ConnectionPool] = None
        self.async_pool: Optional[AsyncConnectionPool] = None

    def connect(self, skip_ping: bool = False, **kwargs) -> bool:
        """Connect to FalkorDB (RedisGraph).

        Args:
            skip_ping: If True, skip testing the connection with ping.
            **kwargs: Additional configuration overrides.

        Returns:
            bool: True if connection successful.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            config = Config.get_falkordb_config()
            config.update(kwargs)

            self.pool = ConnectionPool(
                host=config['host'],
                port=config['port'],
                username=config['username'],
                password=config['password'],
                decode_responses=True
            )
            self.client = Redis(connection_pool=self.pool)
            self.graph_name = config.get('graph_name', 'graph')

            # Test connection (unless skip_ping is True)
            if not skip_ping:
                self.client.ping()
            self.connected = True
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to FalkorDB: {str(e)}")

    async def connect_async(self, skip_ping: bool = False, **kwargs) -> bool:
        """Async connect to FalkorDB.

        Args:
            skip_ping: If True, skip testing the connection with ping.
            **kwargs: Additional configuration overrides.

        Returns:
            bool: True if connection successful.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            config = Config.get_falkordb_config()
            config.update(kwargs)

            self.async_pool = AsyncConnectionPool(
                host=config['host'],
                port=config['port'],
                username=config['username'],
                password=config['password'],
                decode_responses=True
            )
            self.async_client = AsyncRedis(connection_pool=self.async_pool)
            self.graph_name = config.get('graph_name', 'graph')

            # Test connection (unless skip_ping is True)
            if not skip_ping:
                await self.async_client.ping()
            self.connected = True
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to FalkorDB: {str(e)}")

    def disconnect(self) -> bool:
        """Disconnect from FalkorDB (RedisGraph) for synchronous clients."""
        if self.client:
            self.client.close()
            self.client = None
        if self.pool:
            self.pool.disconnect()
            self.pool = None
        self.connected = False
        return True

    async def disconnect_async(self) -> bool:
        """Async disconnect from FalkorDB."""
        if self.async_client:
            await self.async_client.close()
            self.async_client = None
        if self.async_pool:
            await self.async_pool.disconnect()
            self.async_pool = None
        self.connected = False
        return True

    async def _execute_graph_query_async(self, query_str: str, *args) -> Any:
        """Execute a RedisGraph query asynchronously."""
        if not self.async_client:
            raise ConnectionError("Database not connected")

        # Rewrite "CONTAINS(n.someProp, 'val')" -> "n.someProp =~ '.*val.*'"
        pattern = r"CONTAINS\(n\.(\w+),\s*'([^']*)'\)"
        repl = r"n.\1 =~ '.*\2.*'"
        query_str = re.sub(pattern, repl, query_str)

        client = cast(AsyncRedis, self.async_client)
        return await client.execute_command("GRAPH.QUERY", self.graph_name, query_str, "COMPACT", *args)

    def _execute_graph_query(self, query_str: str, *args) -> Any:
        """
        Execute a RedisGraph query, rewriting "CONTAINS(...)" to a regex match 
        that RedisGraph understands, and also specifying "COMPACT" for a simpler response.
        """
        if not self.client:
            raise ConnectionError("Database not connected")

        pattern = r"CONTAINS\(n\.(\w+),\s*'([^']*)'\)"
        repl = r"n.\1 =~ '.*\2.*'"
        query_str = re.sub(pattern, repl, query_str)

        client = cast(Redis, self.client)
        return client.execute_command("GRAPH.QUERY", self.graph_name, query_str, "COMPACT", *args)

    def _parse_properties(self, props: Any) -> Dict[str, Any]:
        """
        Convert the result of 'properties(n)' to a Python dict.
        If it's a node dictionary or string, parse carefully.
        """
        if not props:
            return {}
        if isinstance(props, dict):
            return props
        if not isinstance(props, str):
            return {}

        try:
            val = ast.literal_eval(props)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

        # Fallback parse: "k=v" or "k:v"
        result: Dict[str, Any] = {}
        tokens = re.split(r"[,\s]+", props.strip())
        for tok in tokens:
            if '=' in tok:
                sep = '='
            elif ':' in tok:
                sep = ':'
            else:
                continue
            parts = tok.split(sep, 1)
            if len(parts) == 2:
                k = parts[0].strip()
                v = parts[1].strip().strip('"').strip("'")
                result[k] = v
        return result

    def _extract_id_from_cell(self, cell) -> int:
        """Safely extract a numeric ID from the cell, which might be string '42', int 42, or dict."""
        if isinstance(cell, int):
            return cell
        if isinstance(cell, str) and cell.isdigit():
            return int(cell)
        if isinstance(cell, dict) and "id" in cell:
            return int(cell["id"])
        raise ValueError(f"Unexpected row cell for ID: {cell!r}")

    #
    # NODE OPERATIONS
    #
    async def _create_node_async_impl(self, label: str, properties: Dict[str, Any]) -> str:
        """Async implementation of node creation."""
        if not self.validate_node(label, properties):
            raise ValueError("Node validation failed")

        props_copy = {}
        for k, v in properties.items():
            if isinstance(v, list):
                v = ",".join(str(x) for x in v)
            props_copy[k] = v

        props_str = ", ".join(
            f"{k}: '{val}'" if isinstance(val, str) else f"{k}: {val}"
            for k, val in props_copy.items()
        )
        cypher = f"CREATE (n:{label} {{{props_str}}}) RETURN ID(n)"
        raw = await self._execute_graph_query_async(cypher)
        if not raw or len(raw) < 2 or not raw[1]:
            raise ValueError("Failed to create node in RedisGraph (no rows)")
        first_row = raw[1][0]
        if not first_row:
            raise ValueError("Failed to create node (empty row)")

        return str(self._extract_id_from_cell(first_row[0]))

    def _create_node_impl(self, label: str, properties: Dict[str, Any]) -> int:
        if not self.validate_node(label, properties):
            raise ValueError("Node validation failed")

        props_copy = {}
        for k, v in properties.items():
            if isinstance(v, list):
                v = ",".join(str(x) for x in v)
            props_copy[k] = v

        props_str = ", ".join(
            f"{k}: '{val}'" if isinstance(val, str) else f"{k}: {val}"
            for k, val in props_copy.items()
        )
        cypher = f"CREATE (n:{label} {{{props_str}}}) RETURN ID(n)"
        raw = self._execute_graph_query(cypher)
        if not raw or len(raw) < 2 or not raw[1]:
            raise ValueError("Failed to create node in RedisGraph (no rows)")
        first_row = raw[1][0]
        if not first_row:
            raise ValueError("Failed to create node (empty row)")

        return self._extract_id_from_cell(first_row[0])

    def _get_node_impl(self, node_id: str) -> Optional[Dict[str, Any]]:
        try:
            node_id_int = int(node_id)
        except ValueError:
            return None
        cypher = f"MATCH (n) WHERE ID(n) = {node_id_int} RETURN n"
        raw = self._execute_graph_query(cypher)
        if not raw or len(raw) < 2 or not raw[1]:
            return None
        row = raw[1][0]
        if not row:
            return None
        cell = row[0]
        if isinstance(cell, dict):
            return {
                "id": str(cell.get("id", "")),
                "label": cell.get("labels", [None])[0],
                "properties": cell.get("properties", {})
            }
        return None

    def _update_node_impl(self, node_id: str, properties: Dict[str, Any]) -> bool:
        curr = self._get_node_impl(node_id)
        if not curr:
            return False

        updated_props = {**curr["properties"], **properties}
        if not self.validate_node(curr["label"], updated_props):
            raise ValueError("Node validation failed")

        props_copy = {}
        for k, v in properties.items():
            if isinstance(v, list):
                v = ",".join(str(x) for x in v)
            props_copy[k] = v

        set_expr = ", ".join(
            f"n.{k} = '{val}'" if isinstance(val, str) else f"n.{k} = {val}"
            for k, val in props_copy.items()
        )
        cypher = f"MATCH (n) WHERE ID(n) = {node_id} SET {set_expr} RETURN ID(n)"
        raw = self._execute_graph_query(cypher)
        if not raw or len(raw) < 2 or not raw[1]:
            return False
        return True

    def _delete_node_impl(self, node_id: str) -> bool:
        try:
            node_id_int = int(node_id)
        except ValueError:
            return False
        cypher = f"MATCH (n) WHERE ID(n) = {node_id_int} DETACH DELETE n"
        self._execute_graph_query(cypher)
        return True

    #
    # EDGE OPERATIONS
    #
    def _create_edge_impl(self, from_id: str, to_id: str, label: str, properties: Dict[str, Any]) -> int:
        if not self._get_node_impl(from_id) or not self._get_node_impl(to_id):
            raise ValueError("One or both nodes do not exist")
        if not self.validate_edge(label, properties):
            raise ValueError("Edge validation failed")

        props_copy = {}
        for k, v in properties.items():
            if isinstance(v, list):
                v = ",".join(str(x) for x in v)
            props_copy[k] = v

        props_str = ""
        if props_copy:
            plist = [
                f"{kk}: '{vv}'" if isinstance(vv, str) else f"{kk}: {vv}"
                for kk, vv in props_copy.items()
            ]
            props_str = " {" + ", ".join(plist) + "}"

        cypher = (
            f"MATCH (a), (b) "
            f"WHERE ID(a) = {from_id} AND ID(b) = {to_id} "
            f"CREATE (a)-[r:{label}{props_str}]->(b) RETURN ID(r)"
        )
        raw = self._execute_graph_query(cypher)
        if not raw or len(raw) < 2 or not raw[1]:
            raise ValueError("Failed to create edge")
        first_row = raw[1][0]
        return self._extract_id_from_cell(first_row[0])

    def _get_edge_impl(self, edge_id: str) -> Optional[Dict[str, Any]]:
        try:
            edge_id_int = int(edge_id)
        except ValueError:
            return None
        cypher = f"MATCH ()-[r]->() WHERE ID(r) = {edge_id_int} RETURN r"
        raw = self._execute_graph_query(cypher)
        if not raw or len(raw) < 2 or not raw[1]:
            return None
        row = raw[1][0]
        if not row:
            return None
        cell = row[0]
        if isinstance(cell, dict):
            return {
                "label": cell.get("type", ""),
                "properties": cell.get("properties", {}),
                "from_id": str(cell.get("src_node", "")),
                "to_id": str(cell.get("dst_node", ""))
            }
        return None

    def _update_edge_impl(self, edge_id: str, properties: Dict[str, Any]) -> bool:
        curr = self._get_edge_impl(edge_id)
        if not curr:
            return False
        updated_props = {**curr["properties"], **properties}
        if not self.validate_edge(curr["label"], updated_props):
            raise ValueError("Edge validation failed")

        props_copy = {}
        for k, v in properties.items():
            if isinstance(v, list):
                v = ",".join(str(x) for x in v)
            props_copy[k] = v

        set_expr = ", ".join(
            f"r.{kk} = '{vv}'" if isinstance(vv, str) else f"r.{kk} = {vv}"
            for kk, vv in props_copy.items()
        )
        cypher = f"MATCH ()-[r]->() WHERE ID(r) = {edge_id} SET {set_expr} RETURN ID(r)"
        raw = self._execute_graph_query(cypher)
        if not raw or len(raw) < 2 or not raw[1]:
            return False
        return True

    def _delete_edge_impl(self, edge_id: str) -> bool:
        try:
            edge_id_int = int(edge_id)
        except ValueError:
            return False
        cypher = f"MATCH ()-[r]->() WHERE ID(r) = {edge_id_int} DELETE r"
        self._execute_graph_query(cypher)
        return True

    #
    # QUERY IMPLEMENTATION
    #
    def _build_cypher_query(self, query: Query) -> str:
        parts = ["MATCH (n)"]
        wheres = []

        if query.vector_search:
            vector_field = query.vector_search["field"]
            vector = query.vector_search["vector"]
            k = query.vector_search["k"]
            min_score = query.vector_search.get("min_score")

            # Calculate cosine similarity using FalkorDB's vector functions
            similarity_expr = f"vector.similarity(n.{vector_field}, {vector}) AS similarity"
            parts.append(f"WITH n, {similarity_expr}")

            if min_score is not None:
                wheres.append(f"similarity >= {min_score}")

            # Add sorting by similarity
            parts.append("ORDER BY similarity DESC")
            if k:
                parts.append(f"LIMIT {k}")
        for f in query.filters:
            if hasattr(f, "filter_type"):
                t = f.filter_type
                if t == "label_equals":
                    wheres.append(f"n:{f.label}")
                elif t == "property_equals":
                    wheres.append(f"n.{f.property_name} = {repr(f.value)}")
                elif t == "property_contains":
                    # produce EXACT "CONTAINS(n.X, 'Y')"
                    wheres.append(f"CONTAINS(n.{f.property_name}, {repr(f.value)})")

        if wheres:
            parts.append("WHERE " + " AND ".join(wheres))

        if query.sort_key:
            direction = "DESC" if query.sort_reverse else "ASC"
            parts.append(f"ORDER BY n.{query.sort_key} {direction}")

        if query.limit:
            parts.append(f"LIMIT {query.limit}")

        parts.append("RETURN n")
        return " ".join(parts)

    async def _query_async_impl(self, query: Query) -> List[Dict[str, Any]]:
        """Async implementation of query operation."""
        cypher = self._build_cypher_query(query)
        raw = await self._execute_graph_query_async(cypher)
        data_rows = raw[1] if raw and len(raw) > 1 else []

        results = []
        for record in data_rows:
            if not record:
                continue
            cell = record[0]
            if isinstance(cell, dict):
                results.append({
                    "id": str(cell.get("id", "")),
                    "label": cell.get("labels", [""])[0],
                    "properties": cell.get("properties", {})
                })
        return results

    def _query_impl(self, query: Query) -> List[Dict[str, Any]]:
        cypher = self._build_cypher_query(query)
        raw = self._execute_graph_query(cypher)
        data_rows = raw[1] if raw and len(raw) > 1 else []

        results = []
        for record in data_rows:
            if not record:
                continue
            cell = record[0]
            if isinstance(cell, dict):
                results.append({
                    "id": str(cell.get("id", "")),
                    "label": cell.get("labels", [""])[0],
                    "properties": cell.get("properties", {})
                })
        return results

    #
    # BATCH IMPLEMENTATION
    #
    def _batch_create_nodes_impl(self, nodes: List[Dict[str, Any]]) -> List[str]:
        for n in nodes:
            if not self.validate_node(n["label"], n["properties"]):
                raise ValueError(f"Node validation failed for node: {n}")

        queries = []
        for node in nodes:
            props_copy = {}
            for k, v in node["properties"].items():
                if isinstance(v, list):
                    v = ",".join(str(x) for x in v)
                props_copy[k] = v

            props_str = ", ".join(
                f"{kk}: '{vv}'" if isinstance(vv, str) else f"{kk}: {vv}"
                for kk, vv in props_copy.items()
            )
            queries.append(f"CREATE (n:{node['label']} {{{props_str}}}) RETURN ID(n)")

        union_query = " UNION ALL ".join(queries)
        raw = self._execute_graph_query(union_query)
        if not raw or len(raw) < 2:
            return []

        data_rows = raw[1]
        node_ids: List[str] = []
        for row in data_rows:
            if not row:
                continue
            val = row[0]
            node_id_int = self._extract_id_from_cell(val)
            node_ids.append(str(node_id_int))
        return node_ids

    def _batch_create_edges_impl(self, edges: List[Dict[str, Any]]) -> List[str]:
        for e in edges:
            if not self.validate_edge(e["label"], e.get("properties", {})):
                raise ValueError(f"Edge validation failed for {e}")

        queries = []
        for edge in edges:
            from_id = edge["from_id"]
            to_id = edge["to_id"]
            props_copy = {}
            for k, v in edge.get("properties", {}).items():
                if isinstance(v, list):
                    v = ",".join(str(x) for x in v)
                props_copy[k] = v

            props_str = ""
            if props_copy:
                plist = [
                    f"{kk}: '{vv}'" if isinstance(vv, str) else f"{kk}: {vv}"
                    for kk, vv in props_copy.items()
                ]
                props_str = " {" + ", ".join(plist) + "}"

            queries.append(
                f"MATCH (a), (b) "
                f"WHERE ID(a) = {from_id} AND ID(b) = {to_id} "
                f"CREATE (a)-[r:{edge['label']}{props_str}]->(b) RETURN ID(r)"
            )

        union_query = " UNION ALL ".join(queries)
        raw = self._execute_graph_query(union_query)
        if not raw or len(raw) < 2:
            return []

        data_rows = raw[1]
        edge_ids: List[str] = []
        for row in data_rows:
            if not row:
                continue
            val = row[0]
            edge_id = self._extract_id_from_cell(val)
            edge_ids.append(str(edge_id))
        return edge_ids
