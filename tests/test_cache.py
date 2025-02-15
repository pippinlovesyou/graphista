"""
Tests for the query cache implementation.
"""
import pytest
from datetime import datetime, timedelta
from graphrouter.cache import QueryCache

def test_cache_initialization():
    """Test cache initialization with default TTL."""
    cache = QueryCache()
    assert cache.ttl == 300  # Default TTL
    assert len(cache.cache) == 0

def test_cache_initialization_custom_ttl():
    """Test cache initialization with custom TTL."""
    cache = QueryCache(ttl=60)
    assert cache.ttl == 60

def test_cache_set_and_get():
    """Test basic cache set and get operations."""
    cache = QueryCache()
    
    # Test with different data types
    test_data = {
        'string_key': 'test_value',
        'int_key': 42,
        'dict_key': {'nested': 'data'},
        'list_key': [1, 2, 3]
    }
    
    # Set values
    for key, value in test_data.items():
        cache.set(key, value)
    
    # Get values
    for key, expected in test_data.items():
        assert cache.get(key) == expected

def test_cache_ttl():
    """Test cache TTL functionality."""
    cache = QueryCache(ttl=1)  # 1 second TTL
    
    # Set a value
    cache.set('test_key', 'test_value')
    assert cache.get('test_key') == 'test_value'
    
    # Wait for TTL to expire
    import time
    time.sleep(2)
    
    # Value should be None after TTL expiration
    assert cache.get('test_key') is None

def test_cache_overwrite():
    """Test overwriting existing cache entries."""
    cache = QueryCache()
    
    # Set initial value
    cache.set('test_key', 'initial_value')
    assert cache.get('test_key') == 'initial_value'
    
    # Overwrite value
    cache.set('test_key', 'updated_value')
    assert cache.get('test_key') == 'updated_value'

def test_cache_nonexistent_key():
    """Test getting a nonexistent key."""
    cache = QueryCache()
    assert cache.get('nonexistent_key') is None
