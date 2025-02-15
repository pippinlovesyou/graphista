# Advanced Usage Guide - Graphista

Graphista leverages LLM‑powered tools for efficient graph-based memory management. This guide covers advanced topics—including performance tuning, complex querying, schema management, monitoring, and error handling—to help you get the most out of your dynamic memory system.

## Performance Optimization

### Connection Pooling
Customize your database pool size and caching:
~~~python
from graphrouter import Neo4jGraphDatabase

db = Neo4jGraphDatabase(pool_size=10)
db.connect(uri="bolt://localhost:7687", username="neo4j", password="your_password")
~~~

### Query Caching
Set custom cache TTL and invalidate caches when necessary:
~~~python
# Set cache TTL to 10 minutes
db._cache = QueryCache(ttl=600)

# Invalidate caches by pattern
db._cache.invalidate("node:*")
db._cache.invalidate("query:*")
~~~

### Batch Operations
Perform bulk node and edge creation efficiently:
~~~python
# Bulk create nodes
nodes = [
    {'label': 'Person', 'properties': {'name': f'User{i}', 'age': 20 + i}}
    for i in range(1000)
]
node_ids = db.batch_create_nodes(nodes)

# Bulk create edges
edges = [
    {'from_id': node_ids[i], 'to_id': node_ids[i+1], 'label': 'KNOWS'}
    for i in range(len(node_ids)-1)
]
edge_ids = db.batch_create_edges(edges)
~~~

## Advanced Querying

### Complex Filters
Combine multiple filters to narrow down your results:
~~~python
from graphrouter import Query

query = Query()
query.filter(Query.label_equals('Person'))
query.filter(Query.property_greater_than('age', 25))
query.filter(Query.property_contains('interests', 'coding'))
query.filter(
    lambda node: any(city in node['properties'].get('location', '')
                     for city in ['New York', 'London', 'Tokyo'])
)
~~~

### Custom Query Builders
Extend the query class for reusable filters:
~~~python
class AdvancedQuery(Query):
    @staticmethod
    def age_range(min_age: int, max_age: int) -> Callable:
        def filter_func(node: Dict[str, Any]) -> bool:
            age = node['properties'].get('age', 0)
            return min_age <= age <= max_age
        return filter_func

    @staticmethod
    def has_complete_profile() -> Callable:
        required_fields = {'name', 'email', 'phone'}
        def filter_func(node: Dict[str, Any]) -> bool:
            return all(field in node['properties'] for field in required_fields)
        return filter_func
~~~

## Schema Management

### Advanced Ontology
Define complex schemas with nested structures:
~~~python
from graphrouter import Ontology

ontology = Ontology()
ontology.add_node_type('Person', {
    'name': str,
    'age': int,
    'contacts': list,
    'address': {
        'street': str,
        'city': str,
        'country': str
    }
})
ontology.add_edge_type('KNOWS', {
    'since': str,
    'strength': float,
    'tags': list
})
db.set_ontology(ontology)
~~~

## Monitoring and Metrics

### Custom Metrics Collection
Retrieve detailed performance metrics:
~~~python
detailed_metrics = db._monitor.get_detailed_metrics()
query_stats = db._monitor.get_operation_stats('query')
print(f"Average query duration: {query_stats['avg_duration']:.3f}s")
print(f"Median duration: {query_stats['median_duration']:.3f}s")
print(f"Standard deviation: {query_stats['std_dev']:.3f}s")
print(f"Error rate: {query_stats['error_rate']*100:.1f}%")
db._monitor.reset()
~~~

### Performance Profiling
Profile specific operations using a context manager:
~~~python
import time
from contextlib import contextmanager

@contextmanager
def profile_operation(db, operation_name: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        db._monitor.record_operation(operation_name, duration)

with profile_operation(db, 'complex_query'):
    results = db.query(complex_query)
~~~

## Error Handling and Recovery

### Retry Logic
Use retry strategies for transient errors (e.g., with Tenacity):
~~~python
from tenacity import retry, stop_after_attempt, wait_exponential

class RetryingDatabase(Neo4jGraphDatabase):
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def query(self, query: Query) -> List[Dict[str, Any]]:
        return super().query(query)
~~~

### Transaction Management
Execute multiple operations atomically:
~~~python
class TransactionManager:
    def __init__(self, db):
        self.db = db
        self.operations = []

    def add_operation(self, op_type: str, *args, **kwargs):
        self.operations.append((op_type, args, kwargs))

    def execute(self):
        results = []
        try:
            for op_type, args, kwargs in self.operations:
                if op_type == 'create_node':
                    results.append(self.db.create_node(*args, **kwargs))
                elif op_type == 'create_edge':
                    results.append(self.db.create_edge(*args, **kwargs))
            return results
        except Exception as e:
            # Implement rollback logic if needed
            raise
~~~

## Best Practices

1. **Connection Management:** Use appropriate pool sizes and implement health checks.
2. **Query Optimization:** Use batch operations and caching for efficiency.
3. **Error Handling:** Leverage retry mechanisms and detailed logging.
4. **Performance Monitoring:** Regularly collect and analyze metrics.
5. **Data Validation:** Use comprehensive ontology schemas for consistent data quality.

For additional details, refer to the [API Reference](api_reference.md) and [Quick Start Guide](quickstart.md).
