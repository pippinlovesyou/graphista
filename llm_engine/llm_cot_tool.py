import time
import json
from typing import Any, Dict, List, Callable
import logging
from graphrouter.query import Query
from graphrouter.ontology import format_ontology  # helper for formatting

# Set up a logger for this module.
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SmartRetrievalTool:
    def __init__(self, llm_client: Any, db: Any, ontology: Any, max_iterations: int = 20):
        """
        Initialize the Smart Retrieval Tool.

        Args:
            llm_client: An LLM client that implements call_structured(prompt, output_schema) and get_embedding(text).
            db: A graph database instance with full query functions.
            ontology: The Ontology instance.
            max_iterations: Maximum iterations for the chain‑of‑thought loop.
        """
        self.llm_client = llm_client
        self.db = db
        self.ontology = ontology
        self.max_iterations = max_iterations
        # Build a toolset limited to read-only operations.
        self.tools: Dict[str, Callable] = {
            "query": self.db.query,
            "vector_search": self._vector_search,
            "get_node": self.db.get_node,
            "get_edges": self.db.get_edges_of_node,
            "get_connected_nodes": self.db.get_connected_nodes,
            "get_node_by_property": self.db.get_node_by_property,
            "get_nodes_with_property": self.db.get_nodes_with_property
        }
        self.system_description = (
            "The database was gathered by an ingestion engine that automatically embeds every document "
            "and extracts structured nodes using a predefined ontology. "
            "The ontology defines available node types and edge types along with their required properties. "
            "Remember: if a 'works_at' edge is directed from a Person to an Organization, then to find colleagues "
            "you may need to use the 'in' or 'both' direction when retrieving nodes from the Organization."
        )
        logger.debug("SmartRetrievalTool initialized.")

    def _vector_search(self, embedding_field: str, query_text: str, k: int = 10, min_score: float = None) -> Any:
        query_vector = self.llm_client.get_embedding(query_text)
        q = Query()
        q.vector_nearest(embedding_field, query_vector, k, min_score)
        logger.debug(f"Vector search query built with field: {embedding_field}, query_text: {query_text} -> vector: {query_vector}, k: {k}, min_score: {min_score}")
        return self.db.query(q)

    def run(self, question: str, update_callback: Callable[[Dict[str, Any]], None] = None) -> Dict[str, Any]:
        """
        Run the chain‑of‑thought loop.

        Args:
            question: The input question.
            update_callback: Optional callback called after each iteration with the latest update.

        Returns:
            A dict with 'final_answer' and 'chain_of_thought' where each iteration's entry contains:
              "Thought:", "Action:", "Action Input:" and "Output:" (or "Final Answer:" on finish).
        """
        logger.debug(f"Starting run() with question: {question}")
        chain_of_thought: List[str] = []
        current_context = question
        final_output = None
        print("******* MAX ITERATIONS******")
        print(self.max_iterations)
        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration+1} starting. Current context:\n{current_context}")
            prompt = self._build_prompt(current_context, chain_of_thought)
            logger.debug("Prompt built successfully.")
            try:
                response = self.llm_client.call_structured(prompt, output_schema={
                    "thought": "string",
                    "action": "string",
                    "action_input": "string",
                    "final_answer": "string"
                })
            except Exception as e:
                error_msg = f"Iteration {iteration+1}: LLM call failed: {str(e)}"
                logger.error(error_msg)
                chain_of_thought.append(error_msg)
                return {"final_answer": error_msg, "chain_of_thought": chain_of_thought}

            logger.debug(f"Raw LLM response content: {json.dumps(response)}")
            thought = response.get("thought", "")
            action = response.get("action", "").lower()
            action_input = response.get("action_input", "")
            final_answer = response.get("final_answer", "")
            if action == "finish":
                chain_entry = f"Iteration {iteration+1}: Thought: {thought}, Action: {action}, Action Input: {action_input}, Final Answer: {final_answer}"
                chain_of_thought.append(chain_entry)
                if update_callback:
                    update_callback({
                        "iteration": iteration + 1,
                        "chain_of_thought": chain_of_thought,
                        "current_context": current_context
                    })
                final_output = final_answer
                break
            else:
                try:
                    if action == "query":
                        params = self._parse_action_input(action_input)
                        q = Query()
                        if "filters" in params:
                            filters = params["filters"]
                            for key, value in filters.items():
                                if key.lower() == "label":
                                    q.filter(Query.label_equals(value))
                                else:
                                    q.filter(Query.property_equals(key, value))
                        if "sort_key" in params:
                            q.sort(params["sort_key"], reverse=params.get("sort_reverse", False))
                        if "limit" in params:
                            q.limit_results(params["limit"])
                        tool_result = self.db.query(q)
                        logger.debug(f"Query tool returned: {tool_result}")
                    elif action in self.tools:
                        tool_result = self.tools[action](**self._parse_action_input(action_input))
                        logger.debug(f"Tool '{action}' returned: {tool_result}")
                    else:
                        tool_result = f"Unknown action '{action}'"
                        logger.warning(tool_result)
                except Exception as ex:
                    tool_result = f"Error executing tool '{action}': {str(ex)}"
                    logger.error(tool_result)
                chain_entry = f"Iteration {iteration+1}: Thought: {thought}, Action: {action}, Action Input: {action_input}, Output: {tool_result}"
                chain_of_thought.append(chain_entry)
                if update_callback:
                    update_callback({
                        "iteration": iteration + 1,
                        "chain_of_thought": chain_of_thought,
                        "current_context": current_context
                    })
                current_context = f"{current_context}\nTool [{action}] result: {tool_result}"
            time.sleep(0.1)
        if final_output is None:
            final_output = current_context
        return {"final_answer": final_output, "chain_of_thought": chain_of_thought}

    def _build_prompt(self, current_context: str, chain: List[str]) -> str:
        chain_text = ("Previous Chain-of-Thought:\n" + "\n".join(chain) + "\n\n") if chain else ""
        ontology_summary = format_ontology(self.ontology)
        # Improved prompt text with additional instructions for indirect relationships.
        prompt = (
            f"You are a smart retrieval assistant with a strong sense of logic and reasoning, with access to an embedded graph database with embeddings.\n"
            f"Your task is to answer the following question by leveraging all available tools. "
            f"Examine both direct and indirect relationships between nodes. If a direct relationship is not present, "
            f"investigate indirect connections through intermediary nodes. Consider all relevant edge types such as "
            f"'launched', 'acquired', 'affiliated_with', 'knows', etc., and use multiple steps if necessary to uncover "
            f"any indirect relationship.\n\n"
            f"System Description: {self.system_description}\n\n"
            f"{ontology_summary}\n\n"
            f"IMPORTANT: When formulating your queries, use only properties valid for the given node types. "
            f"For example, for a 'Person' node, use only properties such as name, role, age, or embedding; "
            f"and for a 'Company' node, use only properties such as name, industry, or embedding.\n\n"
            f"The following read-only tools are available:\n\n"
            f"1. query:\n"
            f"   Example: {{\"filters\": {{\"label\": \"Person\", \"name\": \"John Doe\"}}}}\n\n"
            f"2. vector_search:\n"
            f"   Example: {{\"embedding_field\": \"embedding\", \"query_text\": \"software engineer\", \"k\": 5}}\n\n"
            f"3. get_node:\n"
            f"   Example: {{\"node_id\": \"abc123\"}}\n\n"
            f"4. get_edges:\n"
            f"   Example: {{\"node_id\": \"abc123\", \"edge_type\": \"friend\"}}\n\n"
            f"5. get_connected_nodes:\n"
            f"   Example: {{\"node_id\": \"abc123\", \"edge_type\": \"friend\", \"direction\": \"both\"}}\n\n"
            f"6. get_node_by_property:\n"
            f"   Example: {{\"property_name\": \"name\", \"value\": \"Alice\"}}\n\n"
            f"7. get_nodes_with_property:\n"
            f"   Example: {{\"property_name\": \"email\"}}\n\n"
            f"Available tool names: \"query\", \"vector_search\", \"get_node\", \"get_edges\", "
            f"\"get_connected_nodes\", \"get_node_by_property\", \"get_nodes_with_property\", and \"finish\" if you are done.\n\n"
            f"Ontology (Summary):\n{ontology_summary}\n\n"
            f"Current Context:\n{current_context}\n\n"
            f"{chain_text}"
            f"Based on the above, decide on your next action. When no direct connection is found, consider exploring "
            f"indirect relationships by continue querying relationships of connected nodes. As you traverse the nodes, consider searching for duplicates of the nodes using searches (such as vector)."
            f"clearly state whether the relationship is direct, indirect, or not present, and explain the reasoning behind it.\n\n"
            f"Respond with a JSON object with keys:\n"
            f"  - \"thought\": your reasoning,\n"
            f"  - \"action\": one of the available tool names,\n"
            f"  - \"action_input\": a JSON string for the chosen tool,\n"
            f"  - \"final_answer\": if finishing, your final answer.\n"
            f"Ensure your response is valid JSON."
        )
        #print(prompt)
        return prompt

    def _parse_action_input(self, action_input: str) -> Dict[str, Any]:
        # If action_input is already a dict, return it as is.
        if isinstance(action_input, dict):
            return action_input

        if not action_input.strip():
            return {}
        try:
            print(action_input)
            parsed = json.loads(action_input)
            logger.debug(f"Parsed action_input: {parsed}")
            return parsed
        except Exception as e:
            error_msg = f"Failed to parse action_input: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
