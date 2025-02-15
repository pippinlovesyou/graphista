
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .node_processor import NodeProcessor, ExtractionRule

@dataclass
class EnrichmentConfig:
    """Configuration for node enrichment"""
    source_types: List[str]  # Types of nodes/data to enrich from
    target_types: List[str]  # Types of nodes to create/enrich
    properties_to_extract: Optional[List[str]] = None
    relationship_types: Optional[List[str]] = None
    llm_schema: Optional[Dict[str, Any]] = None

class NodeEnrichmentManager:
    def __init__(self, node_processor: NodeProcessor):
        self.processor = node_processor
        self.enrichment_configs: Dict[str, EnrichmentConfig] = {}
        
    def register_enrichment(self, source_type: str, config: EnrichmentConfig):
        """Register enrichment configuration for a source type"""
        self.enrichment_configs[source_type] = config
        
        # Create extraction rule for node processor
        rule = ExtractionRule(
            node_label=source_type,
            extract_nodes=True,
            extract_properties=True,
            target_schema=config.llm_schema,
            multi_node_types=config.target_types,
            extract_params=config.properties_to_extract,
            relationship_types=config.relationship_types
        )
        self.processor.register_rule(rule)
        
    def process_ingested_data(self, source_type: str, data: Dict[str, Any]) -> None:
        """Process newly ingested data"""
        if config := self.enrichment_configs.get(source_type):
            self.processor.process_node(data["id"], data)
