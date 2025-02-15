import pytest
from graphrouter.query_builder import QueryBuilder

def test_query_builder_filter():
    qb = QueryBuilder()
    result = qb.filter("name", "eq", "John").build()
    assert result["filters"][0] == {
        "field": "name",
        "operator": "eq",
        "value": "John"
    }

def test_query_builder_sort():
    qb = QueryBuilder()
    result = qb.sort("age", ascending=False).build()
    assert result["sort"] == {
        "field": "age",
        "direction": "DESC"
    }

def test_query_builder_limit_skip():
    qb = QueryBuilder()
    result = qb.limit(10).skip(5).build()
    assert result["limit"] == 10
    assert result["skip"] == 5

def test_query_builder_chaining():
    qb = QueryBuilder()
    result = (qb
        .filter("age", "gt", 18)
        .sort("name")
        .limit(10)
        .build())
    
    assert len(result["filters"]) == 1
    assert result["sort"]["direction"] == "ASC"
    assert result["limit"] == 10

import pytest
from graphrouter.query_builder import QueryBuilder

def test_query_builder_init():
    builder = QueryBuilder()
    assert builder.filters == []
    assert builder.sort_field is None
    assert builder.sort_direction == "ASC"
    assert builder.limit_value is None
    assert builder.skip_value is None

def test_filter():
    builder = QueryBuilder()
    result = builder.filter("name", "equals", "Alice")
    assert len(builder.filters) == 1
    assert builder.filters[0] == {
        "field": "name",
        "operator": "equals",
        "value": "Alice"
    }
    assert result == builder  # Test chaining

def test_sort():
    builder = QueryBuilder()
    result = builder.sort("age", ascending=False)
    assert builder.sort_field == "age"
    assert builder.sort_direction == "DESC"
    assert result == builder

def test_limit():
    builder = QueryBuilder()
    result = builder.limit(10)
    assert builder.limit_value == 10
    assert result == builder

def test_skip():
    builder = QueryBuilder()
    result = builder.skip(5)
    assert builder.skip_value == 5
    assert result == builder

def test_build():
    builder = QueryBuilder()
    builder.filter("name", "equals", "Alice")
    builder.sort("age", ascending=False)
    builder.limit(10)
    builder.skip(5)
    
    query = builder.build()
    assert query == {
        "filters": [{
            "field": "name",
            "operator": "equals",
            "value": "Alice"
        }],
        "sort": {
            "field": "age",
            "direction": "DESC"
        },
        "limit": 10,
        "skip": 5
    }

def test_build_empty():
    builder = QueryBuilder()
    query = builder.build()
    assert query == {}

def test_multiple_filters():
    builder = QueryBuilder()
    builder.filter("name", "equals", "Alice")
    builder.filter("age", "gt", 25)
    query = builder.build()
    assert len(query["filters"]) == 2

def test_exists_filter():
    builder = QueryBuilder()
    result = builder.exists("email").build()
    assert result["filters"][0] == {
        "field": "email",
        "operator": "exists"
    }

def test_in_list_filter():
    builder = QueryBuilder()
    result = builder.in_list("status", ["active", "pending"]).build()
    assert result["filters"][0] == {
        "field": "status",
        "operator": "in",
        "value": ["active", "pending"]
    }

def test_vector_search():
    builder = QueryBuilder()
    query_vector = [0.1, 0.2, 0.3]
    result = builder.vector_nearest("embedding", query_vector, k=5, min_score=0.8).build()
    assert result["vector_search"] == {
        "field": "embedding",
        "vector": query_vector,
        "k": 5,
        "min_score": 0.8
    }

def test_vector_search_validation():
    builder = QueryBuilder()
    # Test invalid vector type
    with pytest.raises(ValueError, match="Query vector must be a list"):
        builder.vector_nearest("embedding", "not a vector")
    
    # Test invalid vector contents
    with pytest.raises(ValueError, match="must contain only numbers"):
        builder.vector_nearest("embedding", [1, "two", 3])
        
    # Test invalid k
    with pytest.raises(ValueError, match="k must be positive"):
        builder.vector_nearest("embedding", [1,2,3], k=0)
        
    # Test invalid min_score
    with pytest.raises(ValueError, match="min_score must be between 0 and 1"):
        builder.vector_nearest("embedding", [1,2,3], min_score=1.5)

def test_hybrid_search():
    builder = QueryBuilder()
    query_vector = [0.1, 0.2, 0.3]
    result = (builder
        .filter("category", "eq", "article")
        .hybrid_search("embedding", query_vector, k=5, min_score=0.7)
        .build())
    
    assert result["filters"][0] == {
        "field": "category",
        "operator": "eq",
        "value": "article"
    }
    assert result["vector_search"] == {
        "field": "embedding",
        "vector": query_vector,
        "k": 5,
        "min_score": 0.7
    }

def test_group_by_having():
    builder = QueryBuilder()
    result = (builder
        .group_by_fields(["department"])
        .having_count(5)
        .build())
    assert result["group_by"] == ["department"]
    assert result["having"][0]["value"] == 5

def test_vector_search_with_filters():
    # Test combined filters and vector search
    builder = QueryBuilder()
    query_vector = [0.1, 0.2, 0.3]
    result = (builder
        .filter("category", "eq", "article")
        .vector_nearest("embedding", query_vector, k=5, min_score=0.7)
        .build())

    assert result["vector_search"] == {
        "field": "embedding",
        "vector": query_vector,
        "k": 5,
        "min_score": 0.7
    }
    assert result["filters"][0] == {
        "field": "category",
        "operator": "eq",
        "value": "article"
    }

    # Test multiple filters with vector search (using new builder instance)
    builder = QueryBuilder()
    result = (builder
        .filter("category", "eq", "article")
        .filter("status", "eq", "published")
        .vector_nearest("embedding", query_vector, k=5, min_score=0.7)
        .build())

    assert len(result["filters"]) == 2
    assert result["vector_search"] == {
        "field": "embedding",
        "vector": query_vector,
        "k": 5,
        "min_score": 0.7
    }
    assert result["filters"][0] == {
        "field": "category",
        "operator": "eq",
        "value": "article"
    }
    assert result["filters"][1] == {
        "field": "status",
        "operator": "eq",
        "value": "published"
    }

def test_vector_search_without_min_score():
    builder = QueryBuilder()
    query_vector = [0.1, 0.2, 0.3]
    result = builder.vector_nearest("embedding", query_vector, k=5).build()
    
    assert result["vector_search"] == {
        "field": "embedding",
        "vector": query_vector,
        "k": 5,
        "min_score": None
    }