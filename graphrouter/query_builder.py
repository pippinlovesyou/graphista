from typing import Any, Dict, List, Optional, Callable

class QueryBuilder:
    def __init__(self):
        self.filters: List[Dict[str, Any]] = []
        self.sort_field: Optional[str] = None
        self.sort_direction: str = "ASC"
        self.limit_value: Optional[int] = None
        self.skip_value: Optional[int] = None
        self.vector_search: Optional[Dict[str, Any]] = None
        self.group_by: Optional[List[str]] = None
        self.having: List[Dict[str, Any]] = []

    def vector_nearest(self, embedding_field: str, query_vector: List[float], k: int = 10, min_score: float = None) -> 'QueryBuilder':
        """
        Find k-nearest neighbors by vector similarity with optional minimum score threshold

        Args:
            embedding_field: Field containing the vector embeddings
            query_vector: Query vector to compare against
            k: Number of nearest neighbors to return
            min_score: Minimum similarity score (0-1), optional
        """
        if not isinstance(query_vector, list):
            raise ValueError("Query vector must be a list of floats")

        if not all(isinstance(x, (int, float)) for x in query_vector):
            raise ValueError("Query vector must contain only numbers")

        if k < 1:
            raise ValueError("k must be positive")

        if min_score is not None and not (0 <= min_score <= 1):
            raise ValueError("min_score must be between 0 and 1")

        self.vector_search = {
            "field": embedding_field,
            "vector": query_vector,
            "k": k,
            "min_score": min_score
        }
        return self

    def hybrid_search(self, embedding_field: str, query_vector: List[float], k: int = 10, min_score: float = None) -> 'QueryBuilder':
        """
        Combines vector similarity search with property filters

        This method allows combining vector search with any other filters added to the query
        """
        return self.vector_nearest(embedding_field, query_vector, k, min_score)

    def group_by_fields(self, fields: List[str]) -> 'QueryBuilder':
        """Group results by specified fields"""
        self.group_by = fields
        return self

    def having_count(self, min_count: int) -> 'QueryBuilder':
        """Filter groups by minimum count"""
        self.having.append({
            "type": "count",
            "operator": "gte",
            "value": min_count
        })
        return self

    def filter(self, field: str, operator: str, value: Any) -> 'QueryBuilder':
        self.filters.append({
            "field": field,
            "operator": operator,
            "value": value
        })
        return self

    def sort(self, field: str, ascending: bool = True) -> 'QueryBuilder':
        self.sort_field = field
        self.sort_direction = "ASC" if ascending else "DESC"
        return self

    def limit(self, value: int) -> 'QueryBuilder':
        self.limit_value = value
        return self

    def skip(self, value: int) -> 'QueryBuilder':
        self.skip_value = value
        return self

    def exists(self, field: str) -> 'QueryBuilder':
        """Filter for nodes where a property exists"""
        self.filters.append({
            "field": field,
            "operator": "exists"
        })
        return self

    def in_list(self, field: str, values: List[Any]) -> 'QueryBuilder':
        """Filter for nodes where property is in a list of values"""
        self.filters.append({
            "field": field,
            "operator": "in",
            "value": values
        })
        return self

    def starts_with(self, field: str, prefix: str) -> 'QueryBuilder':
        """Filter for string properties starting with prefix"""
        self.filters.append({
            "field": field,
            "operator": "starts_with",
            "value": prefix
        })
        return self

    def build(self) -> Dict[str, Any]:
        query = {}
        if self.filters:
            query["filters"] = self.filters
        if self.sort_field:
            query["sort"] = {
                "field": self.sort_field,
                "direction": self.sort_direction
            }
        if self.limit_value is not None:
            query["limit"] = self.limit_value
        if self.skip_value is not None:
            query["skip"] = self.skip_value
        if self.vector_search is not None:
            query["vector_search"] = self.vector_search
        if self.group_by is not None:
            query["group_by"] = self.group_by
        if self.having:
            query["having"] = self.having
        return query