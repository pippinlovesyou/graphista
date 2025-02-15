"""
llm_smart_node_processor.py

A smarter node processor that deduplicates and updates nodes.
It pre-chunks long node content and processes each chunk sequentially.
At each chunk, the LLM is prompted (using a chain‐of‑thought loop) to decide whether the information 
duplicates an existing node (by delegating duplicate detection to the provided tool 'find_similar_nodes'),
should update an existing node, or if a new node should be created. In addition, batch add/update tools
are provided. The final output is a JSON summary of all node/edge actions performed.
"""

import time
import json
from typing import Any, Dict, List, Callable, Optional
import logging
from difflib import SequenceMatcher
from graphrouter.query import Query
from graphrouter.ontology import format_ontology

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SmartNodeProcessor:
    def __init__(
        self,
        llm_client: Any,
        db: Any,
        ontology: Any,
        max_iterations: int = 20,
        max_chunk_tokens: int = 500,
        fuzzy_threshold: float = 0.8
    ):
        self.llm_client = llm_client
        self.db = db
        self.ontology = ontology
        self.max_iterations = max_iterations
        self.max_chunk_tokens = max_chunk_tokens
        self.fuzzy_threshold = fuzzy_threshold

        # Caches to track created/updated nodes and edges.
        self.created_nodes: Dict[str, str] = {}       # keyed by node name
        self.updated_nodes: Dict[str, Dict[str, Any]] = {}  # keyed by node id
        self.created_edges: Dict[str, str] = {}         # composite key: "fromID-edgeType-toID"

        # Build a toolset including retrieval/update, batch, and duplicate-finding tools.
        self.tools: Dict[str, Callable] = {
            "query": self.db.query,
            "vector_search": self._vector_search,
            "get_node": self.db.get_node,
            "get_edges": self.db.get_edges_of_node,
            "get_connected_nodes": self.db.get_connected_nodes,
            "get_node_by_property": self.db.get_node_by_property,
            "get_nodes_with_property": self.db.get_nodes_with_property,
            "update_node": self._update_node_wrapper,
            "create_node": self._create_node_wrapper,
            "create_edge": self._create_edge_wrapper,
            "batch_create_nodes": self._batch_create_nodes_wrapper,
            "batch_update_nodes": self._batch_update_nodes_wrapper,
            "batch_create_edges": self._batch_create_edges_wrapper,
            "find_similar_nodes": self._find_similar_nodes_tool,
            "token_count": self.token_count,
            "chunk_text": self.chunk_text
        }

        # Updated system description and prompt instructions.
        self.system_description = (
            "You are a smart node deduplication assistant with access to a graph database. Your goal is to process "
            "incoming text (typically from a document) and decide whether to create new nodes, update existing nodes, "
            "or add edges between nodes. All decisions regarding fuzzy matching and vector similarity (to determine duplicates) "
            "should be delegated to you via the tool 'find_similar_nodes'.\n\n"
            "Available tools:\n"
            "  - create_node: expects a JSON object with keys \"label\" and \"properties\". Use this to create a new node.\n"
            "  - update_node: expects a JSON object with keys \"node_id\" and \"properties\". Use this to update an existing node; include ALL updated properties (do not leave fields empty).\n"
            "  - get_node_by_property: expects a JSON object with keys \"property_name\" and \"value\".\n"
            "  - create_edge: expects a JSON object with keys \"from_node\", \"to_node\", and \"edge_type\" (optionally \"properties\"). IMPORTANT: Use node IDs, not names.\n"
            "  - batch_create_nodes: expects a JSON object with key \"nodes\", a list of node objects (each with \"label\" and \"properties\").\n"
            "  - batch_update_nodes: expects a JSON object with key \"updates\", a list of update objects (each with \"node_id\" and \"properties\").\n"
            "  - batch_create_edges: expects a JSON object with key \"edges\", a list of edge objects (each with \"from_id\", \"to_id\", \"label\", and \"properties\").\n"
            "  - vector_search: expects a JSON object with keys such as \"embedding_field\", \"query_text\", \"k\", etc. Do not include any key named \"embedding\".\n"
            "  - find_similar_nodes: expects a JSON object with keys \"label\", \"target_name\", and optionally \"query_vector\". Returns a list of candidate nodes with keys \"node_id\", \"name\", \"fuzzy_score\", and (if applicable) \"vector_score\".\n\n"
            "Always use node IDs (not names) when specifying edge endpoints. If a node already exists (as indicated by find_similar_nodes), "
            "update it rather than creating a duplicate. When updating, ensure that all properties that should be changed (including corrections) are included in the update.\n\n"
            "Ensure your JSON output contains no extra keys."
        )
        logger.debug("SmartNodeProcessor initialized.")

    def token_count(self, text: str) -> int:
        return len(text.split())

    def chunk_text(self, text: str, max_tokens: Optional[int] = None) -> List[str]:
        if max_tokens is None:
            max_tokens = self.max_chunk_tokens
        words = text.split()
        chunks = []
        current_chunk = []
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= max_tokens:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    def _vector_search(self, embedding_field: str, query_text: str, k: int = 10, min_score: float = None) -> Any:
        query_vector = self.llm_client.get_embedding(query_text)
        q = Query()
        q.vector_nearest(embedding_field, query_vector, k, min_score)
        logger.debug(f"Vector search query built with field: {embedding_field}, query_text: {query_text}")
        return self.db.query(q)

    def _fuzzy_match(self, s1: str, s2: str) -> float:
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    def _find_similar_nodes_tool(self, label: str, target_name: str, query_vector: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """
        Tool: find_similar_nodes.
        Returns a list of candidate nodes with keys:
          - node_id, name, fuzzy_score, and optionally vector_score.
        """
        candidates = []
        for node_id, node in self.db.nodes.items():
            if node.get("label", "").lower() == label.lower():
                existing_name = node.get("properties", {}).get("name", "")
                score = self._fuzzy_match(existing_name, target_name)
                candidates.append({
                    "node_id": node_id,
                    "name": existing_name,
                    "fuzzy_score": score
                })
        if query_vector:
            q = Query()
            q.vector_nearest("embedding", query_vector, k=5, min_score=0)
            vector_results = self.db.query(q)
            for res in vector_results:
                if res.get("label", "").lower() == label.lower():
                    existing_name = res.get("properties", {}).get("name", "")
                    # Here, you might compute a dedicated vector similarity score.
                    v_score = self._fuzzy_match(existing_name, target_name)  # For simplicity, using fuzzy match here.
                    candidates.append({
                        "node_id": res.get("id"),
                        "name": existing_name,
                        "vector_score": v_score
                    })
        return candidates

    def _sanitize_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in properties.items() if k != "embedding"}

    def _filter_properties(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        allowed = self.ontology.node_types[label]["properties"].keys()
        return {k: v for k, v in properties.items() if k in allowed and k != "embedding"}

    def _update_node_wrapper(self, node_id: str, properties: Dict[str, Any]) -> bool:
        existing = self.db.get_node(node_id)
        if not existing:
            raise ValueError(f"Node {node_id} does not exist.")
        merged = existing.get("properties", {}).copy()
        merged.update(properties)
        filtered = self._filter_properties(existing["label"], merged)
        success = self.db.update_node(node_id, filtered)
        if success:
            updated_node = self.db.get_node(node_id)
            sanitized = self._sanitize_properties(updated_node.get("properties", {}))
            self.updated_nodes[node_id] = {"label": updated_node.get("label"), "properties": sanitized}
            logger.debug(f"Updated node {node_id} with properties: {sanitized}")
        return success

    def _create_node_wrapper(self, label: str, properties: Dict[str, Any]) -> str:
        # Remove any internal fuzzy matching; rely on the LLM to call find_similar_nodes.
        filtered_properties = self._filter_properties(label, properties)
        new_node_id = self.db.create_node(label, filtered_properties)
        logger.debug(f"Created new node '{label}' with ID: {new_node_id} and properties: {self._sanitize_properties(filtered_properties)}")
        if "name" in filtered_properties:
            self.created_nodes[filtered_properties["name"]] = new_node_id
        return new_node_id

    def _create_edge_wrapper(self, edge_type: str, from_node: str, to_node: str, properties: Optional[Dict[str, Any]] = None) -> str:
        if properties is None:
            properties = {}
        new_edge_id = self.db.create_edge(from_node, to_node, edge_type, properties)
        composite_key = f"{from_node}-{edge_type}-{to_node}"
        self.created_edges[composite_key] = new_edge_id
        logger.debug(f"Created edge '{edge_type}' from {from_node} to {to_node} with ID: {new_edge_id}")
        return new_edge_id

    def _batch_create_nodes_wrapper(self, nodes: List[Dict[str, Any]]) -> List[str]:
        prepared_nodes = []
        for node in nodes:
            label = node.get("label")
            props = self._filter_properties(label, node.get("properties", {}))
            prepared_nodes.append({"label": label, "properties": props})
        node_ids = self.db.batch_create_nodes(prepared_nodes)
        for nid in node_ids:
            node = self.db.get_node(nid)
            if node and "name" in node.get("properties", {}):
                self.created_nodes[node["properties"]["name"]] = nid
        logger.debug(f"Batch created nodes: {node_ids}")
        return node_ids

    def _batch_update_nodes_wrapper(self, updates: Any) -> List[bool]:
        results = []
        if isinstance(updates, list):
            for update in updates:
                if not isinstance(update, dict):
                    raise ValueError("Each update must be a dictionary.")
                node_id = update.get("node_id")
                if not node_id:
                    raise ValueError("Each update dictionary must include a 'node_id'.")
                props = self._filter_properties(self.db.get_node(node_id)["label"], update.get("properties", {}))
                result = self.db.update_node(node_id, props)
                if result:
                    updated_node = self.db.get_node(node_id)
                    self.updated_nodes[node_id] = {"label": updated_node.get("label"), "properties": self._sanitize_properties(updated_node.get("properties", {}))}
                results.append(result)
        elif isinstance(updates, dict):
            node_id = updates.get("node_id")
            props = self._filter_properties(self.db.get_node(node_id)["label"], updates.get("properties", {}))
            results.append(self.db.update_node(node_id, props))
        else:
            raise ValueError("Invalid type for batch_update_nodes input; expected a dict or a list of dicts.")
        logger.debug(f"Batch update results: {results}")
        return results

    def _batch_create_edges_wrapper(self, edges: List[Dict[str, Any]]) -> List[str]:
        edge_ids = self.db.batch_create_edges(edges)
        logger.debug(f"Batch created edges: {edge_ids}")
        return edge_ids

    def _fix_tool_params(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "vector_search" and "embedding" in params:
            del params["embedding"]
        if tool == "create_edge":
            allowed_keys = {"from_node", "to_node", "edge_type", "properties"}
            params = {k: v for k, v in params.items() if k in allowed_keys}
            # Convert names to node IDs if needed.
            for key in ["from_node", "to_node"]:
                if key in params and isinstance(params[key], str):
                    candidate = params[key]
                    if candidate not in self.db.nodes:
                        found_id = None
                        for nid, node in self.db.nodes.items():
                            if node.get("properties", {}).get("name") == candidate:
                                found_id = nid
                                break
                        if found_id:
                            params[key] = found_id
                        else:
                            raise ValueError(f"Node with name {candidate} not found.")
        if tool in {"batch_update_nodes"}:
            # Ensure that if the LLM returns a list, we accept it.
            if isinstance(params, list):
                return {"updates": params}
        return params

    def _parse_action_input(self, action_input: str, tool: Optional[str] = None) -> Dict[str, Any]:
        if isinstance(action_input, dict):
            parsed = action_input
        else:
            if not action_input.strip():
                return {}
            try:
                parsed = json.loads(action_input)
            except Exception as e:
                error_msg = f"Failed to parse action_input: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        if tool is not None:
            parsed = self._fix_tool_params(tool, parsed)
        logger.debug(f"Parsed action_input for tool '{tool}': {parsed}")
        return parsed

    def _build_prompt(self, node_id: str, node_data: Dict[str, Any], current_context: str, chain: List[str]) -> str:
        chain_text = ("Previous Chain-of-Thought:\n" + "\n".join(chain) + "\n\n") if chain else ""
        ontology_summary = format_ontology(self.ontology)
        content = node_data.get("properties", {}).get("content", "")
        created_nodes_text = ""
        if self.created_nodes:
            sanitized_nodes = ", ".join(f"{name}: {nid}" for name, nid in self.created_nodes.items())
            created_nodes_text = "Previously created nodes: " + sanitized_nodes + "\n\n"
        updated_nodes_text = ""
        if self.updated_nodes:
            sanitized_updates = ", ".join(f"{nid}: {node['properties']}" for nid, node in self.updated_nodes.items())
            updated_nodes_text = "Previously updated nodes: " + sanitized_updates + "\n\n"
        created_edges_text = ""
        if self.created_edges:
            sanitized_edges = ", ".join(f"{key}: {eid}" for key, eid in self.created_edges.items())
            created_edges_text = "Previously created edges: " + sanitized_edges + "\n\n"
        tool_instructions = (
            "When using tools, please use exactly the following keys in your JSON output:\n"
            " - create_node: use keys \"label\" and \"properties\".\n"
            " - update_node: use keys \"node_id\" and \"properties\".\n"
            " - get_node_by_property: use keys \"property_name\" and \"value\".\n"
            " - create_edge: use unique node IDs for \"from_node\" and \"to_node\", and key \"edge_type\" (optionally \"properties\").\n"
            " - batch_create_nodes: return an object with key \"nodes\" mapping to a list of node objects (each with \"label\" and \"properties\").\n"
            " - batch_update_nodes: return an object with key \"updates\" mapping to a list of update objects (each with \"node_id\" and \"properties\").\n"
            " - batch_create_edges: return an object with key \"edges\" mapping to a list of edge objects (each with \"from_id\", \"to_id\", \"label\", and \"properties\").\n"
            " - vector_search: do not include any key named \"embedding\".\n"
            " - find_similar_nodes: return a list of candidate node objects with keys \"node_id\", \"name\", and similarity scores.\n\n"
        )
        prompt = (
            f"You are a smart node deduplication assistant with access to a graph database.\n"
            f"Your objective is to process the provided text and decide if new nodes or updates are required.\n"
            f"Delegate all duplicate and fuzzy matching decisions to the tool 'find_similar_nodes'.\n"
            f"Always use node IDs (not names) when creating or updating edges.\n\n"
            f"System Description: {self.system_description}\n\n"
            f"Ontology Summary:\n{ontology_summary}\n\n"
            f"Node ID: {node_id}\n"
            f"Current Chunk Content: {content}\n"
            f"Context from previous chunks: {current_context}\n\n"
            f"{chain_text}"
            f"{created_nodes_text}"
            f"{updated_nodes_text}"
            f"{created_edges_text}"
            f"{tool_instructions}"
            f"Available tools:\n"
            f"  - query, vector_search, get_node, get_edges, get_connected_nodes, get_node_by_property, "
            f"get_nodes_with_property, update_node, create_node, create_edge, batch_create_nodes, batch_update_nodes, "
            f"batch_create_edges, find_similar_nodes, token_count, chunk_text.\n\n"
            f"**IMPORTANT:** If no further actions are needed, output an action of 'finish' with your final summary.\n\n"
            f"Respond with a JSON object with keys:\n"
            f"  - \"thought\": your reasoning,\n"
            f"  - \"action\": the tool name,\n"
            f"  - \"action_input\": a JSON string of parameters,\n"
            f"  - \"final_actions\": summary if finishing.\n"
            f"Ensure valid JSON."
        )
        return prompt

    def _run_single_chunk(
        self,
        node_id: str,
        chunk_node_data: Dict[str, Any],
        current_context: str,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        chain_of_thought: List[str] = []
        final_actions = None
        updated_node_id: Optional[str] = None

        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration+1} (single chunk) with context:\n{current_context}")
            prompt = self._build_prompt(node_id, chunk_node_data, current_context, chain_of_thought)
            try:
                response = self.llm_client.call_structured(
                    prompt,
                    output_schema={
                        "thought": "string",
                        "action": "string",
                        "action_input": "string",
                        "final_actions": "string"
                    }
                )
            except Exception as e:
                error_msg = f"Iteration {iteration+1}: LLM call failed: {str(e)}"
                logger.error(error_msg)
                chain_of_thought.append(error_msg)
                return {"final_actions": error_msg, "chain_of_thought": chain_of_thought, "updated_node_id": updated_node_id}

            logger.debug(f"Raw LLM response (chunk): {json.dumps(response)}")
            thought = response.get("thought", "")
            action = response.get("action", "").lower()
            action_input = response.get("action_input", "")
            final_actions = response.get("final_actions", "")

            if action == "finish":
                chain_entry = f"Iteration {iteration+1}: Thought: {thought}, Action: {action}, Action Input: {action_input}, Final Actions: {final_actions}"
                chain_of_thought.append(chain_entry)
                if update_callback:
                    update_callback({"iteration": iteration + 1, "chain_of_thought": chain_of_thought, "current_context": current_context})
                if updated_node_id is None:
                    name = chunk_node_data.get("properties", {}).get("name", "")
                    if name:
                        result = self.db.get_node_by_property("name", name)
                        if result:
                            for nid, node in self.db.nodes.items():
                                if node.get("properties", {}).get("name") == name:
                                    updated_node_id = nid
                                    break
                break
            else:
                try:
                    if action in self.tools:
                        params = self._parse_action_input(action_input, tool=action)
                        tool_result = self.tools[action](**params)
                        if action == "create_node" and isinstance(tool_result, str) and not tool_result.startswith("new_"):
                            updated_node_id = tool_result
                        logger.debug(f"Tool '{action}' returned: {tool_result}")
                    else:
                        tool_result = f"Unknown action '{action}'"
                        logger.warning(tool_result)
                except Exception as ex:
                    tool_result = f"Error executing tool '{action}': {str(ex)}"
                    logger.error(tool_result)
                chain_entry = f"Iteration {iteration+1}: Thought: {thought}, Action: {action}, Action Input: {action_input}, Output: {tool_result}"
                chain_of_thought.append(chain_entry)
                current_context = f"{current_context}\nTool [{action}] result: {tool_result}"
                if iteration > 1 and len(chain_of_thought) >= 2 and chain_of_thought[-1] == chain_of_thought[-2]:
                    logger.debug("Chain-of-thought repeating; forcing early termination.")
                    final_actions = f"Terminated early at iteration {iteration+1} due to repetitive responses."
                    break
            time.sleep(0.1)
        if final_actions is None:
            final_actions = current_context
        return {"final_actions": final_actions, "chain_of_thought": chain_of_thought, "updated_node_id": updated_node_id}

    def run(self, node_id: str, node_data: Dict[str, Any], update_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        logger.debug(f"Starting SmartNodeProcessor run() for node_id: {node_id}")
        content = node_data.get("properties", {}).get("content", "")
        token_cnt = self.token_count(content)
        if token_cnt > self.max_chunk_tokens:
            chunks = self.chunk_text(content)
            logger.debug(f"Content token count {token_cnt} exceeds threshold; split into {len(chunks)} chunks.")
        else:
            chunks = [content]

        overall_actions: List[str] = []
        overall_chain: List[str] = []
        accumulated_context = "No previous actions."

        for idx, chunk in enumerate(chunks):
            chunk_node_data = dict(node_data)
            chunk_node_data["properties"] = dict(node_data.get("properties", {}))
            chunk_node_data["properties"]["content"] = chunk
            current_context = f"Processing chunk {idx+1} of {len(chunks)}. Previous actions: {accumulated_context}"
            result = self._run_single_chunk(node_id, chunk_node_data, current_context, update_callback)
            overall_chain.extend(result["chain_of_thought"])
            overall_actions.append(result["final_actions"])
            if result.get("updated_node_id"):
                node_id = result["updated_node_id"]
            accumulated_context += f"\nChunk {idx+1} actions: {result['final_actions']}"
        final_summary = "\n".join(overall_actions)
        return {"final_actions": final_summary, "chain_of_thought": overall_chain, "updated_node_id": node_id}
