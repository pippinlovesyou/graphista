"""
llm_engine/litellm_client.py

A utility for calling the litellm library with structured outputs and embeddings,
using litellm.completion(...) for chat completions and litellm.embedding(...) for embeddings.
"""

import json
from typing import Any, Dict, List, Optional, Union

try:
    import litellm
except ImportError:
    litellm = None


class LiteLLMError(Exception):
    """Custom error for LLM-related issues."""
    pass


# If the litellm module does not expose a chat_completion function,
# define one as a thin wrapper around litellm.completion.
if litellm is not None and not hasattr(litellm, "chat_completion"):
    def chat_completion(api_key: Optional[str],
                          messages: List[Dict[str, Any]],
                          model: str,
                          temperature: float,
                          max_tokens: int,
                          **kwargs) -> Dict[str, Any]:
        """
        A wrapper around litellm.completion that uses the OpenAI input/output format.
        It passes along the provided parameters and returns a dictionary with the key "content"
        extracted from the response.
        """
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            **kwargs
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LiteLLMError(f"Unexpected response format from completion: {e}")
        return {"content": content}

    litellm.chat_completion = chat_completion


class LiteLLMClient:
    """
    High-level client that uses:
      - litellm.chat_completion(...) for chat completions
      - litellm.embedding(...) for embeddings
      - Additional error handling for structured JSON outputs.

    This client now leverages strict, detailed prompts and supports converting
    the JSON output into a structured class (e.g., a Pydantic model) if provided.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs
    ):
        """
        Args:
            api_key (str): LLM API key.
            model_name (str): e.g. "gpt-3.5-turbo" or "text-embedding-ada-002".
            temperature (float): Model temperature for chat completions.
            max_tokens (int): Maximum tokens in the completion.
            kwargs: Additional parameters passed to the completion/embedding calls.
        """
        if not litellm:
            raise ImportError("The litellm library is not installed or cannot be imported.")

        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs

    def _serialize_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a schema defined as a dictionary mapping keys to Python types or nested schemas
        into a valid JSON Schema object.

        The output schema will be of type "object" with a "properties" field that maps
        each key to a JSON Schema definition.
        """
        def python_type_to_json_type(py_type):
            if py_type is str:
                return {"type": "string"}
            elif py_type is int:
                return {"type": "integer"}
            elif py_type is float:
                return {"type": "number"}
            elif py_type is bool:
                return {"type": "boolean"}
            elif py_type is dict:
                return {"type": "object"}
            # Fallback to string
            return {"type": "string"}

        properties = {}
        for key, value in schema.items():
            if isinstance(value, type):
                if value == list:
                    if key == "embedding":
                        properties[key] = {"type": "array", "items": {"type": "number"}}
                    else:
                        properties[key] = {"type": "array", "items": {"type": "string"}}
                else:
                    properties[key] = python_type_to_json_type(value)
            elif isinstance(value, dict):
                properties[key] = {
                    "type": "object",
                    "properties": self._serialize_schema(value)["properties"]
                }
            elif isinstance(value, list):
                if len(value) > 0 and isinstance(value[0], type):
                    properties[key] = {"type": "array", "items": python_type_to_json_type(value[0])}
                else:
                    if key == "embedding":
                        properties[key] = {"type": "array", "items": {"type": "number"}}
                    else:
                        properties[key] = {"type": "array", "items": {"type": "string"}}
            else:
                properties[key] = {"type": "string"}
        return {"type": "object", "properties": properties}

    def call_structured(self, prompt: str, output_schema: Union[Dict[str, Any], type]) -> Any:
        """
        Sends a prompt expecting a valid JSON answer. Uses litellm.chat_completion.
        Constructs a system message instructing the LLM to output strictly valid JSON
        that adheres exactly to the provided JSON schema.

        If output_schema is not a dict, it is assumed to be a Pydantic model class,
        and its schema is used.
        """
        # Determine the schema for the prompt.
        if not isinstance(output_schema, dict):
            try:
                from pydantic import BaseModel
            except ImportError:
                raise LiteLLMError("Pydantic must be installed to use model classes for output_schema.")
            if isinstance(output_schema, type) and issubclass(output_schema, BaseModel):
                schema_for_prompt = output_schema.schema()
            else:
                raise ValueError("output_schema must be either a dict or a Pydantic model class.")
        else:
            # If the output_schema already appears to be a complete JSON schema,
            # use it as is.
            if "type" in output_schema and "properties" in output_schema:
                schema_for_prompt = output_schema
                print("[DEBUG] Using provided complete JSON schema without re-serialization.")
            else:
                schema_for_prompt = self._serialize_schema(output_schema)

        system_message = (
            "You are a helpful assistant designed to produce strictly valid JSON output. "
            "Please provide your answer as raw JSON (no extra text, markdown, or commentary) that exactly matches "
            "the following JSON schema:\n"
            f"{json.dumps(schema_for_prompt, indent=2)}\n"
            "Your output must contain all the keys specified in the schema and no additional keys."
        )
        #print("**********************")
        #print(system_message)
        #print("**********************")
        #print(schema_for_prompt)
        #print("**********************")

        try:
            from litellm import supports_response_schema
            custom_provider = self.kwargs.get("custom_llm_provider", "openai")
            if supports_response_schema(model=self.model_name, custom_llm_provider=custom_provider):
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "output",
                        "schema": schema_for_prompt
                    },
                    "strict": True
                }
                if self.model_name.startswith("gpt-"):
                    response_format.pop("strict", None)
            else:
                response_format = {"type": "json_object"}
        except Exception:
            response_format = {"type": "json_object"}

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        try:
            response = litellm.chat_completion(
                api_key=self.api_key,
                messages=messages,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format=response_format,
                **self.kwargs
            )
            content = response["content"]
            print("[DEBUG] Raw LLM response content:", content)
            parsed = json.loads(content)
            if not isinstance(output_schema, dict) and isinstance(output_schema, type):
                return output_schema(**parsed)
            return parsed

        except json.JSONDecodeError as e:
            raise LiteLLMError(f"JSON parse error. Model did not return valid JSON. {e}")
        except Exception as e:
            raise LiteLLMError(f"Error during LLM call: {e}")


    def get_embedding(self, text: str, **kwargs) -> List[float]:
        """
        Retrieves an embedding for the given text using litellm.embedding(...).
        """
        merged_kwargs = {**self.kwargs, **kwargs}
        try:
            response = litellm.embedding(
                input=[text],
                api_key=self.api_key,
                model='text-embedding-ada-002',
                **merged_kwargs
            )
            if hasattr(response, "model_dump"):
                response = response.model_dump()
            elif hasattr(response, "dict"):
                response = response.dict()
            if isinstance(response, list):
                return response
            if isinstance(response, dict) and "data" in response:
                data = response["data"]
                if isinstance(data, list) and len(data) > 0:
                    embedding = data[0].get("embedding")
                    if embedding is not None:
                        return embedding
            raise LiteLLMError("Embedding response did not contain expected 'data' structure.")
        except Exception as e:
            raise LiteLLMError(f"Error retrieving embedding: {e}")
