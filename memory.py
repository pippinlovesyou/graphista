import os
import json
import logging
import tempfile
import webbrowser
from datetime import datetime

from graphrouter import (
    LocalGraphDatabase,
    Neo4jGraphDatabase,
    FalkorDBGraphDatabase,
    Ontology,
    Query
)
from llm_engine.litellm_client import LiteLLMClient
from llm_engine.llm_smart_node_processor import SmartNodeProcessor
from llm_engine.llm_cot_tool import SmartRetrievalTool  # for natural language querying
from ingestion_engine.ingestion_engine import IngestionEngine

HISTORY = []

class Memory:
    """
    Unified entry point for the GraphRouter framework.
    This Memory class now uses our new SmartNodeProcessor for deduplication and node updating.
    """

    def __init__(self, *, backend="local", ontology_config=None, extraction_rules=None,
                 auto_embedding=True, llm_config=None, **kwargs):
        self.logger = logging.getLogger("Memory")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
            self.logger.addHandler(handler)

        self.logger.debug("Initializing Memory instance...")

        # Instantiate the appropriate graph database backend.
        if backend.lower() == "local":
            self.logger.debug("Using local backend.")
            self.db = LocalGraphDatabase()
            db_path = kwargs.get("db_path", "graph.json")
            self.logger.debug("Connecting to local database at: %s", db_path)
            self.db.connect(db_path=db_path)
        elif backend.lower() == "neo4j":
            self.logger.debug("Using neo4j backend.")
            self.db = Neo4jGraphDatabase()
            uri = kwargs.get("uri")
            username = kwargs.get("username")
            password = kwargs.get("password")
            if not (uri and username and password):
                raise ValueError("For neo4j backend, 'uri', 'username', and 'password' must be provided.")
            self.logger.debug("Connecting to neo4j at: %s", uri)
            self.db.connect(uri=uri, username=username, password=password)
        elif backend.lower() == "falkordb":
            self.logger.debug("Using falkordb backend.")
            self.db = FalkorDBGraphDatabase()
            self.db.connect(**kwargs)
        else:
            raise ValueError(f"Unsupported backend '{backend}'.")
        self.logger.info(f"Connected to {backend} backend.")

        # Load ontology
        if ontology_config is None:
            self.logger.debug("No ontology_config provided; using empty ontology.")
            self.ontology = Ontology()
        elif isinstance(ontology_config, str):
            try:
                self.logger.debug("Loading ontology from file: %s", ontology_config)
                with open(ontology_config, "r") as f:
                    data = json.load(f)
                self.ontology = Ontology.from_dict(data)
            except Exception as e:
                self.logger.error(f"Failed to load ontology from {ontology_config}: {e}")
                raise
        elif isinstance(ontology_config, dict):
            self.logger.debug("Loading ontology from provided dictionary.")
            self.ontology = Ontology.from_dict(ontology_config)
        else:
            raise ValueError("ontology_config must be a filepath string or a dictionary.")

        # Load extraction rules (if provided)
        if extraction_rules is not None:
            if isinstance(extraction_rules, str):
                try:
                    self.logger.debug("Loading extraction rules from file: %s", extraction_rules)
                    with open(extraction_rules, "r") as f:
                        data = json.load(f)
                    self.extraction_rules = data
                except Exception as e:
                    self.logger.error(f"Failed to load extraction rules from {extraction_rules}: {e}")
                    raise
            elif isinstance(extraction_rules, dict):
                self.logger.debug("Loading extraction rules from provided dictionary.")
                self.extraction_rules = extraction_rules
            else:
                raise ValueError("extraction_rules must be a filepath string or a dictionary.")
        else:
            self.extraction_rules = None

        self._validate_configurations()
        self.db.set_ontology(self.ontology)
        self.logger.info("Ontology loaded and set on the database.")
        self.logger.debug("Ontology data: %s", json.dumps(self.ontology.to_dict(), indent=2))
        self.auto_embedding = auto_embedding
        self.logger.debug("Auto embedding is set to: %s", self.auto_embedding)

        # Initialize LLM integration.
        if self.auto_embedding or self.extraction_rules is not None:
            api_key = None
            if llm_config and "api_key" in llm_config:
                api_key = llm_config["api_key"]
            else:
                api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.logger.warning("No API key provided for LLM integration; auto_embedding and extraction may not work.")
            model_name = llm_config.get("model_name", "gpt-4o") if llm_config else "gpt-4o"
            temperature = llm_config.get("temperature", 0.0) if llm_config else 0.0
            max_tokens = llm_config.get("max_tokens", 1500) if llm_config else 1500
            self.logger.debug("Initializing LLM client with model: %s", model_name)
            self.llm_client = LiteLLMClient(api_key=api_key, model_name=model_name,
                                            temperature=temperature, max_tokens=max_tokens)
        else:
            self.logger.debug("LLM client not required; skipping initialization.")
            self.llm_client = None

        # Initialize our new SmartNodeProcessor for ingestion (deduplication and updates).
        if self.llm_client:
            self.logger.debug("Initializing SmartNodeProcessor for deduplication and updates.")
            self.smart_node_processor = SmartNodeProcessor(
                llm_client=self.llm_client,
                db=self.db,
                ontology=self.ontology,
                max_iterations=25,
                max_chunk_tokens=500
            )
        else:
            self.logger.debug("SmartNodeProcessor not initialized due to missing LLM client.")
            self.smart_node_processor = None

        # Initialize SmartRetrievalTool (llm_cot_tool) for natural language querying (asking questions).
        if self.llm_client:
            self.logger.debug("Initializing SmartRetrievalTool for natural language querying.")
            self.smart_tool = SmartRetrievalTool(
                llm_client=self.llm_client,
                db=self.db,
                ontology=self.ontology
            )
        else:
            self.logger.debug("SmartRetrievalTool not initialized due to missing LLM client.")
            self.smart_tool = None

        # Initialize IngestionEngine for file ingestion.
        self.logger.debug("Initializing IngestionEngine for file ingestion.")
        from ingestion_engine.ingestion_engine import IngestionEngine
        self.ingestion_engine = IngestionEngine(
            router_config={"type": backend, "db_path": kwargs.get("db_path", "graph.json")},
            default_ontology=self.ontology.to_dict(),
            auto_extract_structured_data=self.auto_embedding,
            extraction_rules=self.extraction_rules
        )
        self.logger.info("Memory initialized successfully.")

    def _validate_configurations(self):
        if not isinstance(self.ontology.node_types, dict) or not isinstance(self.ontology.edge_types, dict):
            raise ValueError("Ontology format invalid: 'node_types' and 'edge_types' must be dictionaries.")
        if self.extraction_rules is not None:
            if not isinstance(self.extraction_rules, dict):
                raise ValueError("Extraction rules must be a dictionary.")
            if "extractable_types" not in self.extraction_rules:
                raise ValueError("Extraction rules must contain an 'extractable_types' key.")

    def ingest(self, text: str):
        if not text:
            raise ValueError("Text to ingest cannot be empty.")
        try:
            self.logger.debug("Ingesting text: %s", text)
            doc_id = self.db.create_node("Document", {"content": text})
            self.logger.info("Document node created with id: %s", doc_id)
            # Retrieve the created document node.
            node = self.db.get_node(doc_id)
            processing_result = {}
            # Use our SmartNodeProcessor to process the node.
            if self.smart_node_processor:
                self.logger.debug("Processing Document node with SmartNodeProcessor.")
                processing_result = self.smart_node_processor.run(doc_id, node)
                # Log the chain-of-thought to history.
                HISTORY.append({
                    "type": "ingest_processor",
                    "doc_id": doc_id,
                    "chain_of_thought": processing_result.get("chain_of_thought", []),
                    "timestamp": str(datetime.now())
                })
            # Return both document ID and the processing result.
            return {"id": doc_id, "processing_result": processing_result}
        except Exception as e:
            self.logger.exception("Failed to ingest text:")
            raise

    def ingest_file(self, file_path: str):
        if not file_path:
            raise ValueError("File path cannot be empty.")
        try:
            self.logger.debug("Ingesting file: %s", file_path)
            file_node_id = self.ingestion_engine.upload_file(file_path, source_name="FileIngestion")
            self.logger.info("File ingested with node id: %s", file_node_id)
            return file_node_id
        except Exception as e:
            self.logger.exception(f"Failed to ingest file '{file_path}':")
            raise

    def ask(self, query: str) -> dict:
        if not query:
            raise ValueError("Query cannot be empty.")
        try:
            self.logger.debug("Processing query: %s", query)
            def update_callback(update):
                HISTORY.append({
                    "type": "iteration_update",
                    "data": update,
                    "timestamp": str(datetime.now())
                })
            # IMPORTANT: For asking questions, we now use the SmartRetrievalTool (llm_cot_tool)
            # so that we return a detailed chain-of-thought and final answer.
            if self.smart_tool is not None:
                result = self.smart_tool.run(query, update_callback=update_callback)
            elif self.smart_node_processor:
                # Fallback (should not normally happen)
                dummy_node_id = "new_Question"
                dummy_node_data = {"label": "Question", "properties": {"content": query}}
                result = self.smart_node_processor.run(dummy_node_id, dummy_node_data, update_callback=update_callback)
            else:
                self.logger.warning("No retrieval tool is configured, returning fallback answer.")
                return {"final_answer": "LLM integration not configured.", "chain_of_thought": []}
            HISTORY.append({
                "type": "ask",
                "query": query,
                "final_answer": result.get("final_answer", ""),
                "timestamp": str(datetime.now())
            })
            return result
        except Exception as e:
            self.logger.exception(f"Failed to process query '{query}':")
            raise

    def retrieve(self, keyword: str):
        if not keyword:
            raise ValueError("Keyword cannot be empty.")
        try:
            self.logger.debug("Retrieving memories for keyword: %s", keyword)
            q = Query()
            q.filter(Query.property_contains("content", keyword))
            results = self.db.query(q)
            self.logger.info("Retrieved %d memories for keyword '%s'.", len(results), keyword)
            return results
        except Exception as e:
            self.logger.exception(f"Failed to retrieve memories for keyword '{keyword}':")
            raise

    def query(self, query_input):
        try:
            if isinstance(query_input, str):
                if self.smart_tool is None:
                    raise RuntimeError("SmartRetrievalTool is not initialized.")
                self.logger.debug("Running natural language query: %s", query_input)
                result = self.smart_tool.run(query_input)
                self.logger.info("Custom natural language query executed.")
                return result
            elif isinstance(query_input, Query):
                self.logger.debug("Running custom Query object.")
                results = self.db.query(query_input)
                self.logger.info("Custom Query executed.")
                return results
            else:
                raise ValueError("Invalid query_input. Must be a string or a Query object.")
        except Exception as e:
            self.logger.exception("Failed to execute custom query:")
            raise

    def get_graph(self):
        try:
            self.logger.debug("Retrieving full graph data.")
            if isinstance(self.db.nodes, dict):
                nodes = []
                for node_id, node in self.db.nodes.items():
                    new_node = dict(node)
                    new_node["id"] = node_id
                    nodes.append(new_node)
            else:
                nodes = self.db.nodes

            if isinstance(self.db.edges, dict):
                edges = []
                for edge_id, edge in self.db.edges.items():
                    new_edge = dict(edge)
                    new_edge["id"] = edge_id
                    edges.append(new_edge)
            else:
                edges = self.db.edges

            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            self.logger.exception("Failed to retrieve graph data:")
            raise

    def get_ontology_data(self):
        try:
            self.logger.debug("Retrieving ontology data.")
            if hasattr(self.ontology, "to_dict"):
                return self.ontology.to_dict()
            else:
                return {}
        except Exception as e:
            self.logger.exception("Failed to retrieve ontology data:")
            raise

    def visualize(self):
        try:
            self.logger.debug("Preparing graph visualization.")
            graph_data = {
                "nodes": self.db.nodes,
                "edges": self.db.edges
            }
            html_content = f"""
            <html>
            <head>
                <title>Memory Graph Visualization</title>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    pre {{ background-color: #f4f4f4; padding: 10px; }}
                </style>
            </head>
            <body>
                <h1>Memory Graph Visualization</h1>
                <pre>{json.dumps(graph_data, indent=2)}</pre>
            </body>
            </html>
            """
            with tempfile.NamedTemporaryFile('w', delete=False, suffix=".html") as f:
                f.write(html_content)
                temp_filename = f.name
            self.logger.debug("Opening browser with graph visualization at: %s", temp_filename)
            webbrowser.open(f"file://{temp_filename}")
            self.logger.info("Graph visualization opened in browser.")
        except Exception as e:
            self.logger.exception("Failed to visualize graph:")
            raise

    def close(self):
        try:
            self.logger.debug("Closing connection to database.")
            self.db.disconnect()
            self.logger.info("Database disconnected.")
        except Exception as e:
            self.logger.exception("Error during disconnect:")
            raise
