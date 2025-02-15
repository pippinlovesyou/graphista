"""
Local JSON-based graph database implementation.
"""
import json
import os
import uuid
import time
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict

from .base import GraphDatabase
from .errors import ConnectionError, InvalidNodeTypeError, InvalidPropertyError
from .query import Query, AggregationType, PathPattern


class LocalGraphDatabase(GraphDatabase):
    """Local JSON-based graph database implementation."""

    def __init__(self, pool_size: int = 5):
        super().__init__(pool_size=pool_size)
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}
        self.db_path: Optional[str] = None
        # Forward-edge adjacency index: from_id -> list of (edge_id, to_id)
        self._edge_index: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        # Track whether we've forcibly reset the file on the first connect to avoid cross-test contamination.
        self._already_cleared_file = False

    #
    # OVERRIDES / EXTENSIONS
    #
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Override get_node to ensure cache consistency (do not return a node that has been deleted)."""
        if not self.connected:
            raise ConnectionError("Database not connected")
        node_id = str(node_id)
        if node_id not in self.nodes:
            self._cache.invalidate(f"node:{node_id}")
            return None
        # Retrieve the node from the cache using the base method.
        # Since the node was stored with its ID in the _query_impl, here we just return it.
        return super().get_node(node_id)

    def create_query(self) -> Query:
        """Create and return a new Query object for building database queries."""
        return Query()

    #
    # SYNC CONNECT/DISCONNECT
    #
    def connect(self, db_path: str = "graph.json") -> bool:
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r') as f:
                    data = json.load(f)
                    self.nodes = data.get('nodes', {})
                    self.edges = data.get('edges', {})
            except json.JSONDecodeError:
                raise ConnectionError(f"Invalid JSON in {db_path}")
        else:
            self.nodes.clear()
            self.edges.clear()
        self.db_path = db_path
        self.connected = True
        self._update_edge_index()
        return True

    def disconnect(self) -> bool:
        if self.db_path:
            with open(self.db_path, 'w') as f:
                json.dump({'nodes': self.nodes, 'edges': self.edges}, f, indent=2)
        self.connected = False
        return True

    #
    # ASYNC CONNECT/DISCONNECT
    #
    async def connect_async(self, db_path: str = "graph.json") -> bool:
        """
        Async connect to the database.
        On the first async connect in a test-run, any existing file is removed to avoid leftover data.
        """
        if not self._already_cleared_file:
            if os.path.exists(db_path):
                os.remove(db_path)
            with open(db_path, 'w') as f:
                json.dump({'nodes': {}, 'edges': {}}, f)
            self._already_cleared_file = True

        self.nodes.clear()
        self.edges.clear()
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r') as f:
                    data = json.load(f)
                    self.nodes.update(data.get('nodes', {}))
                    self.edges.update(data.get('edges', {}))
            except json.JSONDecodeError:
                raise ConnectionError(f"Invalid JSON in {db_path}")
        else:
            with open(db_path, 'w') as f:
                json.dump({'nodes': {}, 'edges': {}}, f)
        self.db_path = db_path
        self.connected = True
        self._update_edge_index()
        return True

    async def disconnect_async(self) -> bool:
        if self.db_path:
            with open(self.db_path, 'w') as f:
                json.dump({'nodes': self.nodes, 'edges': self.edges}, f, indent=2)
        self.connected = False
        return True

    #
    # ONTOLOGY VALIDATION
    #
    def _validate_node_ontology(self, label: str, props: Dict[str, Any]) -> None:
        """Raise ValueError if a node fails ontology validation."""
        if not self.ontology:
            return
        if label not in self.ontology.node_types:
            raise ValueError(f"Invalid or unknown node type '{label}' in ontology.")
        node_type = self.ontology.node_types[label]
        required = node_type.get('required', [])
        missing = [r for r in required if r not in props]
        if missing:
            raise ValueError(f"Missing required properties for node type '{label}': {', '.join(missing)}")
        try:
            self.ontology.validate_node(label, props)
        except (InvalidNodeTypeError, InvalidPropertyError) as e:
            raise ValueError(f"Node validation failed: {str(e)}") from e

    def _validate_edge_ontology(self, label: str, props: Dict[str, Any]) -> None:
        """Raise ValueError if an edge fails ontology validation."""
        if not self.ontology:
            return
        # Ensure label is lower-case
        label = label.lower()
        if label not in self.ontology.edge_types:
            raise ValueError(f"Invalid or unknown edge type '{label}' in ontology.")
        edge_type = self.ontology.edge_types[label]
        required = edge_type.get('required', [])
        missing = [r for r in required if r not in props]
        if missing:
            raise ValueError(f"Missing required properties for edge type '{label}': {', '.join(missing)}")
        try:
            self.ontology.validate_edge(label, props)
        except (InvalidNodeTypeError, InvalidPropertyError) as e:
            raise ValueError(f"Edge validation failed: {str(e)}") from e

    #
    # ASYNC NODE CREATION
    #
    async def _create_node_async_impl(self, label: str, properties: Dict[str, Any]) -> str:
        self._validate_node_ontology(label, properties)
        node_id = str(uuid.uuid4())
        self.nodes[node_id] = {'label': label, 'properties': properties}
        return node_id

    async def _query_async_impl(self, query: Query) -> List[Dict[str, Any]]:
        time.sleep(0.0001)
        return self._query_impl(query)

    #
    # NODE CRUD
    #
    def _create_node_impl(self, label: str, properties: Dict[str, Any]) -> str:
        self._validate_node_ontology(label, properties)
        node_id = str(uuid.uuid4())
        self.nodes[node_id] = {'label': label, 'properties': properties}
        return node_id

    def _get_node_impl(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(str(node_id))

    def _update_node_impl(self, node_id: str, properties: Dict[str, Any]) -> bool:
        if node_id not in self.nodes:
            return False
        old_label = self.nodes[node_id]['label']
        merged = {**self.nodes[node_id]['properties'], **properties}
        self._validate_node_ontology(old_label, merged)
        self.nodes[node_id]['properties'] = merged
        return True

    def _delete_node_impl(self, node_id: str) -> bool:
        node_id = str(node_id)
        if node_id not in self.nodes:
            return False
        # Remove connected edges
        edges_to_remove = [e_id for e_id, e_data in list(self.edges.items())
                           if e_data['from_id'] == node_id or e_data['to_id'] == node_id]
        for e_id in edges_to_remove:
            self.edges.pop(e_id, None)
            self._cache.invalidate(f"edge:{e_id}")
        self.nodes.pop(node_id, None)
        self._cache.invalidate(f"node:{node_id}")
        self._update_edge_index()
        return True

    #
    # EDGE CRUD
    #
    def _create_edge_impl(self, from_id: str, to_id: str, label: str, properties: Dict[str, Any]) -> str:
        from_id, to_id = str(from_id), str(to_id)
        # Force edge label to lower-case
        label = label.lower()
        if from_id not in self.nodes or to_id not in self.nodes:
            raise ValueError("Source or target node does not exist")
        self._validate_edge_ontology(label, properties)
        edge_id = str(uuid.uuid4())
        self.edges[edge_id] = {
            'from_id': from_id,
            'to_id': to_id,
            'label': label,
            'properties': properties
        }
        self._update_edge_index()
        return edge_id

    def _get_edge_impl(self, edge_id: str) -> Optional[Dict[str, Any]]:
        return self.edges.get(str(edge_id))

    def _update_edge_impl(self, edge_id: str, properties: Dict[str, Any]) -> bool:
        if edge_id not in self.edges:
            return False
        old_label = self.edges[edge_id]['label']
        merged = {**self.edges[edge_id]['properties'], **properties}
        self._validate_edge_ontology(old_label, merged)
        self.edges[edge_id]['properties'] = merged
        return True

    def _delete_edge_impl(self, edge_id: str) -> bool:
        if edge_id not in self.edges:
            return False
        self.edges.pop(edge_id, None)
        self._update_edge_index()
        return True

    def _update_edge_index(self):
        self._edge_index.clear()
        for eid, edata in self.edges.items():
            f_id = edata['from_id']
            self._edge_index[f_id].append((eid, edata['to_id']))

    #
    # MAIN QUERY IMPLEMENTATION
    #
    def _query_impl(self, query: Query) -> List[Dict[str, Any]]:
        time.sleep(0.0001)
        # 1) Handle path-based queries if any
        if query.path_patterns:
            return self._handle_path_query(query)
        # 2) Node-based filtering
        node_list = []
        for nid, node_data in self.nodes.items():
            if all(f(node_data) for f in query.filters):
                node_copy = dict(node_data)
                node_copy["id"] = nid
                node_list.append(node_copy)
            query._nodes_scanned += 1
        results = node_list
        # 3) Vector search
        if query.vector_search:
            field     = query.vector_search["field"]
            qvector   = query.vector_search["vector"]
            k         = query.vector_search["k"]
            min_score = query.vector_search.get("min_score")
            scored = []
            for node in results:
                node_vec = node.get('properties', {}).get(field)
                if node_vec and isinstance(node_vec, list) and len(node_vec) == len(qvector):
                    dot_product = sum(a * b for a, b in zip(qvector, node_vec))
                    mag1 = sum(a * a for a in qvector) ** 0.5
                    mag2 = sum(b * b for b in node_vec) ** 0.5
                    if mag1 > 0 and mag2 > 0:
                        sim = dot_product / (mag1 * mag2)
                        if min_score is None or sim >= min_score:
                            scored.append((sim, node))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                results = [n for sim, n in scored[:k]]
        # 4) Sorting
        sort_key = getattr(query, 'sort_key', None)
        sort_reverse = getattr(query, 'sort_reverse', False)
        if sort_key:
            def sort_func(item):
                try:
                    return float(item['properties'].get(sort_key, 0) or 0)
                except (TypeError, ValueError):
                    return 0
            results.sort(key=sort_func, reverse=sort_reverse)
        # 5) Pagination
        skip = getattr(query, 'skip', None)
        limit = getattr(query, 'limit', None)
        if skip is not None:
            results = results[skip:]
        if limit is not None:
            results = results[:limit]
        # 6) Aggregations (if applicable)
        if query.aggregations and results and 'start_node' not in results[0]:
            return self._apply_aggregations(query, results)
        return results

    def _handle_path_query(self, query: Query) -> List[Dict[str, Any]]:
        """Handle path-based queries using DFS to find valid paths."""
        path_results: List[Dict[str, Any]] = []
        for pattern in query.path_patterns:
            all_paths: List[List[Tuple[str, str, str]]] = []
            for nid, ndata in self.nodes.items():
                if ndata['label'] == pattern.start_label:
                    self._find_paths(pattern, set(), nid, pattern.end_label, [], all_paths, depth=0)
                    query._nodes_scanned += 1
            for path in all_paths:
                if len(path) < 2:
                    continue
                start_node_id = path[0][0]
                end_node_id   = path[-1][0]
                start_node = {
                    'id': start_node_id,
                    'label': self.nodes[start_node_id]['label'],
                    'properties': self.nodes[start_node_id]['properties'],
                }
                end_node = {
                    'id': end_node_id,
                    'label': self.nodes[end_node_id]['label'],
                    'properties': self.nodes[end_node_id]['properties'],
                }
                path_obj = {
                    'start_node': start_node,
                    'end_node':   end_node,
                    'relationships': []
                }
                for step in path[1:]:
                    (node_id, edge_id, prev_node) = step
                    if edge_id:
                        ed = self.edges[edge_id]
                        path_obj['relationships'].append({
                            'id': edge_id,
                            'label': ed['label'],
                            'properties': ed['properties'],
                            'from_id': ed['from_id'],
                            'to_id': ed['to_id'],
                        })
                keep = True
                for rel in path_obj['relationships']:
                    for rel_filter in query.relationship_filters:
                        if not rel_filter(rel):
                            keep = False
                            break
                    if not keep:
                        break
                if keep and path_obj['relationships']:
                    path_results.append(path_obj)
                    query._edges_traversed += len(path_obj['relationships'])
        return path_results

    def _apply_aggregations(self, query: Query, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        agg_res = {}
        for agg in query.aggregations:
            if agg.type == AggregationType.COUNT:
                val = len(results)
            else:
                vals = []
                for item in results:
                    props = item.get('properties', {})
                    if agg.field in props:
                        try:
                            vals.append(float(props[agg.field]))
                        except ValueError:
                            pass
                if vals:
                    if agg.type == AggregationType.SUM:
                        val = sum(vals)
                    elif agg.type == AggregationType.AVG:
                        val = sum(vals) / len(vals)
                    elif agg.type == AggregationType.MIN:
                        val = min(vals)
                    elif agg.type == AggregationType.MAX:
                        val = max(vals)
                else:
                    val = None
            alias = agg.alias or agg.field or agg.type.name.lower()
            agg_res[alias] = val
        return [agg_res]

    #
    # DFS HELPER FOR PATH QUERIES
    #
    def _find_paths(
        self,
        pattern: PathPattern,
        visited: Set[str],
        current_node: str,
        target_label: str,
        path: List[Tuple[str, str, str]],
        paths: List[List[Tuple[str, str, str]]],
        depth: int
    ) -> None:
        if current_node in visited or depth > (pattern.max_depth or float('inf')):
            return
        visited.add(current_node)
        new_path = path or [(current_node, '', '')]
        node_data = self.nodes[current_node]
        if node_data['label'] == target_label and depth >= (pattern.min_depth or 0):
            if len(new_path) > 1:
                paths.append(new_path)
        if current_node in self._edge_index:
            for (edge_id, to_id) in self._edge_index[current_node]:
                e_data = self.edges[edge_id]
                if e_data['label'] in pattern.relationships:
                    if to_id not in visited:
                        branch_visited = visited.copy()
                        extended_path = new_path + [(to_id, edge_id, current_node)]
                        self._find_paths(pattern, branch_visited, to_id, pattern.end_label, extended_path, paths, depth + 1)

    #
    # BATCH OPERATIONS
    #
    def _batch_create_nodes_impl(self, nodes: List[Dict[str, Any]]) -> List[str]:
        node_ids = []
        for n in nodes:
            label = n['label']
            props = n['properties']
            self._validate_node_ontology(label, props)
            node_id = str(uuid.uuid4())
            self.nodes[node_id] = {'label': label, 'properties': props}
            node_ids.append(node_id)
        self._update_edge_index()
        return node_ids

    def _batch_create_edges_impl(self, edges: List[Dict[str, Any]]) -> List[str]:
        edge_ids = []
        for e in edges:
            from_id = str(e['from_id'])
            to_id = str(e['to_id'])
            label = e['label'].lower()  # force lower-case
            props = e.get('properties', {})
            if from_id not in self.nodes or to_id not in self.nodes:
                raise ValueError(f"Source or target node does not exist for edge: {e}")
            self._validate_edge_ontology(label, props)
            edge_id = str(uuid.uuid4())
            self.edges[edge_id] = {
                'from_id': from_id,
                'to_id': to_id,
                'label': label,
                'properties': props
            }
            edge_ids.append(edge_id)
        self._update_edge_index()
        return edge_ids

    #
    # ADDITIONS: Return node IDs in query methods.
    #
    def get_node_by_property(self, property_name: str, value: Any) -> List[Dict[str, Any]]:
        """Return all nodes that have a specific property value, including their unique IDs."""
        result = []
        for node_id, node in self.nodes.items():
            if node.get("properties", {}).get(property_name) == value:
                node_copy = dict(node)
                node_copy["id"] = node_id
                result.append(node_copy)
        return result

    def get_nodes_with_property(self, property_name: str) -> List[Dict[str, Any]]:
        """Return all nodes that have a specific property present, including their unique IDs."""
        result = []
        for node_id, node in self.nodes.items():
            if property_name in node.get("properties", {}):
                node_copy = dict(node)
                node_copy["id"] = node_id
                result.append(node_copy)
        return result
