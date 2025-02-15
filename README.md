# Graphista: Dynamic Graph-Based LLM-Powered Memory System

Welcome to **Graphista** – a proof-of-concept prototype that leverages a large language model (LLM) loop for graph‑based memory management. Graphista integrates LLM-powered ingestion and querying tools to enable dynamic knowledge management. It uses two specialized LLM‑driven loops: one (via the `ingest()` function and the **SmartNodeProcessor** tool) automatically processes incoming text to deduplicate, extract, and update nodes; the other (via the `ask()` function and the **SmartRetrievalTool** tool) allows you to ask natural language questions that are answered using a detailed chain‑of‑thought reasoning process. **Note:** Async operations and advanced backend integrations (Neo4j, FalkorDB) are experimental and not yet fully tested.

## Quickstart

Follow these simple steps to get started quickly with Graphista.

### Step 1: Installation

Clone the repository from GitHub:

~~~bash
git clone https://github.com/pippinlovesyou/graphista.git
cd graphista
~~~

Then install the development dependencies:

~~~bash
pip install -e .
~~~

### Step 2: Initialize Memory with LLM Integration

Graphista’s unified `Memory` class brings together your graph database, ontology, LLM integration, and data ingestion. In your application, you can simply import `Memory` from the `memory` module and specify the backend in the instance setup. For example, using the default local JSON backend:

~~~python
from memory import Memory

# Define your ontology (using JSON Schema style)
ontology_config = {
    "node_types": {
        "Person": {
            "properties": {"name": "str", "role": "str", "age": "int", "embedding": "list"},
            "required": ["name"]
        },
        "Company": {
            "properties": {"name": "str", "industry": "str", "embedding": "list"},
            "required": ["name"]
        },
        "Document": {
            "properties": {"content": "str"},
            "required": ["content"]
        }
    },
    "edge_types": {
        "WORKS_AT": {
            "properties": {"since": "str", "role": "str", "known_for": "str"},
            "required": []
        }
    }
}

# Define extraction rules for LLM-powered auto‑extraction and deduplication
extraction_rules = {
    "extractable_types": {
        "Person": {"target_schema": {"name": "str", "role": "str", "embedding": "list"}},
        "Company": {"target_schema": {"name": "str", "industry": "str", "embedding": "list"}}
    },
    "relationship_types": ["works_at"],
    "trigger_conditions": {"required_properties": ["content"]}
}

# Configure LLM settings
llm_config = {
    "api_key": "YOUR_OPENAI_API_KEY",
    "model_name": "gpt-4o",
    "temperature": 0.0,
    "max_tokens": 1500
}

# Initialize Memory (backend is defined here; use "local" for testing)
memory = Memory(
    backend="local",
    ontology_config=ontology_config,
    extraction_rules=extraction_rules,
    auto_embedding=True,
    llm_config=llm_config,
    db_path="graph.json"
)
~~~

### Step 3: Ingest Data

Use the `ingest()` method to add new memories (e.g., documents) into your graph. The SmartNodeProcessor automatically extracts entities, deduplicates nodes, and updates your graph based on the text.

~~~python
doc_text = (
    "John Doe is a brilliant software engineer at Innotech. "
    "He is known for his innovative coding and leadership skills. "
    "Innotech is a rising tech company specializing in innovative solutions."
)

result = memory.ingest(doc_text)
print("Document ID:", result["id"])
print("Processing Iterations:")
print("\n".join(result["processing_result"].get("chain_of_thought", [])))
~~~

### Step 4: Query Your Memory

Use the `ask()` method to pose natural language questions about your data. This leverages the SmartRetrievalTool to perform a detailed chain‑of‑thought reasoning process.

~~~python
answer = memory.ask("Who works at Innotech?")
print("Final Answer:", answer["final_answer"])
print("Chain of Thought:")
print("\n".join(answer["chain_of_thought"]))
~~~

### Additional Query Examples

Beyond `ask()`, you can perform various types of queries directly using the unified API. Here are a few examples:

- **Custom Query via Query Object:**

  ~~~python
  from graphista import Query

  # Retrieve all Company nodes
  q = Query()
  q.filter(Query.label_equals("Company"))
  companies = memory.query(q)
  print("Company Nodes:", companies)
  ~~~

- **Hybrid Vector and Property Search:**

  ~~~python
  q = Query()
  q.filter(Query.property_equals("industry", "tech"))
  q.vector_nearest(embedding_field="embedding", query_vector=[0.1, 0.2, 0.3], k=5, min_score=0.7)
  results = memory.query(q)
  print("Hybrid Search Results:", results)
  ~~~

- **Keyword Retrieval:**

  ~~~python
  memories = memory.retrieve("innovative")
  print("Memories containing 'innovative':", memories)
  ~~~

For a full list of available query functions, refer to the [GraphRouter README](graphrouter/README.md).

## Advanced Usage

Graphista offers advanced functionalities for power users. For example:

- **Batch Operations:** Efficiently create multiple nodes and edges in a single operation.

  ~~~python
  nodes = [
      {'label': 'Person', 'properties': {'name': f'User{i}', 'age': 20 + i}}
      for i in range(1000)
  ]
  node_ids = memory.db.batch_create_nodes(nodes)
  ~~~

- **Path Queries:** Discover indirect relationships between nodes.

  ~~~python
  from graphista import Query

  q = Query()
  q.find_path('Person', 'Company', ['works_at'], min_depth=1, max_depth=3)
  paths = memory.db.query(q)
  print("Paths found:", paths)
  ~~~

For more details, see the [Advanced Usage Guide](advanced_usage.md) and the [API Reference](api_reference.md).

## Installation

Clone the repository from GitHub:

~~~bash
git clone https://github.com/pippinlovesyou/graphista.git
cd graphista
~~~

## Discord Support

Join our Discord community for support:  
[https://discord.gg/xNXnJ5JFsA](https://discord.gg/xNXnJ5JFsA)

## Contributing

Contributions, issues, and feature requests are welcome! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License.

---

Happy graphing and knowledge discovery with **Graphista**!
