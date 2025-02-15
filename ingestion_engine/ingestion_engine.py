"""
Ingestion Engine for Automated Graph Updates

This engine handles:

1. File Upload (with CSV auto-parsing)
2. Authentication & Download (via Composio) 
3. Regular Sync / Historical Data Collection
4. Search & Dedupe
5. Webhook Handling (auth-enabled)
6. Automatic Structured Extraction of Logs/Data
7. Linking to a default/core ontology for consistent node/relationship types
"""

import os
import json
import csv
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from graphrouter.core_ontology import create_core_ontology, extend_ontology

# Default / Core Ontology
CORE_ONTOLOGY = {
    "DataSource": {
        "description": "Represents a distinct data source (webhook, Airtable, Gmail, etc.)."
    },
    "File": {
        "description": "Represents an uploaded file, e.g., CSV, PDF, etc."
    },
    "Row": {
        "description": "Represents a single row from a parsed CSV or similar tabular structure."
    },
    "Log": {
        "description": "Represents a log or log entry associated with an ingestion event."
    },
    "SearchResult": {
        "description": "Represents a single search result (deduplicated if needed)."
    },
    "Webhook": {
        "description": "Represents an inbound or outbound webhook endpoint or event."
    },
    # Add additional core types as your system requires
}


class IngestionEngine:
    """Engine for data ingestion and enrichment."""

    def __init__(
        self,
        router_config: Optional[Dict[str, Any]] = None,
        composio_config: Optional[Dict[str, Any]] = None,
        default_ontology: Optional[Any] = None,     # Added parameter
        auto_extract_structured_data: bool = False,
        extraction_rules: Optional[Dict[str, List[str]]] = None,
        deduplicate_search_results: bool = True,
        schedule_interval: Optional[int] = None,
        llm_integration: Optional[Any] = None
    ):
        """Initialize the ingestion engine."""
        self.logger = logging.getLogger("IngestionEngine")

        # If router_config is not provided, default to local with default path.
        if router_config is None:
            router_config = {'type': 'local', 'path': 'graph.json'}
        else:
            # If no "type" key is provided but a "db_path" is present,
            # assume local backend and map "db_path" to "path".
            if 'type' not in router_config:
                router_config['type'] = 'local'
            if 'db_path' in router_config and 'path' not in router_config:
                router_config['path'] = router_config.pop('db_path')

        self.logger.info("Initializing GraphRouter backend.")
        if router_config['type'] == 'local':
            from graphrouter.local import LocalGraphDatabase
            self.db = LocalGraphDatabase()
            # Use 'path' from router_config
            self.db.connect(router_config.get('path', 'graph.json'))
        else:
            raise ValueError(f"Unsupported database type: {router_config['type']}")

        # Store additional config
        self.auto_extract_structured_data = auto_extract_structured_data
        self.extraction_rules = extraction_rules or {}
        self.deduplicate_search_results = deduplicate_search_results
        self.schedule_interval = schedule_interval
        self.composio_config = composio_config
        self.composio_toolset = None  # Initialize composio toolset attribute

        # Store the ontology if given, else None
        self.ontology = default_ontology

        # LLM integration
        self.llm_integration = llm_integration
        if llm_integration:
            from llm_engine.node_processor import NodeProcessor
            from llm_engine.enrichment import NodeEnrichmentManager
            self.node_processor = NodeProcessor(llm_integration)
            self.enrichment_manager = NodeEnrichmentManager(self.node_processor)

    def upload_file(self, file_path: str, source_name: str, parse_csv: bool = False) -> str:
        """Upload a file and create a File node."""
        # Create data source if it doesn't exist
        self.logger.debug(f"Creating DataSource '{source_name}'.")
        source_id = self._get_or_create_source(source_name)

        file_node = {
            'label': 'File',
            'name': os.path.basename(file_path),
            'source_id': source_id,
            'upload_time': datetime.now().isoformat(),
            'processed': False
        }

        file_node_id = self.db.create_node('File', file_node)
        self.db.create_edge(file_node_id, source_id, 'FROM_SOURCE', properties={})

        if parse_csv and file_path.endswith('.csv'):
            self.logger.info(f"Parsing CSV: {file_node['name']}")
            self._process_csv(file_path, file_node_id)

        self.logger.info(f"File '{file_node['name']}' uploaded. Node ID: {file_node_id}")
        return file_node_id

    def _process_csv(self, file_path: str, file_node_id: str) -> None:
        """Process a CSV file and create Row nodes."""
        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row_node = {
                    'label': 'Row',
                    'data': row,
                    'file_id': file_node_id,
                    'created_at': datetime.now().isoformat()
                }
                row_id = self.db.create_node('Row', row_node)
                self.db.create_edge(file_node_id, row_id, 'HAS_ROW', properties={})

    def _get_or_create_source(self, source_name: str) -> str:
        """Get or create a DataSource node."""
        results = None
        query = self.db.create_query()
        try:
            query.filter(query.label_equals('DataSource'))
            query.filter(query.property_equals('name', source_name))
            results = self.db.query(query)
        except AttributeError:
            # Fallback for query object lacking filter methods.
            self.logger.warning("Query object does not have filter method. Using alternative query approach.")
            query = f"MATCH (n:DataSource{{name:'{source_name}'}}) RETURN n"
            results = self.db.query(query)

        if results:
            if isinstance(results, list):
                return results[0]['id']
            elif isinstance(results, dict) and 'n' in results and isinstance(results['n'], list) and results['n']:
                return results['n'][0]['id']
            else:
                self.logger.warning(f"Unexpected results format from query: {results}")
                return None

        source_node = {
            'name': source_name,
            'created_at': datetime.now().isoformat()
        }
        return self.db.create_node('DataSource', source_node)

    def enrich_with_llm(self, node_id: str, enrichment_type: str, processor=None) -> None:
        """Enrich a node with LLM-generated content."""
        if processor is None and not self.llm_integration:
            raise ValueError("Node processor or LLM integration is required for enrichment")

        processor = processor or self.node_processor

        # Get the node
        node = self.db.get_node(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        # Process the node
        enriched_data = processor.process_node(node, enrichment_type)

        # Update node with enriched data
        if enriched_data:
            node['properties'].update(enriched_data)
            self.db.update_node(node_id, node['properties'])

        # Create enrichment record
        enrichment_node = {
            'type': enrichment_type,
            'timestamp': datetime.now().isoformat(),
            'source': 'LLM'
        }

        enrichment_id = self.db.create_node('Enrichment', enrichment_node)
        self.db.create_edge(node_id, enrichment_id, 'HAS_ENRICHMENT', properties={})

    def search_and_store_results(self, query_str: str) -> None:
        """Stub for search functionality."""
        self.logger.info(f"Search request for: {query_str}")
        # For testing purposes, we'll just create a search result node
        result_node = {
            'query': query_str,
            'timestamp': datetime.now().isoformat()
        }
        self.db.create_node('SearchResult', result_node)

    def handle_webhook(self, webhook_data: Dict[str, Any], data_source_name: str) -> None:
        """Handle incoming webhook data."""
        # Create source if it doesn't exist
        source_id = self._get_or_create_source(data_source_name)

        # Create webhook node
        webhook_node = {
            'data': webhook_data,
            'timestamp': datetime.now().isoformat()
        }
        webhook_id = self.db.create_node('Webhook', webhook_node)

        # Link to source
        self.db.create_edge(webhook_id, source_id, 'FROM_SOURCE', properties={})

        # Create log entry
        log_node = {
            'type': 'webhook_event',
            'timestamp': datetime.now().isoformat(),
            'data': json.dumps(webhook_data)
        }
        log_id = self.db.create_node('Log', log_node)
        self.db.create_edge(webhook_id, log_id, 'HAS_LOG', properties={})
