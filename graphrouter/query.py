"""
Query builder for advanced queries.
"""
from typing import Dict, Any, List, Optional, Callable, TypeVar
from enum import Enum
from graphrouter.errors import QueryValidationError

T = TypeVar('T')

class AggregationType(Enum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"

class PathPattern:
    def __init__(self, start_label: str, end_label: str,
                 relationships: List[str],
                 min_depth: Optional[int] = None,
                 max_depth: Optional[int] = None):
        self.start_label = start_label
        self.end_label = end_label
        self.relationships = relationships
        self.min_depth = min_depth
        self.max_depth = max_depth

class Aggregation:
    def __init__(self, type: AggregationType, field: Optional[str] = None, alias: Optional[str] = None):
        self.type = type
        self.field = field
        self.alias = alias or f"{type.value}_{field if field else 'result'}"

class Query:
    def __init__(self):
        self.filters: List[Callable[[Dict[str, Any]], bool]] = []
        self.relationship_filters: List[Callable[[Dict[str, Any]], bool]] = []
        self.aggregations: List[Aggregation] = []
        self.path_patterns: List[PathPattern] = []
        self.vector_search: Optional[Dict[str, Any]] = None

        self._nodes_scanned = 0
        self._edges_traversed = 0
        self._execution_time= 0.0
        self._memory_used= 0.0

        self.sort_key: Optional[str] = None
        self.sort_reverse: bool = False
        self.skip: Optional[int] = None
        self.limit: Optional[int] = None

    def filter(self, fn: Callable[[Dict[str, Any]], bool]) -> 'Query':
        self.filters.append(fn)
        return self

    def filter_relationship(self, fn: Callable[[Dict[str, Any]], bool]) -> 'Query':
        self.relationship_filters.append(fn)
        return self

    def find_path(self, start_label: str, end_label: str, relationships: List[str],
                  min_depth: int=1, max_depth: int=2) -> 'Query':
        self.path_patterns.append(PathPattern(start_label, end_label, relationships,
                                              min_depth, max_depth))
        return self

    def aggregate(self, agg_type: AggregationType, field: Optional[str]=None,
                  alias: Optional[str]=None) -> 'Query':
        self.aggregations.append(Aggregation(agg_type, field, alias))
        return self

    def vector_nearest(self, embedding_field: str, query_vector: List[float],
                       k:int=10, min_score:Optional[float]=None) -> 'Query':
        self.vector_search= {
            "field": embedding_field,
            "vector": query_vector,
            "k": k,
            "min_score": min_score
        }
        return self

    def sort(self, key:str, reverse:bool=False) -> 'Query':
        self.sort_key = key
        self.sort_reverse = reverse
        return self

    def paginate(self, page:int, page_size:int) -> 'Query':
        self.skip = (page-1)*page_size
        self.limit= page_size
        return self

    def limit_results(self, limit:int) -> 'Query':
        self.limit= limit
        return self

    def collect_stats(self) -> Dict[str,float]:
        return {
            'nodes_scanned': self._nodes_scanned,
            'edges_traversed': self._edges_traversed,
            'execution_time': self._execution_time,
            'memory_used': self._memory_used
        }

    def _set_execution_time(self, sec: float):
        self._execution_time= sec

    def _set_memory_used(self, mem: float):
        self._memory_used= mem

    def matches_node(self, node_data: Dict[str, Any]) -> bool:
        return all(f(node_data) for f in self.filters)

    @staticmethod
    def label_equals(lbl:str) -> Callable[[Dict[str,Any]], bool]:
        def fn(node):
            return node.get('label')==lbl
        return fn

    @staticmethod
    def property_equals(prop:str, val:Any) -> Callable[[Dict[str,Any]], bool]:
        def fn(node):
            return node.get('properties',{}).get(prop)==val
        return fn

    @staticmethod
    def property_contains(prop:str, substring:str) -> Callable[[Dict[str,Any]], bool]:
        def fn(node):
            v= node.get('properties',{}).get(prop)
            return isinstance(v,str) and substring in v
        return fn

    @staticmethod
    def relationship_exists(other_id:str, rel_label:str) -> Callable[[Dict[str,Any]], bool]:
        def fn(node):
            edges = node.get('edges',[])
            for e in edges:
                if e.get('label')==rel_label:
                    if (e.get('from_id')==node['id'] and e.get('to_id')==other_id) \
                       or (e.get('to_id')==node['id'] and e.get('from_id')==other_id):
                        return True
            return False
        return fn
