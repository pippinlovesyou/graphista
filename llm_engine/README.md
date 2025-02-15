# LLM Engine

This component provides LLM-powered functionality for automated node processing, property extraction, and intelligent graph operations within **Graphista**. The LLM Engine integrates multiple sub-components that work together to process, deduplicate, and query your graph data using natural language.

**Note:** Advanced features—such as asynchronous operations and support for Neo4j/FalkorDB backends—are still under development and not yet fully tested.

## Components Overview

Graphista’s LLM Engine is composed of the following key components:

1. **NodeProcessor and SmartNodeProcessor**  
   - **NodeProcessor:** Handles automated node processing using configurable extraction rules and integrates with your graph's ontology.
   - **SmartNodeProcessor (in `llm_smart_node_processor.py`):**  
     A smarter version that pre-chunks long node content and processes each chunk sequentially using a chain‑of‑thought loop. It decides whether to create new nodes, update existing nodes, or add edges between nodes—delegating duplicate detection to the `find_similar_nodes` tool. Batch creation and update tools are provided, and the final output is a JSON summary of all node/edge actions performed.  
     *Note: This component is experimental and may require further tuning.*

2. **LiteLLM Integration**  
   Provides core LLM functionality for:
   - Structured extraction (using defined schemas)
   - Embedding generation
   - Basic error handling and retries  
   *(Advanced rate limiting and robust retry mechanisms are under active development.)*

3. **SmartRetrievalTool (in `llm_cot_tool.py`)**  
   Implements a chain‑of‑thought loop for natural language querying. This tool:
   - Leverages LLM-powered reasoning to generate multi-step responses.
   - Utilizes a set of read-only operations (query, vector search, get_node, etc.) to fetch data from the graph.
   - Returns a detailed JSON output including a final answer and a chain‑of‑thought log.  
   *Note: Advanced chain‑of‑thought capabilities are experimental and subject to further improvement.*

## Usage Examples

### Basic Node Processing with SmartNodeProcessor

~~~python
from llm_engine.litellm_client import LiteLLMClient
from llm_engine.node_processor import NodeProcessor, ExtractionRule, NodePropertyRule
from graphrouter import LocalGraphDatabase, Ontology

# Initialize LLM client and local graph database
llm_client = LiteLLMClient(
    api_key="YOUR_OPENAI_API_KEY",
    model_name="gpt-4o",
    temperature=0.0,
    max_tokens=1500
)
db = LocalGraphDatabase()
db.connect(db_path="graph.json")
ontology = Ontology()
# Configure your ontology as needed...
db.set_ontology(ontology)

# Instantiate SmartNodeProcessor for advanced extraction
processor = NodeProcessor(llm_client, db)  # Alternatively, use SmartNodeProcessor for deduplication and chunked processing

# Define extraction rules
rule = ExtractionRule(
    extractable_types={
        "Person": NodePropertyRule(target_schema={"name": str, "role": str, "embedding": list}),
        "Company": NodePropertyRule(target_schema={"name": str, "industry": str, "embedding": list})
    },
    relationship_types=["WORKS_AT"],
    trigger_conditions={"required_properties": ["content"], "content_length_min": 10}
)
processor.register_rule(rule)

# Process a document node for extraction
node_id = "document_123"
document_node = {"label": "Document", "properties": {"content": "John Doe is an innovative engineer at Innotech."}}
processor.process_node(node_id, document_node)
~~~

### Querying with SmartRetrievalTool (Chain‑of‑Thought)

~~~python
from llm_engine.litellm_client import LiteLLMClient
from llm_engine.llm_cot_tool import SmartRetrievalTool
from graphrouter import LocalGraphDatabase, Ontology, Query

# Initialize components
llm_client = LiteLLMClient(
    api_key="YOUR_OPENAI_API_KEY",
    model_name="gpt-4o",
    temperature=0.0,
    max_tokens=1500
)
db = LocalGraphDatabase()
db.connect(db_path="graph.json")
ontology = Ontology()
# Configure your ontology as needed...
db.set_ontology(ontology)

# Instantiate SmartRetrievalTool for answering queries
retrieval_tool = SmartRetrievalTool(llm_client, db, ontology, max_iterations=20)

# Ask a natural language question
result = retrieval_tool.run("Who is the software engineer mentioned in the document?")
print("Final Answer:", result["final_answer"])
print("Chain of Thought:")
print("\n".join(result["chain_of_thought"]))
~~~

## Additional Notes

- **Asynchronous Operations:**  
  Although async methods exist in the underlying libraries, asynchronous support in Graphista is not yet fully tested.

- **Backend Support:**  
  Graphista supports multiple backends (Local JSON, Neo4j, FalkorDB). Currently, only the local JSON backend is fully tested; Neo4j and FalkorDB support remain experimental.

- **Error Handling & Retry:**  
  Basic error handling and simple retry mechanisms are implemented. Comprehensive strategies for rate limiting and robust retries are under active development.

## Further Documentation

For additional details on each component and advanced usage, please refer to:
- **GraphRouter:** [graphrouter/README.md](graphrouter/README.md)
- **Data Ingestion Pipeline:** [ingestion_engine/README.md](ingestion_engine/README.md)
- **Advanced Usage Guides:** [docs/advanced_usage.md](advanced_usage.md)

Happy graphing and exploring with **Graphista**!
