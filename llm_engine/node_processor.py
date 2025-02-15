# llm_engine/node_processor.py

"""
llm_engine/node_processor.py

Processes nodes using extraction rules, LLM integration, and database operations.
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from graphrouter.errors import InvalidNodeTypeError, InvalidPropertyError

@dataclass
class NodePropertyRule:
    target_schema: Optional[Dict[str, Any]] = None
    extract_params: Optional[List[str]] = None
    overwrite_existing: bool = True
    conditions: Optional[Dict[str, Any]] = None

@dataclass 
class ExtractionRule:
    extractable_types: Dict[str, NodePropertyRule]
    relationship_types: Optional[List[str]] = None
    trigger_conditions: Optional[Dict[str, Any]] = None
    source_type: Optional[str] = None

    def __post_init__(self):
        if not self.extractable_types:
            raise ValueError("Must specify at least one extractable type")
        if self.relationship_types is not None:
            if not isinstance(self.relationship_types, list):
                raise ValueError("relationship_types must be a list")
            if not all(isinstance(rt, str) for rt in self.relationship_types):
                raise ValueError("All relationship types must be strings")
            # Normalize all relationship types to lower case.
            self.relationship_types = [rt.lower() for rt in self.relationship_types]

#############################
# Helper functions for auto‑updating ontology
#############################

def infer_type(value: Any) -> str:
    if isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, list):
        return "list"
    else:
        return "str"

def auto_update_node_ontology(ontology, node_type: str, new_props: dict) -> None:
    """
    Auto-update (or create) the node type in the ontology.
    If the node type does not exist, create it with the given properties.
    Otherwise, for each key in new_props that is missing in the ontology,
    infer its type and add it.
    """
    if node_type not in ontology.node_types:
        new_schema = {key: infer_type(value) for key, value in new_props.items()}
        ontology.add_node_type(node_type, new_schema, required=[])
        print(f"[INFO] Auto-created new node type '{node_type}' with schema: {new_schema}")
    else:
        current_schema = ontology.node_types[node_type]["properties"]
        for key, value in new_props.items():
            if key not in current_schema:
                inferred = infer_type(value)
                current_schema[key] = inferred
                print(f"[INFO] Auto-updating ontology for node type '{node_type}': Adding property '{key}' as {inferred}")

def auto_update_edge_ontology(ontology, edge_type: str, new_props: dict) -> None:
    """
    Auto-update (or create) the edge type in the ontology.
    If the edge type does not exist, create it with the given properties.
    Otherwise, for each key in new_props that is missing in the edge schema,
    infer its type and add it.
    """
    edge_type = edge_type.lower()  # Normalize to lower case
    if edge_type not in ontology.edge_types:
        new_schema = {key: infer_type(value) for key, value in new_props.items()}
        ontology.add_edge_type(edge_type, new_schema, required=[])
        print(f"[INFO] Auto-created new edge type '{edge_type}' with schema: {new_schema}")
    else:
        current_schema = ontology.edge_types[edge_type]["properties"]
        for key, value in new_props.items():
            if key not in current_schema:
                inferred = infer_type(value)
                current_schema[key] = inferred
                print(f"[INFO] Auto-updating ontology for edge type '{edge_type}': Adding property '{key}' as {inferred}")

#############################
# End helper functions
#############################

class NodeProcessor:
    """Processes nodes using extraction rules, LLM integration, and database operations."""

    def __init__(self, llm_integration, db):
        self.llm_integration = llm_integration
        self.db = db  # The database instance is provided separately.
        self.rules_list: List[ExtractionRule] = []

    @property
    def rules(self) -> Dict[str, ExtractionRule]:
        d = {}
        for rule in self.rules_list:
            for target in rule.extractable_types.keys():
                d[target] = rule
        return d

    def register_rule(self, rule: ExtractionRule) -> None:
        if not isinstance(rule, ExtractionRule):
            raise TypeError("Rule must be an ExtractionRule instance")
        self.rules_list.append(rule)
        print("[DEBUG] Registered extraction rule for types:", list(rule.extractable_types.keys()))

    def _check_conditions(self, properties: Dict[str, Any], conditions: Optional[Dict[str, Any]]) -> bool:
        if not conditions:
            return True
        if conditions.get("always", False):
            return True
        return all(properties.get(k) == v for k, v in conditions.items())

    def _find_node_by_name(self, name: str, expected_label: Optional[str] = None) -> Optional[str]:
        """Helper method to search self.db.nodes for a node with a matching 'name' property."""
        for node_id, node in self.db.nodes.items():
            if expected_label is not None and node["label"] != expected_label:
                continue
            if node["properties"].get("name") == name:
                return node_id
        return None

    def _handle_multi_node_extraction(
        self,
        node_id: str,
        source_label: str,
        node_data: Dict[str, Any],
        extracted: Dict[str, Any],
        triggered_targets: Dict[str, NodePropertyRule]
    ) -> None:
        # Ensure the source node exists.
        if node_id not in self.db.nodes:
            self.db.nodes[node_id] = {
                "label": source_label,
                "properties": node_data.get("properties", {})
            }
            print(f"[DEBUG] Created source node {node_id} as part of multi-node extraction.")
        else:
            print(f"[DEBUG] Using existing source node {node_id} for multi-node extraction.")

        # Build a mapping for lookup:
        node_map = {}
        node_map["node_1"] = node_id
        if "name" in node_data.get("properties", {}):
            node_map[node_data["properties"]["name"]] = node_id

        next_node_idx = 2
        for node in extracted.get("nodes", []):
            if not isinstance(node, dict):
                print(f"[DEBUG] Skipping node not in dict format: {node}")
                continue

            # If the extracted label is not among expected types, default it.
            if node["label"] not in triggered_targets:
                default_label = "person" if "person" in triggered_targets else list(triggered_targets.keys())[0]
                print(f"[DEBUG] Extracted node label '{node['label']}' not in expected targets {list(triggered_targets.keys())}, defaulting to '{default_label}'.")
                node["label"] = default_label

            # Prepare (and possibly filter) the properties for this node.
            target_rule = triggered_targets.get(node["label"])
            if target_rule and target_rule.target_schema:
                allowed_keys = set(target_rule.target_schema.keys())
                filtered_props = {k: v for k, v in node.get("properties", {}).items() if k in allowed_keys}
                # If the target schema includes an "embedding" field and it is missing but we have a "name", auto‐compute it.
                if "embedding" in target_rule.target_schema and "embedding" not in filtered_props and "name" in filtered_props:
                    filtered_props["embedding"] = self.llm_integration.get_embedding(filtered_props["name"])
                node_props = filtered_props
            else:
                node_props = node.get("properties", {})

            # Auto-update the ontology for this node type
            auto_update_node_ontology(self.db.ontology, node["label"], node_props)

            # If the extracted node has the same label as the source node, check if we can update the source instead of creating a duplicate.
            if node["label"] == source_label:
                source_props = node_data.get("properties", {})
                extracted_name = node_props.get("name")
                if extracted_name is not None and "name" not in source_props:
                    self.db.update_node(node_id, node_props)
                    print(f"[DEBUG] Updated source node {node_id} with extracted properties: {node_props}")
                    continue
                elif extracted_name is not None and source_props.get("name") == extracted_name:
                    print(f"[DEBUG] Skipping extracted node with label same as source: {node}")
                    continue

            new_id = self.db.create_node(node["label"], node_props)
            key = f"node_{next_node_idx}"
            node_map[key] = new_id
            if "name" in node_props:
                node_map[node_props["name"]] = new_id
            print(f"[DEBUG] Created new node {new_id} of type '{node['label']}' with properties: {node_props}")
            next_node_idx += 1

        # Process relationships.
        for rel in extracted.get("relationships", []):
            if not isinstance(rel, dict):
                print(f"[DEBUG] Skipping relationship because it is not a dict: {rel}")
                continue
            # Normalize relationship type to lower case.
            rel_type_lower = rel["type"].lower()
            valid_types_lower = [rt.lower() for rt in (self.rules_list[0].relationship_types or [])]
            if valid_types_lower and rel_type_lower not in valid_types_lower:
                raise ValueError(f"Invalid relationship type: {rel['type']}")
            # Auto-update the ontology for the edge type.
            auto_update_edge_ontology(self.db.ontology, rel_type_lower, rel.get("properties", {}))
            # Attempt to look up node IDs for the relationship endpoints.
            from_key = rel["from"]
            to_key = rel["to"]
            from_id = node_map.get(from_key)
            if not from_id:
                from_id = self._find_node_by_name(from_key, expected_label="Person")
            to_id = node_map.get(to_key)
            if not to_id:
                to_id = self._find_node_by_name(to_key, expected_label="Company")
            if from_id and to_id:
                self.db.create_edge(from_id=from_id, to_id=to_id, label=rel_type_lower, properties=rel.get("properties", {}))
                print(f"[DEBUG] Created edge from {from_id} to {to_id} of type '{rel_type_lower}'.")
            else:
                print(f"[DEBUG] Could not find node IDs for relationship: from='{from_key}', to='{to_key}'.")

    def _handle_single_node_update(
        self,
        node_id: str,
        node_type: str,
        node_data: Dict[str, Any],
        extracted_props: Dict[str, Any],
        node_rule: NodePropertyRule
    ) -> None:
        # Auto-update the ontology for the node type
        auto_update_node_ontology(self.db.ontology, node_type, extracted_props)

        final_props = {}
        if not node_rule.overwrite_existing:
            final_props.update(node_data.get("properties", {}))
        if node_rule.extract_params:
            final_props.update({ k: v for k, v in extracted_props.items() if k in node_rule.extract_params })
            print(f"[DEBUG] (Update) Using extract_params; final properties: {final_props}")
        elif node_rule.target_schema:
            final_props.update({ k: v for k, v in extracted_props.items() if k in node_rule.target_schema })
            print(f"[DEBUG] (Update) Using target_schema; final properties: {final_props}")
        else:
            final_props.update(extracted_props)
            print(f"[DEBUG] (Update) Using full extracted properties; final properties: {final_props}")
        if node_id not in self.db.nodes:
            new_id = self.db.create_node(node_type, final_props)
            self.db.nodes[node_id] = {"label": node_type, "properties": final_props}
            print(f"[DEBUG] Created new node {new_id} for update.")
        else:
            self.db.update_node(node_id, final_props)
            print(f"[DEBUG] Updated existing node {node_id} with properties: {final_props}")

    def _validate_node_type(self, node_data: Dict[str, Any]) -> str:
        if not node_data.get("label"):
            raise InvalidNodeTypeError("Node data missing label", {})
        return node_data["label"]

    def _get_node_content(self, node_data: Dict[str, Any]) -> str:
        content_props = ["content", "text", "description"]
        content = " ".join(
            str(node_data["properties"].get(prop, ""))
            for prop in content_props
            if prop in node_data["properties"]
        )
        print(f"[DEBUG] Extracted content for node: {content}")
        return content

    def process_node(self, node_id: str, node_data: Dict[str, Any]) -> None:
        content = self._get_node_content(node_data)
        if not content:
            print(f"[DEBUG] Node {node_id} has no content to process.")
            return

        print(f"[DEBUG] Processing node {node_id} with content: {content}")

        # For simplicity, use the first registered rule.
        rule = self.rules_list[0]
        triggered_targets = {}
        for target_type, node_rule in rule.extractable_types.items():
            if self._check_conditions(node_data.get("properties", {}), node_rule.conditions):
                triggered_targets[target_type] = node_rule
        print(f"[DEBUG] Triggered target types for node {node_id}: {list(triggered_targets.keys())}")

        if not triggered_targets:
            print(f"[DEBUG] No extraction targets triggered for node {node_id}.")
            return

        # Merge all target schemas.
        merged_schema = {}
        for node_rule in triggered_targets.values():
            if node_rule.target_schema:
                merged_schema.update(node_rule.target_schema)
        print(f"[DEBUG] Merged target schema for node {node_id}: {merged_schema}")

        # Force multi-node extraction if more than one target type is triggered.
        if len(triggered_targets) > 1:
            valid_labels = list(triggered_targets.keys())
            # Load allowed relationship types from the ontology if available.
            if self.db.ontology and hasattr(self.db.ontology, "edge_types") and self.db.ontology.edge_types:
                allowed_relationships = [r.lower() for r in self.db.ontology.edge_types.keys()]
            else:
                allowed_relationships = []
            forced_schema = {
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "enum": valid_labels},
                                "properties": {"type": "object"}
                            },
                            "required": ["label", "properties"]
                        }
                    },
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"},
                                "type": {"type": "string", "enum": allowed_relationships} if allowed_relationships else {"type": "string"},
                                "properties": {"type": "object"}
                            },
                            "required": ["from", "to", "type"]
                        }
                    }
                },
                "required": ["nodes", "relationships"]
            }
            print(f"[DEBUG] Forcing multi-node extraction schema for node {node_id}: {forced_schema}")
            output_schema = forced_schema
        else:
            output_schema = merged_schema

        # Call the LLM using the (possibly forced) output schema.
        extracted = self.llm_integration.call_structured(
            prompt=content,
            output_schema=output_schema
        )
        print(f"[DEBUG] LLM extraction result for node {node_id}: {extracted}")
        if isinstance(extracted, dict):
            print(f"[DEBUG] LLM extraction keys: {list(extracted.keys())}")
        else:
            print("[DEBUG] LLM extraction result is not a dictionary.")

        if not isinstance(extracted, dict):
            print(f"[DEBUG] Extraction result for node {node_id} is not a dict; skipping update.")
            return

        if "nodes" in extracted:
            print(f"[DEBUG] Detected multi-node extraction output for node {node_id}.")
            self._handle_multi_node_extraction(node_id, self._validate_node_type(node_data), node_data, extracted, triggered_targets)
        else:
            print(f"[DEBUG] Detected single-node extraction output for node {node_id}.")
            source_label = self._validate_node_type(node_data)
            if source_label in triggered_targets:
                self._handle_single_node_update(node_id, source_label, node_data, extracted, triggered_targets[source_label])
