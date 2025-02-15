# GraphRouter

GraphRouter is a flexible Python graph database router library that provides a unified interface for working with multiple graph database backends. It lets you write queries once and run them on different databases (e.g. Local JSON, Neo4j, FalkorDB) with built‑in support for schema validation, connection pooling, performance monitoring, and more.

**Note:** While GraphRouter supports multiple backends and asynchronous operations, full async support and advanced features for Neo4j and FalkorDB are experimental and not fully tested.

## Features

- **Multiple Backend Support:**  
  Seamlessly work with different graph databases (Local JSON, Neo4j, FalkorDB).

- **Unified Query Interface:**  
  Write queries once and run them on any supported backend with features such as:
  - Advanced filtering, sorting, and pagination  
  - Hybrid searches combining vector similarity and property filters  
  - Group-by and aggregation functions

- **Schema & Ontology Validation:**  
  Define custom node and edge types using ontologies; validate property types and enforce required fields.

- **Transaction Management & Connection Pooling:**  
  Support for ACID-compliant transactions and efficient resource usage.

- **Performance Monitoring:**  
  Built-in metrics and advanced caching options.

- **Async Operations:**  
  Full asynchronous support for database operations. *(Note: Async methods are currently minimal for some backends.)*

- **Security Features:**  
  Input validation, parameterized queries, connection timeouts, and ontology-based sanitization.

## Installation

To install GraphRouter (as part of Graphista), run:

~~~bash
pip install graphista
~~~

## Quick Start

### 1. Initialize the Graph Database

For local testing, start with a JSON-based database:

~~~python
from graphista import LocalGraphDatabase

# Initialize and connect to a local JSON database.
db = LocalGraphDatabase()
db.connect(db_path="graph.json")
~~~

For production, you can switch to Neo4j or FalkorDB:

~~~python
# For Neo4j:
# from graphista import Neo4jGraphDatabase
# db = Neo4jGraphDatabase()
# db.connect(uri="bolt://0.0.0.0:7687", username="neo4j", password="password")

# For FalkorDB:
# from graphista import FalkorDBGraphDatabase
# db = FalkorDBGraphDatabase()
# db.connect(host="0.0.0.0", port=6379)
~~~

### 2. Define Your Knowledge Structure

Set up an ontology to define the data types and relationships:

~~~python
from graphista import Ontology

ontology = Ontology()
ontology.add_node_type("Person", {
    "name": str,
    "role": str,
    "age": int
}, required=["name"])

ontology.add_node_type("Company", {
    "name": str,
    "industry": str
}, required=["name"])

ontology.add_relationship_type("WORKS_AT", 
    source_types=["Person"],
    target_types=["Company"]
)

db.set_ontology(ontology)
~~~

### 3. Querying and Advanced Operations

Use GraphRouter’s unified query interface:

~~~python
from graphista import Query

query = Query()
query.filter(Query.label_equals("Person"))
query.filter(Query.property_equals("age", 30))
results = db.query(query)

# Check performance metrics
metrics = db.get_performance_metrics()
print(f"Average query time: {metrics['query']:.3f}s")
~~~

For more detailed usage, see the [GraphRouter Documentation](../docs/README.md).

## Security

GraphRouter implements:
- Input validation and sanitization  
- Parameterized queries  
- Connection pooling with timeouts  
- Ontology-based schema validation  

## Additional Information

GraphRouter provides a solid foundation for building complex, dynamic graph‑based systems. For details on advanced features (such as caching, async operations, and performance monitoring), please refer to our API reference and additional documentation.

---
**Note:** Advanced features like async operations and full support for Neo4j/FalkorDB are still under development.

