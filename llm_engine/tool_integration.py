"""
tool_integration.py

Higher-level utilities that combine LiteLLM calls with your domain logic.
Examples:
  - Auto-embed new data (with toggle).
  - Use structured LLM extraction to map unstructured data into a specific node or property format.
  - More advanced text → data flows.
"""

from typing import Any, Dict, List, Optional

from graphrouter import GraphDatabase, Query
# from .litellm_client import LiteLLMClient, LiteLLMError  # local import
# or if you prefer an absolute import: from llm_engine.litellm_client import LiteLLMClient, LiteLLMError

class LLMToolIntegration:
    """
    A tool-layer that leverages LiteLLMClient for domain-specific tasks,
    such as automatically embedding new nodes or extracting structured data
    before insertion into your GraphRouter database.
    """

    def __init__(
        self,
        db: GraphDatabase,
        llm_client: "LiteLLMClient", 
        auto_embed: bool = True,
        embed_fields: Optional[List[str]] = None,
        auto_process: bool = True,
        node_processor: Optional["NodeProcessor"] = None
    ):
        """
        Args:
            db (GraphDatabase): Graph database instance
            llm_client (LiteLLMClient): LLM client for structured extraction
            auto_embed (bool): Whether to automatically embed new data
            embed_fields (List[str]): Fields to embed
            auto_process (bool): Whether to automatically process nodes
        """
        """
        Args:
            db (GraphDatabase): An instance of your GraphRouter database (local, Neo4j, etc.).
            llm_client (LiteLLMClient): The LLM client for structured calls / embeddings.
            auto_embed (bool): Whether to automatically embed new data by default.
            embed_fields (List[str]): Which fields to embed if auto_embed is True.
        """
        self.db = db
        self.llm_client = llm_client
        self.auto_embed = auto_embed
        self.embed_fields = embed_fields or ["name", "description", "text"]

    def embed_node_if_needed(self, node_id: str) -> None:
        """
        Example: embed selected fields in a node's properties and store them back to the node.
        This is purely an example; adapt the property naming or logic to your needs.
        """
        if not self.auto_embed:
            return

        node_data = self.db.get_node(node_id)
        if not node_data:
            return

        label = node_data["label"]
        props = node_data["properties"]

        # Collect text fields that exist in the node
        texts_to_embed = []
        for field in self.embed_fields:
            value = props.get(field)
            if value and isinstance(value, str):
                texts_to_embed.append(value)

        # Optionally combine them or embed each separately
        combined_text = " ".join(texts_to_embed)
        if not combined_text.strip():
            return

        try:
            embedding = self.llm_client.get_embedding(combined_text)
            # Store embedding
            # E.g. as "embedding" property, or perhaps in a separate vector store
            # For demonstration, we'll store it on the node. This may not be optimal for large embeddings.
            self.db.update_node(node_id, {"embedding": embedding})
        except Exception as e:
            print(f"[WARN] Failed embedding for node {node_id}: {e}")

    def auto_embed_new_nodes(self, label_filter: Optional[str] = None):
        """
        Query the graph for newly created nodes (some logic needed to track "new")
        or simply retrieve all with a given label, then embed them if needed.
        """
        query = Query()
        if label_filter:
            query.filter(Query.label_equals(label_filter))

        nodes = self.db.query(query)
        for n in nodes:
            # Example: skip if it already has an "embedding" or we have a better "new" check
            if "embedding" in n["properties"]:
                continue
            self.embed_node_if_needed(n["id"])

    def structured_extraction_for_node(
        self,
        text: str,
        schema: Dict[str, Any],
        node_label: str,
        default_properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Example method that calls the LLM for structured extraction from arbitrary text,
        then creates (or updates) a node with those structured properties.

        Args:
            text (str): Unstructured text to parse with LLM
            schema (Dict[str, Any]): Expected schema to parse from text
            node_label (str): Label of the node to create or update
            default_properties (Dict[str, Any]): Any default props to merge in

        Returns:
            str: The ID of the created or updated node
        """
        from llm_engine.litellm_client import LiteLLMError  # local import in method scope

        # 1) Ask LLM to parse the text into structured data
        try:
            structured_data = self.llm_client.call_structured(
                prompt=text,
                output_schema=schema
            )
        except LiteLLMError as e:
            raise ValueError(f"LLM extraction error: {e}")

        # 2) Merge with defaults if provided
        final_props = (default_properties or {}).copy()
        final_props.update(structured_data)

        # 3) Create or update node
        # For demonstration, we'll always create a new node
        # In real usage, you might search for an existing node and update it
        node_id = self.db.create_node(node_label, final_props)

        # 4) Optionally embed
        if self.auto_embed:
            self.embed_node_if_needed(node_id)

        return node_id
