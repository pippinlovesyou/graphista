"""
test_litellm_client.py

Tests for LiteLLMClient in litellm_client.py,
including both mock-based unit tests and optional integration tests.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
import os
from llm_engine.litellm_client import LiteLLMClient

from llm_engine.litellm_client import LiteLLMClient, LiteLLMError

##############################################################################
# Optional fixture for real integration tests
##############################################################################
@pytest.fixture(scope="session")
def openai_api_key():
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GH_OPENAI_API_KEY")
    if not key:
        pytest.skip("No OpenAI API key found, skipping real integration tests.")
    return key

@pytest.fixture(autouse=True)
def cleanup_litellm():
    """Automatically cleanup any LiteLLM state before and after each test"""
    # Setup
    if 'litellm' in globals():
        import litellm
        litellm.cache = {}  # Reset any internal caching
        litellm._async_embedding = None
        litellm._async_completion = None

    yield  # Run the test

    # Teardown
    if 'litellm' in globals():
        import litellm
        litellm.cache = {}  # Reset again after test
        litellm._async_embedding = None
        litellm._async_completion = None


##############################################################################
# Mock-based (unit) Tests
##############################################################################

@patch("llm_engine.litellm_client.litellm.chat_completion", autospec=True)
def test_call_structured_valid_json(mock_chat):
    """
    Test call_structured with valid JSON returned by mocked chat_completion.
    """
    # Mock the response from chat_completion
    mock_chat.return_value = {"content": json.dumps({"title": "Hello", "score": 42})}

    client = LiteLLMClient(api_key="FAKE_KEY")
    schema = {"title": "string", "score": "number"}

    prompt = "Give me a JSON with title and score."
    result = client.call_structured(prompt, schema)
    assert result == {"title": "Hello", "score": 42}


@patch("llm_engine.litellm_client.litellm.chat_completion", autospec=True)
def test_call_structured_invalid_json(mock_chat):
    """
    Test call_structured raises LiteLLMError if chat returns invalid JSON.
    """
    mock_chat.return_value = {"content": "NOT VALID JSON"}

    client = LiteLLMClient(api_key="FAKE_KEY")
    schema = {"title": "string"}

    with pytest.raises(LiteLLMError) as excinfo:
        client.call_structured("Prompt", schema)

    assert "JSON parse error" in str(excinfo.value)


@patch("llm_engine.litellm_client.litellm.chat_completion", autospec=True)
def test_call_structured_exception_in_chat(mock_chat):
    """
    Test call_structured raises LiteLLMError if chat_completion throws an exception.
    """
    mock_chat.side_effect = Exception("Some internal error")

    client = LiteLLMClient(api_key="FAKE_KEY")
    with pytest.raises(LiteLLMError) as excinfo:
        client.call_structured("Prompt text", {"title": "string"})

    assert "Error during LLM call" in str(excinfo.value)


@patch("llm_engine.litellm_client.litellm.embedding", autospec=True)
def test_get_embedding_success(mock_embedding):
    """
    Test get_embedding returns the embedding from litellm.embedding successfully.
    """
    mock_embedding.return_value = [0.1, 0.2, 0.3]

    client = LiteLLMClient(api_key="FAKE_KEY")
    vec = client.get_embedding("Hello world")
    assert vec == [0.1, 0.2, 0.3]


@patch("llm_engine.litellm_client.litellm.embedding", autospec=True)
def test_get_embedding_error(mock_embedding):
    """
    Test get_embedding raises LiteLLMError if embedding call fails.
    """
    mock_embedding.side_effect = Exception("Embedding Error")

    client = LiteLLMClient(api_key="FAKE_KEY")
    with pytest.raises(LiteLLMError) as excinfo:
        client.get_embedding("Some text")

    assert "Error retrieving embedding" in str(excinfo.value)


##############################################################################
# Integration Tests (real calls)
##############################################################################
@pytest.mark.integration
def test_call_structured_integration(openai_api_key):
    """
    Integration test: actually call litellm.chat_completion
    using your real OPENAI_API_KEY.
    If no key is found, test is skipped.
    """
    client = LiteLLMClient(
        api_key=openai_api_key,
        model_name="gpt-3.5-turbo",
        temperature=0.0,
        max_tokens=100
    )

    schema = {"name": "string", "age": "number"}
    prompt = "Return only valid JSON with name and age keys."
    result = client.call_structured(prompt, schema)
    print("Integration structured result:", result)
    assert "name" in result
    assert "age" in result


@pytest.mark.integration
def test_get_embedding_integration(openai_api_key):
    """
    Integration test: actually call litellm.embedding with a real OpenAI key.
    """
    client = LiteLLMClient(
        api_key=openai_api_key,
        model_name="text-embedding-ada-002"
    )

    text = "GraphRouter is a flexible Python library for graph databases."
    embedding = client.get_embedding(text)
    print("Integration embedding length:", len(embedding))

    assert isinstance(embedding, list)
    assert len(embedding) > 10
    assert all(isinstance(v, float) for v in embedding)