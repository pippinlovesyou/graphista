# Quick Start Guide - Graphista

This guide will help you quickly set up and start using Graphista for graph‑based memory management. Graphista integrates LLM‑powered ingestion and querying tools to enable dynamic knowledge management.

## Step 1: Installation

Clone the Graphista repository from GitHub:

~~~bash
git clone https://github.com/pippinlovesyou/graphista.git
cd graphista
~~~

Then install the package locally:

~~~bash
pip install -e .
~~~

## Step 2: Initialize Memory with LLM Integration

Graphista’s unified `Memory` class encapsulates the graph database backend (local, Neo4j, FalkorDB), ontology, LLM integration, and data ingestion. In your application, simply import `Memory` and create an instance with your configuration. For example, using the default local JSON backend:

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
    "relationship_types": ["WORKS_AT"],
    "trigger_conditions": {"required_properties": ["content"]}
}

# Configure LLM settings
llm_config = {
    "api_key": "YOUR_OPENAI_API_KEY",
    "model_name": "gpt-4o",
    "temperature": 0.0,
    "max_tokens": 1500
}

# Initialize Memory. The 'backend' parameter sets the graph database to use; here we use "local".
memory = Memory(
    backend="local",
    ontology_config=ontology_config,
    extraction_rules=extraction_rules,
    auto_embedding=True,
    llm_config=llm_config,
    db_path="graph.json"
)
~~~

## Step 3: Ingest Data

Add new memories (documents) to your graph. The LLM-powered ingestion engine will automatically extract entities, deduplicate nodes, and update your graph.

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

## Step 4: Query Your Memory

Use the `ask()` method to pose natural language queries about your data. This leverages the SmartRetrievalTool to perform detailed chain‑of‑thought reasoning.

~~~python
answer = memory.ask("Who is the software engineer mentioned in the document?")
print("Final Answer:", answer["final_answer"])
print("Chain of Thought:")
print("\n".join(answer["chain_of_thought"]))
~~~

## Additional Query Examples

Beyond `ask()`, you can perform various types of queries using the unified API. For example:

- **Custom Query via Query Object:**

  ~~~python
  from graphista import Query

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

## Demo Front-End

A demo front‑end is provided in `example.py`. This Flask‑based web interface lets you:
- **Add Memory:** Submit text to be ingested and view processing iterations.
- **Ask Questions:** Enter natural language queries and view detailed chain‑of‑thought responses.
- **Visualize Graph:** See your data as a visual network and in JSON format.
- **Review History:** Check a log of recent operations.

To run the demo:
~~~bash
python example.py
~~~
Then open [http://localhost:5000](http://localhost:5000) in your browser.

## Discord Support

Join our Discord community for support:
[https://discord.gg/xNXnJ5JFsA](https://discord.gg/xNXnJ5JFsA)

## Next Steps

For more details:
- Read the [Advanced Usage Guide](advanced_usage.md)
- Consult the [API Reference](api_reference.md)
- Review the [Installation Guide](installation.md)

Happy graphing with **Graphista**!
