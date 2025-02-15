# GraphRouter Project To-Do List

This updated to-do list integrates our existing roadmap with the new vision for configurable, rule‐based deduplication and merge‐on‐query functionality. The aim is to simplify the ingestion process (using one unified ingestion pipeline) while allowing users to enable and configure various deduplication strategies (LLM-based, similarity score threshold, chained, parameter-triggered, etc.) and to provide an optional “merge on query” mechanism for embedded nodes.

---

## High Priority

1. **Core Database Features:**
   - [~] Complete query builder implementation (70% coverage)
   - [~] Implement transaction management (80% coverage)
   - [~] Finish connection pooling for all database backends (50% coverage)
   - [~] Add async support for database operations (70% coverage)

2. **LLM Integration and Extraction Enhancements:**
   - [~] Enhance extraction rules system (40% coverage)
   - [~] Add support for custom LLM providers (80% coverage)
   - [ ] **Implement Merge-on-Query Functionality:**
     - [ ] Add a query option for merge-on-query for embedded nodes.
     - [ ] When enabled, perform a similarity search (with optional parameter filters) on node embeddings.
     - [ ] Feed candidate similar nodes into an LLM call to generate a “same entity” likelihood score.
     - [ ] Store this likelihood score as a unique relationship type (and update the ontology if configured).
     - [ ] Provide a function to temporarily treat two nodes as the same based on the computed score.
   - [ ] Implement batch extraction optimization (0% coverage)
   - [ ] Add extraction caching (0% coverage)

3. **Data Ingestion and Deduplication:**
   - [~] Complete CSV/JSON ingestion pipeline (30% coverage)
   - [ ] **Implement Configurable Deduplication Rules for Ingestion:**
     - [ ] Remove the need for separate ingestion pipelines—use a single, unified ingestion process.
     - [ ] Allow users to configure deduplication rules via parameters:
       - LLM-based deduplication
       - Similarity score threshold (using semantic embeddings)
       - Chained or parameter-triggered deduplication criteria
       - Other custom rule triggers (e.g., source confidence, extraction metadata)
     - [ ] Integrate these deduplication options into the node and edge creation process (leveraging full metadata and ontology mapping).
   - [ ] Add webhook handling system (0% coverage)
   - [ ] Implement real-time data sync (0% coverage)
   - [~] Add data validation rules (40% coverage)

---

## Medium Priority

1. **Performance:**
   - [~] Implement query caching (50% coverage)
   - [~] Add connection pooling metrics (30% coverage)
   - [ ] Optimize batch operations (0% coverage)
   - [~] Add performance monitoring (40% coverage)

2. **Graph Features:**
   - [~] Add pattern matching queries (60% coverage)
   - [~] Implement graph traversal operations (40% coverage)
   - [ ] Add support for graph algorithms (0% coverage)
   - [~] Enhance ontology validation (70% coverage)

3. **Testing:**
   - [~] Increase overall test coverage (currently 56%)
   - [~] Add integration tests (40% coverage)
   - [ ] Implement performance benchmarks (0% coverage)
   - [ ] Add stress testing (0% coverage)

---

## Low Priority

1. **Documentation:**
   - [~] Add API reference docs (50% complete)
   - [~] Create usage tutorials (30% complete)
   - [~] Document configuration options (40% complete)
   - [ ] Add deployment guides (0% complete)

2. **Developer Tools:**
   - [~] Add development console (60% complete)
   - [ ] Create debug tools (0% complete)
   - [ ] Add query visualization (0% complete)
   - [~] Implement logging system (30% complete)

---

## Environment Setup

- Python 3.8+
- Required packages listed in `pyproject.toml`

---

## Testing Requirements

1. **Unit Tests** for all components:
   - Core database functionality
   - Deduplication rule processing and configuration
   - Embedding generation and similarity computation
   - Merge-on-query logic
2. **Integration Tests** for:
   - Local JSON database
   - Neo4j backend
   - FalkorDB backend
   - LLM integration and extraction pipeline
   - Data ingestion (including deduplication options)

---

## Additional Notes

- **Deduplication Options:**  
  Deduping should be configurable with a variety of rule types:
  - **LLM-Based Deduplication:** Invoke LLM calls to semantically compare nodes.
  - **Similarity Score Threshold:** Compute and compare node embeddings.
  - **Chained/Conditional Rules:** Combine multiple criteria (e.g., metadata, extraction confidence) to trigger deduplication.
- **Merge-on-Query:**  
  When enabled via a query option, the engine will perform:
  - A similarity search (with optional filtering parameters) on embedded nodes.
  - An LLM call to produce a likelihood score indicating whether two nodes represent the same entity.
  - Storage of this score as a unique relationship type (which is added to the ontology if necessary).
  - A temporary “merging” function to treat nodes as one based on configuration.
- **Simplicity and Flexibility:**  
  The ingestion engine should remain generic yet robust and flexible. It will use a single ingestion pipeline that accepts deduplication rules as options rather than splitting the process into multiple pipelines.
- **Optional Extensions:**  
  Integration with Composio and similar tools should be considered optional extensions rather than core features.

