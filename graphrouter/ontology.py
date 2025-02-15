"""
Ontology management for graph databases.
"""
from typing import Dict, Any, List, Optional
from .errors import InvalidPropertyError, InvalidNodeTypeError

# Mapping from type names (as strings) to actual Python types.
_TYPE_MAPPING = {
    "str": str,
    "string": str,
    "int": int,
    "integer": int,
    "float": float,
    "bool": bool,
    "boolean": bool,
    "list": list,
    "dict": dict
}

def _convert_type(typ: Any) -> Any:
    """Recursively convert a type definition to actual Python types or nested schemas."""
    if isinstance(typ, str):
        return _TYPE_MAPPING.get(typ, str)
    elif isinstance(typ, dict):
        return {k: _convert_type(v) for k, v in typ.items()}
    elif isinstance(typ, list):
        if typ:
            return [_convert_type(typ[0])]
        else:
            return list
    else:
        return typ

class Ontology:
    """Manages the ontology (schema) for the graph database."""

    def __init__(self):
        self.node_types: Dict[str, Dict[str, Any]] = {}
        self.edge_types: Dict[str, Dict[str, Any]] = {}

    def add_node_type(self, label: str, properties: Dict[str, Any], required: List[str] = None):
        """Add a node type to the ontology. Converts property type definitions to actual Python types,
        supporting nested structures.
        """
        new_props = {prop: _convert_type(typ) for prop, typ in properties.items()}
        self.node_types[label] = {
            'properties': new_props,
            'required': required or []
        }

    def add_edge_type(self, label: str, properties: Dict[str, Any], required: List[str] = None):
        """Add an edge type to the ontology. Converts property type definitions to actual Python types,
        supporting nested structures. Edge labels are normalized to lower case.
        """
        label = label.lower()  # Force lower-case for consistency
        new_props = {prop: _convert_type(typ) for prop, typ in properties.items()}
        self.edge_types[label] = {
            'properties': new_props,
            'required': required or []
        }

    def validate_node(self, label: str, properties: Dict[str, Any]) -> bool:
        """Validate a node against the ontology. Raises on invalid data."""
        if label not in self.node_types:
            available_types = list(self.node_types.keys())
            raise InvalidNodeTypeError(
                f"Invalid node type '{label}'. Available types: {', '.join(available_types)}",
                {"available_types": available_types}
            )

        node_type = self.node_types[label]
        expected_schema = node_type['properties']

        # Check that required properties are present
        missing_required = [req for req in node_type['required']
                            if req not in properties or properties[req] == ""]
        if missing_required:
            raise InvalidPropertyError(
                f"Missing required properties for node type '{label}': {', '.join(missing_required)}",
                {"required_properties": node_type['required'],
                 "missing_properties": missing_required,
                 "available_properties": list(expected_schema.keys())}
            )

        # Validate property types
        invalid_props = []
        for prop_name, prop_value in properties.items():
            if prop_name in expected_schema:
                expected_type = expected_schema[prop_name]
                if isinstance(expected_type, list):
                    if not isinstance(prop_value, list):
                        invalid_props.append((prop_name, f"list of {expected_type[0].__name__}", type(prop_value).__name__))
                    else:
                        for item in prop_value:
                            if not isinstance(item, expected_type[0]):
                                invalid_props.append((prop_name, f"list of {expected_type[0].__name__}", type(item).__name__))
                elif isinstance(expected_type, dict):
                    if not isinstance(prop_value, dict):
                        invalid_props.append((prop_name, "dict", type(prop_value).__name__))
                    # (Nested validation could be added here.)
                else:
                    if not isinstance(prop_value, expected_type):
                        invalid_props.append((prop_name, expected_type.__name__, type(prop_value).__name__))
            else:
                raise InvalidPropertyError(
                    f"Unknown property '{prop_name}' for node type '{label}'. Available properties: {', '.join(expected_schema.keys())}",
                    {"available_properties": list(expected_schema.keys())}
                )

        if invalid_props:
            details = []
            for item in invalid_props:
                details.append(f"'{item[0]}' (expected {item[1]}, got {item[2]})")
            raise InvalidPropertyError(
                f"Invalid property types for node type '{label}': {', '.join(details)}",
                {"invalid_properties": {item[0]: item[1] for item in invalid_props},
                 "all_properties": {k: (v.__name__ if not isinstance(v, (list, dict)) else str(v))
                                      for k, v in expected_schema.items()}}
            )

        return True

    def validate_edge(self, label: str, properties: Dict[str, Any]) -> bool:
        """Validate an edge against the ontology. Raises on invalid data."""
        label = label.lower()  # Ensure the label is in lower case
        if label not in self.edge_types:
            available = list(self.edge_types.keys())
            raise InvalidNodeTypeError(
                f"Invalid edge type '{label}'. Available edge types: {', '.join(available)}",
                {"available_types": available}
            )

        edge_type = self.edge_types[label]
        expected_schema = edge_type['properties']

        missing_required = [req for req in edge_type['required']
                            if req not in properties or properties[req] == ""]
        if missing_required:
            raise InvalidPropertyError(
                f"Missing required properties for edge type '{label}': {', '.join(missing_required)}",
                {"required_properties": edge_type['required'],
                 "missing_properties": missing_required,
                 "available_properties": list(expected_schema.keys())}
            )

        invalid_props = []
        for prop_name, prop_value in properties.items():
            if prop_name in expected_schema:
                expected_type = expected_schema[prop_name]
                if isinstance(expected_type, list):
                    if not isinstance(prop_value, list):
                        invalid_props.append((prop_name, f"list of {expected_type[0].__name__}", type(prop_value).__name__))
                    else:
                        for item in prop_value:
                            if not isinstance(item, expected_type[0]):
                                invalid_props.append((prop_name, f"list of {expected_type[0].__name__}", type(item).__name__))
                elif isinstance(expected_type, dict):
                    if not isinstance(prop_value, dict):
                        invalid_props.append((prop_name, "dict", type(prop_value).__name__))
                else:
                    if not isinstance(prop_value, expected_type):
                        invalid_props.append((prop_name, expected_type.__name__, type(prop_value).__name__))
            else:
                raise InvalidPropertyError(
                    f"Unknown property '{prop_name}' for edge type '{label}'. Available properties: {', '.join(expected_schema.keys())}",
                    {"available_properties": list(expected_schema.keys())}
                )

        if invalid_props:
            details = []
            for item in invalid_props:
                details.append(f"'{item[0]}' (expected {item[1]}, got {item[2]})")
            raise InvalidPropertyError(
                f"Invalid property types for edge type '{label}': {', '.join(details)}",
                {"invalid_properties": {item[0]: item[1] for item in invalid_props},
                 "all_properties": {k: (v.__name__ if not isinstance(v, (list, dict)) else str(v))
                                      for k, v in expected_schema.items()}}
            )

        return True

    def to_dict(self) -> Dict:
        """Convert the ontology to a dictionary.
        Note: Python types are converted to their type names.
        """
        def serialize_props(props: Dict[str, Any]) -> Dict[str, str]:
            def type_to_str(typ):
                if isinstance(typ, list):
                    return f"List[{typ[0].__name__}]"
                elif isinstance(typ, dict):
                    return "{" + ", ".join(f"{k}: {type_to_str(v)}" for k, v in typ.items()) + "}"
                else:
                    return typ.__name__
            return {k: type_to_str(v) for k, v in props.items()}

        return {
            'node_types': {label: {'properties': serialize_props(spec['properties']),
                                    'required': spec['required']}
                           for label, spec in self.node_types.items()},
            'edge_types': {label: {'properties': serialize_props(spec['properties']),
                                    'required': spec['required']}
                           for label, spec in self.edge_types.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Ontology':
        """Create an ontology from a dictionary."""
        ontology = cls()
        def parse_props(props: Dict[str, Any]) -> Dict[str, Any]:
            new_props = {}
            for k, v in props.items():
                if isinstance(v, dict) and "type" in v:
                    new_props[k] = _TYPE_MAPPING.get(v["type"], str)
                elif isinstance(v, str):
                    new_props[k] = _TYPE_MAPPING.get(v, str)
                else:
                    new_props[k] = v
            return new_props

        ontology.node_types = {
            label: {'properties': parse_props(spec.get('properties', {})),
                    'required': spec.get('required', [])}
            for label, spec in data.get('node_types', {}).items()
        }
        # Force edge type keys to lower-case.
        ontology.edge_types = {
            label.lower(): {'properties': parse_props(spec.get('properties', {})),
                             'required': spec.get('required', [])}
            for label, spec in data.get('edge_types', {}).items()
        }
        return ontology

    def map_node_properties(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Map properties to match ontology schema for a node type.
        Converts values using the stored Python types.
        """
        if label not in self.node_types:
            return properties

        schema = self.node_types[label]['properties']
        mapped = {}
        for prop, value in properties.items():
            if prop in schema:
                try:
                    mapped[prop] = schema[prop](value) if not isinstance(schema[prop], dict) else value
                except (ValueError, TypeError):
                    mapped[prop] = value
            else:
                mapped[prop] = value
        return mapped

    def map_edge_properties(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Map properties to match ontology schema for an edge type.
        Converts values using the stored Python types.
        """
        label = label.lower()
        if label not in self.edge_types:
            return properties

        schema = self.edge_types[label]['properties']
        mapped = {}
        for prop, value in properties.items():
            if prop in schema:
                try:
                    mapped[prop] = schema[prop](value) if not isinstance(schema[prop], dict) else value
                except (ValueError, TypeError):
                    mapped[prop] = value
            else:
                mapped[prop] = value
        return mapped

def format_ontology(ontology: Ontology) -> str:
    """
    Return a human-readable summary of the ontology.
    """
    summary_lines = []
    summary_lines.append("Ontology Summary:")
    summary_lines.append("Node Types:")
    for label, spec in ontology.node_types.items():
        properties = spec.get("properties", {})
        required = spec.get("required", [])
        prop_list = []
        for prop, typ in properties.items():
            # typ may be a type, list, or dict; convert accordingly.
            if isinstance(typ, type):
                type_name = typ.__name__
            elif isinstance(typ, list) and typ:
                type_name = f"List[{typ[0].__name__}]"
            elif isinstance(typ, dict):
                # For nested dict, show as key: type
                nested = ", ".join(f"{k}: {v.__name__ if isinstance(v, type) else str(v)}" for k, v in typ.items())
                type_name = "{" + nested + "}"
            else:
                type_name = str(typ)
            prop_list.append(f"{prop} ({type_name})")
        summary_lines.append(f"  - {label}: properties = {{{', '.join(prop_list)}}}, required = {required}")
    summary_lines.append("Edge Types:")
    for label, spec in ontology.edge_types.items():
        properties = spec.get("properties", {})
        required = spec.get("required", [])
        prop_list = []
        for prop, typ in properties.items():
            if isinstance(typ, type):
                type_name = typ.__name__
            elif isinstance(typ, list) and typ:
                type_name = f"List[{typ[0].__name__}]"
            elif isinstance(typ, dict):
                nested = ", ".join(f"{k}: {v.__name__ if isinstance(v, type) else str(v)}" for k, v in typ.items())
                type_name = "{" + nested + "}"
            else:
                type_name = str(typ)
            prop_list.append(f"{prop} ({type_name})")
        summary_lines.append(f"  - {label}: properties = {{{', '.join(prop_list)}}}, required = {required}")
    return "\n".join(summary_lines)
