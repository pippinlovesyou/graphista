# Installation Guide - Graphista

This guide provides step-by-step instructions for installing Graphista, our dynamic graph‑based memory system, along with all necessary dependencies and backend support.

## Requirements

- Python 3.8 or higher
- git package manager

## Installation from GitHub

Clone the repository and install the dependencies locally:

~~~bash
git clone https://github.com/pippinlovesyou/graphista.git
cd graphista
~~~

## Optional Backend Support

### Neo4j
For Neo4j support, install the optional dependencies:
~~~bash
pip install -e ".[neo4j]"
~~~

### FalkorDB
For FalkorDB support, install the optional dependencies:
~~~bash
pip install -e ".[falkordb]"
~~~

### All Dependencies
For full functionality, install all optional dependencies:
~~~bash
pip install -e ".[all]"
~~~

## Development Installation

To contribute to Graphista:

1. Clone the repository:
~~~bash
git clone https://github.com/pippinlovesyou/graphista.git
cd graphista
~~~
2. Install development dependencies:
~~~bash
pip install -e ".[dev]"
~~~
3. Install test dependencies:
~~~bash
pip install -e ".[test]"
~~~

## Backend Setup

### Neo4j Setup
1. [Install Neo4j](https://neo4j.com/docs/operations-manual/current/installation/).
2. Start the Neo4j server:
~~~bash
neo4j start
~~~
3. Configure your connection:
~~~python
from graphista import Neo4jGraphDatabase

db = Neo4jGraphDatabase()
db.connect(uri="bolt://localhost:7687", username="neo4j", password="your_password")
~~~

> **Note:** Async support for Neo4j is not yet fully tested.

### FalkorDB Setup
1. [Install Redis](https://redis.io/docs/getting-started/).
2. Load the FalkorDB module (if applicable):
~~~bash
redis-cli module load falkordb.so
~~~
3. Connect using:
~~~python
from graphista import FalkorDBGraphDatabase

db = FalkorDBGraphDatabase()
db.connect(host="localhost", port=6379, password="your_password")
~~~

> **Note:** FalkorDB integration is still under development and may not be fully tested.

## Troubleshooting

### Common Issues
- **Connection Errors:** Ensure your database server is running and credentials are correct.
- **Import Errors:** Verify your Python version and that all dependencies are installed (`pip list`).

## Discord Support

Join our Discord community for support and discussion:
[https://discord.gg/xNXnJ5JFsA](https://discord.gg/xNXnJ5JFsA)

## Next Steps

- Read the [Quick Start Guide](quickstart.md) for basic usage.
- Explore the [Advanced Usage Guide](advanced_usage.md) for optimization tips.
- Check the [API Reference](api_reference.md) for detailed documentation.

---

Happy graphing and knowledge discovery with **Graphista**!
