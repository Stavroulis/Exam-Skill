from __future__ import annotations

import os
import streamlit as st


OPENAI_MODELS = {
    "GPT-4.1": "gpt-4.1",
    "GPT-4.1 mini": "gpt-4.1-mini",
    "GPT-4o": "gpt-4o",
    "GPT-4o mini": "gpt-4o-mini",
}

ANTHROPIC_MODELS = {
    "Claude Sonnet 4.6": "claude-sonnet-4-6",
    "Claude Opus 4.7": "claude-opus-4-7",
}


def get_secret(key: str):
    try:
        value = st.secrets.get(key)
        if value:
            return value
    except Exception:
        pass

    return os.getenv(key)


def call_llm(
    prompt: str,
    llm_config: dict | None = None,
    provider: str | None = None,
    model: str | None = None,
    **kwargs,
) -> str:
    """
    Backward-compatible LLM caller.
    """

    if llm_config is not None:
        provider = llm_config.get("provider")
        model = llm_config.get("model")

    if not provider:
        raise ValueError("Missing LLM provider.")

    if not model:
        raise ValueError("Missing LLM model.")

    if provider == "OpenAI / ChatGPT":
        return call_openai(prompt, model)

    if provider == "Anthropic / Claude":
        return call_anthropic(prompt, model)

    raise ValueError(f"Unknown LLM provider: {provider}")


def call_openai(prompt: str, model: str) -> str:
    from openai import OpenAI

    api_key = get_secret("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
        )
        return response.output_text

    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e


def call_anthropic(prompt: str, model: str) -> str:
    from anthropic import Anthropic

    api_key = get_secret("ANTHROPIC_API_KEY")

    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing.")

    client = Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        return response.content[0].text

    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}") from e