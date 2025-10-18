"""OpenAI LLM Service for making chat completions"""
from typing import Optional, List, Dict
from openai import OpenAI
from config import settings

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Default model
DEFAULT_MODEL = "gpt-4o-mini"


def get_llm_response(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system_message: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs
) -> str:
    """
    Get a response from the OpenAI LLM.

    Args:
        prompt: The user prompt/message to send to the LLM
        model: The model to use (default: openai/gpt-oss-20b)
        system_message: Optional system message to set context/behavior
        temperature: Controls randomness (0.0-2.0, default: 0.7)
        max_tokens: Maximum tokens in the response (optional)
        **kwargs: Additional parameters to pass to the OpenAI API

    Returns:
        str: The LLM's response text

    Raises:
        Exception: If the API call fails

    Example:
        >>> from app.services.llm_service import get_llm_response
        >>> response = get_llm_response("What is diabetes?")
        >>> print(response)
    """
    try:
        # Build messages list
        messages: List[Dict[str, str]] = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        # Make API call
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        # Extract and return response
        response_text = completion.choices[0].message.content
        return response_text if response_text else ""

    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")


def get_llm_chat_response(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs
) -> str:
    """
    Get a response from the OpenAI LLM with a full conversation history.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
                 Example: [{"role": "user", "content": "Hello"}]
        model: The model to use (default: openai/gpt-oss-20b)
        temperature: Controls randomness (0.0-2.0, default: 0.7)
        max_tokens: Maximum tokens in the response (optional)
        **kwargs: Additional parameters to pass to the OpenAI API

    Returns:
        str: The LLM's response text

    Raises:
        Exception: If the API call fails

    Example:
        >>> from app.services.llm_service import get_llm_chat_response
        >>> messages = [
        ...     {"role": "system", "content": "You are a medical assistant"},
        ...     {"role": "user", "content": "What is hypertension?"}
        ... ]
        >>> response = get_llm_chat_response(messages)
    """
    try:
        # Make API call
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        # Extract and return response
        response_text = completion.choices[0].message.content
        return response_text if response_text else ""

    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")
