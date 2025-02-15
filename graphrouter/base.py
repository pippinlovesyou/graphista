"""
Base abstract classes for graph database implementations.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import time as _time

from .ontology import Ontology
from .query import Query
from .cache import QueryCache
from .monitoring import PerformanceMonitor
from .errors import ConnectionError, InvalidNodeTypeError, InvalidPropertyError


class GraphDatabase(ABC):
    """Abstract base class for graph database implementations."""

    def __init__(self, pool_size: int = 5):
        self.ontology: Optional[Ontology] = None
        self.connected: bool = False
        self._pool_size = pool_size
        self._connection_pool = []
        self._cache = QueryCache()
        self._monitor = PerformanceMonitor()

    #
    # Connection
    #
    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """Connect to the database."""
        pass

    async def connect_async(self, **kwargs) -> bool:
        """Async connect to the database."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the database."""
        pass

    async def disconnect_async(self) -> bool:
        """Async disconnect from the database."""
        pass

    async def create_node_async(self, label: str, properties: Dict[str, Any] = None) -> str:
        if not self.connected:
            raise ConnectionError("Database not connected")
        if properties is None:
            raise ValueError("Properties cannot be None")
        if self.ontology:
            properties = self.ontology.map_node_properties(label, properties)
        if not self.validate_node(label, properties):
            raise ValueError("Node validation failed")
        start_time = _time.perf_counter()
        node_id = await self._create_node_async_impl(label, properties)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("create_node_async", duration)
        return node_id

    @abstractmethod
    async def _create_node_async_impl(self, label: str, properties: Dict[str, Any]) -> str:
        pass

    async def query_async(self, query: Query) -> List[Dict[str, Any]]:
        if not self.connected:
            raise ConnectionError("Database not connected")
        cache_key = f"query:{hash(str(query))}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        start_time = _time.perf_counter()
        results = await self._query_async_impl(query)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("query_async", duration)
        self._cache.set(cache_key, results)
        query._execution_time = duration
        query._memory_used = float(len(str(results)))
        return results

    @abstractmethod
    async def _query_async_impl(self, query: Query) -> List[Dict[str, Any]]:
        pass

    #
    # NODE OPERATIONS
    #
    def create_node(self, label: str, properties: Dict[str, Any] = None) -> str:
        if not self.connected:
            raise ConnectionError("Database not connected")
        if properties is None:
            raise ValueError("Properties cannot be None")
        if self.ontology:
            properties = self.ontology.map_node_properties(label, properties)
        if not self.validate_node(label, properties):
            raise ValueError("Node validation failed")
        start_time = _time.perf_counter()
        node_id = self._create_node_impl(label, properties)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("create_node", duration)
        return node_id

    @abstractmethod
    def _create_node_impl(self, label: str, properties: Dict[str, Any]) -> str:
        pass

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            raise ConnectionError("Database not connected")
        cache_key = f"node:{node_id}"
        cached_result = self._cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        start_time = _time.perf_counter()
        node = self._get_node_impl(node_id)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("get_node", duration)
        if node is not None:
            self._cache.set(cache_key, node)
        return node

    @abstractmethod
    def _get_node_impl(self, node_id: str) -> Optional[Dict[str, Any]]:
        pass

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        if not self.connected:
            raise ConnectionError("Database not connected")
        if properties is None:
            raise ValueError("Properties cannot be None")
        start_time = _time.perf_counter()
        current = self._get_node_impl(node_id)
        if not current:
            return False
        updated_props = {**current["properties"], **properties}
        if not self.validate_node(current["label"], updated_props):
            raise ValueError("Node validation failed")
        success = self._update_node_impl(node_id, properties)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("update_node", duration)
        self._cache.invalidate(f"node:{node_id}")
        return success

    @abstractmethod
    def _update_node_impl(self, node_id: str, properties: Dict[str, Any]) -> bool:
        pass

    def delete_node(self, node_id: str) -> bool:
        if not self.connected:
            raise ConnectionError("Database not connected")
        start_time = _time.perf_counter()
        success = self._delete_node_impl(node_id)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("delete_node", duration)
        self._cache.invalidate(f"node:{node_id}")
        return success

    @abstractmethod
    def _delete_node_impl(self, node_id: str) -> bool:
        pass

    #
    # EDGE OPERATIONS
    #
    def create_edge(self, from_id: str, to_id: str, label: str, properties: Optional[Dict[str, Any]] = None) -> str:
        if not self.connected:
            raise ConnectionError("Database not connected")
        if properties is None:
            raise ValueError("Properties cannot be None")
        if self.ontology:
            properties = self.ontology.map_edge_properties(label, properties)
        if not self.validate_edge(label, properties):
            raise ValueError("Edge validation failed")
        start_time = _time.perf_counter()
        edge_id = self._create_edge_impl(from_id, to_id, label, properties)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("create_edge", duration)
        return edge_id

    @abstractmethod
    def _create_edge_impl(self, from_id: str, to_id: str, label: str, properties: Dict[str, Any]) -> str:
        pass

    def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            raise ConnectionError("Database not connected")
        cache_key = f"edge:{edge_id}"
        cached_result = self._cache.get(cache_key)
        if cached_result is not None:
            return cached_result
        start_time = _time.perf_counter()
        edge = self._get_edge_impl(edge_id)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("get_edge", duration)
        if edge is not None:
            self._cache.set(cache_key, edge)
        return edge

    @abstractmethod
    def _get_edge_impl(self, edge_id: str) -> Optional[Dict[str, Any]]:
        pass

    def update_edge(self, edge_id: str, properties: Dict[str, Any]) -> bool:
        if not self.connected:
            raise ConnectionError("Database not connected")
        if properties is None:
            raise ValueError("Properties cannot be None")
        start_time = _time.perf_counter()
        current = self._get_edge_impl(edge_id)
        if not current:
            return False
        updated_props = {**current["properties"], **properties}
        if not self.validate_edge(current["label"], updated_props):
            raise ValueError("Edge validation failed")
        success = self._update_edge_impl(edge_id, properties)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("update_edge", duration)
        self._cache.invalidate(f"edge:{edge_id}")
        return success

    @abstractmethod
    def _update_edge_impl(self, edge_id: str, properties: Dict[str, Any]) -> bool:
        pass

    def delete_edge(self, edge_id: str) -> bool:
        if not self.connected:
            raise ConnectionError("Database not connected")
        start_time = _time.perf_counter()
        success = self._delete_edge_impl(edge_id)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("delete_edge", duration)
        self._cache.invalidate(f"edge:{edge_id}")
        return success

    @abstractmethod
    def _delete_edge_impl(self, edge_id: str) -> bool:
        pass

    #
    # QUERY
    #
    def query(self, query: Query) -> List[Dict[str, Any]]:
        if not self.connected:
            raise ConnectionError("Database not connected")
        cache_key = f"query:{hash(str(query))}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        start_time = _time.perf_counter()
        results = self._query_impl(query)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("query", duration)
        self._cache.set(cache_key, results)
        query._execution_time = duration
        query._memory_used = float(len(str(results)))
        return results

    @abstractmethod
    def _query_impl(self, query: Query) -> List[Dict[str, Any]]:
        pass

    #
    # BATCH OPERATIONS
    #
    def batch_create_nodes(self, nodes: List[Dict[str, Any]]) -> List[str]:
        if not self.connected:
            raise ConnectionError("Database not connected")
        start_time = _time.perf_counter()
        for node in nodes:
            if 'label' not in node or 'properties' not in node:
                raise ValueError("Invalid node format")
            if node['properties'] is None:
                raise ValueError("Properties cannot be None")
            if not self.validate_node(node['label'], node['properties']):
                raise ValueError(f"Node validation failed for node: {node}")
        node_ids = self._batch_create_nodes_impl(nodes)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("batch_create_nodes", duration)
        return node_ids

    @abstractmethod
    def _batch_create_nodes_impl(self, nodes: List[Dict[str, Any]]) -> List[str]:
        pass

    def batch_create_edges(self, edges: List[Dict[str, Any]]) -> List[str]:
        if not self.connected:
            raise ConnectionError("Database not connected")
        start_time = _time.perf_counter()
        for edge in edges:
            if not all(k in edge for k in ['from_id', 'to_id', 'label']):
                raise ValueError("Invalid edge format")
            props = edge.get('properties', {})
            if props is None:
                raise ValueError("Properties cannot be None")
            if not self.validate_edge(edge['label'], props):
                raise ValueError(f"Edge validation failed for edge: {edge}")
        edge_ids = self._batch_create_edges_impl(edges)
        duration = _time.perf_counter() - start_time
        self._monitor.record_operation("batch_create_edges", duration)
        return edge_ids

    @abstractmethod
    def _batch_create_edges_impl(self, edges: List[Dict[str, Any]]) -> List[str]:
        pass

    #
    # ONTOLOGY / VALIDATION
    #
    def set_ontology(self, ontology: Ontology):
        self.ontology = ontology

    def validate_node(self, label: str, properties: Dict[str, Any]) -> bool:
        if not self.ontology:
            return True
        try:
            self.ontology.validate_node(label, properties)
            return True
        except (InvalidNodeTypeError, InvalidPropertyError):
            return False

    def validate_edge(self, label: str, properties: Dict[str, Any]) -> bool:
        if not self.ontology:
            return True
        try:
            self.ontology.validate_edge(label, properties)
            return True
        except (InvalidNodeTypeError, InvalidPropertyError):
            return False

    #
    # MONITORING / CACHE
    #
    def get_performance_metrics(self) -> Dict[str, float]:
        return self._monitor.get_average_times()

    def reset_metrics(self):
        self._monitor.reset()

    def clear_cache(self):
        self._cache = QueryCache()

    # NEW HELPER METHODS FOR QUERY-ONLY READ OPERATIONS
    def get_edges_of_node(self, node_id: str, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all edges connected to a node. Optionally filter by edge type."""
        result = []
        if hasattr(self, 'edges'):
            edges = self.edges if isinstance(self.edges, list) else list(self.edges.values())
            for edge in edges:
                if edge.get("from_id") == node_id or edge.get("to_id") == node_id:
                    if edge_type is None or edge.get("label", "").lower() == edge_type.lower():
                        result.append(edge)
        return result

    def get_connected_nodes(self, node_id: str, edge_type: Optional[str] = None, direction: str = "both") -> List[Dict[str, Any]]:
        """Return all nodes connected to a given node via edges.
        'direction' can be 'out', 'in', or 'both'.
        """
        connected = []
        edges = self.get_edges_of_node(node_id, edge_type)
        for edge in edges:
            if direction.lower() == "out" and edge.get("from_id") == node_id:
                other_id = edge.get("to_id")
            elif direction.lower() == "in" and edge.get("to_id") == node_id:
                other_id = edge.get("from_id")
            elif direction.lower() == "both":
                if edge.get("from_id") == node_id:
                    other_id = edge.get("to_id")
                elif edge.get("to_id") == node_id:
                    other_id = edge.get("from_id")
                else:
                    continue
            else:
                continue
            node = self.get_node(other_id)
            if node:
                connected.append(node)
        return connected

    def get_node_by_property(self, property_name: str, value: Any) -> List[Dict[str, Any]]:
        """Return all nodes that have a specific property value."""
        result = []
        if hasattr(self, 'nodes'):
            nodes = self.nodes if isinstance(self.nodes, list) else list(self.nodes.values())
            for node in nodes:
                if node.get("properties", {}).get(property_name) == value:
                    result.append(node)
        return result

    def get_nodes_with_property(self, property_name: str) -> List[Dict[str, Any]]:
        """Return all nodes that have a specific property present."""
        result = []
        if hasattr(self, 'nodes'):
            nodes = self.nodes if isinstance(self.nodes, list) else list(self.nodes.values())
            for node in nodes:
                if property_name in node.get("properties", {}):
                    result.append(node)
        return result
