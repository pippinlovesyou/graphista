# API Reference - Graphista

This document provides a complete reference for Graphista’s core API. Graphista is built atop the GraphRouter library and offers a unified interface for managing graph databases with LLM-powered extraction and querying.

## Core Classes

### GraphDatabase

The abstract base class for all supported graph database backends.

#### Initialization
~~~python
class GraphDatabase(ABC):
    def __init__(self, pool_size: int = 5):
        """Initialize the database connection with a configurable pool size."""
~~~

#### Connection Methods
~~~python
def connect(self, **kwargs) -> bool:
    """Connect to the database. Raises a ConnectionError if the connection fails."""

def disconnect(self) -> bool:
    """Disconnect from the database."""
~~~

#### Node Operations
~~~python
def create_node(self, label: str, properties: Dict[str, Any] = None) -> str:
    """Create a new node with the specified label and properties."""

def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a node by its unique ID."""

def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
    """Update an existing node with new properties."""

def delete_node(self, node_id: str) -> bool:
    """Delete a node by its ID."""
~~~

#### Edge Operations
~~~python
def create_edge(self, from_id: str, to_id: str, label: str, properties: Optional[Dict[str, Any]] = None) -> str:
    """Create an edge between two nodes."""

def get_edge(self, edge_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an edge by its ID."""

def update_edge(self, edge_id: str, properties: Dict[str, Any]) -> bool:
    """Update an edge with new properties."""

def delete_edge(self, edge_id: str) -> bool:
    """Delete an edge by its ID."""
~~~

#### Query Execution
~~~python
def query(self, query: Query) -> List[Dict[str, Any]]:
    """Execute a Query object and return matching nodes."""
~~~

### Query Builder

The `Query` class provides a fluent interface for building and executing graph queries.

#### Example Usage
~~~python
from graphrouter import Query

query = Query()
query.filter(Query.label_equals('Person'))
query.filter(Query.property_equals('age', 30))
results = db.query(query)
~~~

#### Advanced Filtering
~~~python
# Using custom lambda filters
query.filter(lambda node: node['properties'].get('age', 0) > 25)
~~~

### Cache Management

The `QueryCache` class handles caching of query results.
~~~python
cache = QueryCache(ttl=300)  # Cache TTL set to 300 seconds
cache.invalidate("node:*")   # Invalidate node caches
~~~

### Performance Monitoring

The `PerformanceMonitor` class tracks performance metrics for all operations.
~~~python
metrics = db._monitor.get_average_times()
print(f"Average query time: {metrics['query']:.3f}s")
~~~

## Database Implementations

### Local JSON Backend
~~~python
from graphrouter import LocalGraphDatabase

db = LocalGraphDatabase()
db.connect(db_path="graph.json")
~~~

### Neo4j Backend
~~~python
from graphrouter import Neo4jGraphDatabase

db = Neo4jGraphDatabase()
db.connect(uri="bolt://localhost:7687", username="neo4j", password="your_password")
~~~

### FalkorDB Backend
~~~python
from graphrouter import FalkorDBGraphDatabase

db = FalkorDBGraphDatabase()
db.connect(host="localhost", port=6379, password="your_password")
~~~

## Error Handling

Graphista defines custom exceptions to capture common error scenarios:
- `ConnectionError`: Issues with database connectivity.
- `QueryError`: Errors during query execution.
- `ValidationError`: Schema or data validation errors.

For more examples, see the [Quick Start Guide](quickstart.md) and [Advanced Usage Guide](advanced_usage.md).
