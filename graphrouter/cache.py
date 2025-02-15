"""Cache management for GraphRouter."""
from typing import Any, Dict, Optional, Set
from datetime import datetime, timedelta
import time

class QueryCache:
    def __init__(self, ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
        self.invalidation_patterns: Dict[str, Set[str]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache if it exists and hasn't expired."""
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() - entry['timestamp'] < timedelta(seconds=self.ttl):
                return entry['data']
            else:
                # Remove expired entry
                del self.cache[key]
        return None

    def set(self, key: str, value: Any):
        """Store a value in cache with current timestamp."""
        self.cache[key] = {
            'data': value,
            'timestamp': datetime.now()
        }

        # Register for pattern-based invalidation
        parts = key.split(':')
        if len(parts) > 1:
            pattern = f"{parts[0]}:*"
            if pattern not in self.invalidation_patterns:
                self.invalidation_patterns[pattern] = set()
            self.invalidation_patterns[pattern].add(key)

    def invalidate(self, key_or_pattern: str):
        """Invalidate cache entries matching the given key or pattern.

        If an exact key exists in the cache, it is removed.
        Also, if the key_or_pattern is found as a pattern, all associated keys are removed.
        """
        # Invalidate the exact key if present.
        if key_or_pattern in self.cache:
            del self.cache[key_or_pattern]
        # Also, if key_or_pattern is registered as a pattern, invalidate all its keys.
        if key_or_pattern in self.invalidation_patterns:
            for key in self.invalidation_patterns[key_or_pattern]:
                if key in self.cache:
                    del self.cache[key]
            del self.invalidation_patterns[key_or_pattern]

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.invalidation_patterns.clear()

    def cleanup(self):
        """Remove expired entries from cache."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now - entry['timestamp'] >= timedelta(seconds=self.ttl)
        ]
        for key in expired_keys:
            del self.cache[key]
            # Clean up invalidation patterns
            for pattern, keys in list(self.invalidation_patterns.items()):
                keys.discard(key)
                if not keys:
                    del self.invalidation_patterns[pattern]
