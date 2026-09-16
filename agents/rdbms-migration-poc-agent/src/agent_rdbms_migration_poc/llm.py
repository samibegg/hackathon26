"""LLM provider selection for rdbms-migration-poc-agent."""

from __future__ import annotations

import logging
import os
from typing import Any, cast

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "openai"
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-3-flash-preview",
    "openai": "gpt-5.6-luna",
    "xai": "grok-4.6",
}


def build_llm(
    provider: str = DEFAULT_PROVIDER,
    temperature: float = 0,
) -> BaseChatModel:
    configured_provider = provider.strip().lower()
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    xai_key = os.environ.get("XAI_API_KEY", "")

    def _build_gemini() -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = DEFAULT_MODELS["gemini"]
        logger.info("Using Gemini LLM: %s", model_name)
        kwargs: dict[str, Any] = {
            "api_key": gemini_key,
            "model": model_name,
            "temperature": temperature,
        }
        if model_name.startswith("gemini-3-"):
            kwargs["thinking_budget"] = 0
        return cast(BaseChatModel, ChatGoogleGenerativeAI(**kwargs))

    def _build_openai() -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        model_name = DEFAULT_MODELS["openai"]
        logger.info("Using OpenAI LLM: %s", model_name)
        openai_base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        chat_kwargs: dict[str, Any] = {
            "api_key": openai_key,
            "model": model_name,
            "temperature": temperature,
        }
        if openai_base_url:
            chat_kwargs["base_url"] = openai_base_url
        if openai_base_url and "azure-api.net" in openai_base_url:
            chat_kwargs["default_headers"] = {"api-key": openai_key}
        return cast(BaseChatModel, ChatOpenAI(**chat_kwargs))

    def _build_anthropic() -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic

        model_name = DEFAULT_MODELS["anthropic"]
        logger.info("Using Anthropic LLM: %s", model_name)
        return cast(
            BaseChatModel,
            ChatAnthropic(api_key=anthropic_key, model_name=model_name),
        )

    def _build_xai() -> BaseChatModel:
        from langchain_xai import ChatXAI

        model_name = DEFAULT_MODELS["xai"]
        logger.info("Using xAI LLM: %s", model_name)
        return cast(
            BaseChatModel,
            ChatXAI(api_key=xai_key, model=model_name, temperature=temperature),
        )

    builders = {
        "gemini": (gemini_key, _build_gemini),
        "openai": (openai_key, _build_openai),
        "anthropic": (anthropic_key, _build_anthropic),
        "xai": (xai_key, _build_xai),
    }
    if configured_provider not in builders:
        raise RuntimeError(f"Unsupported provider {configured_provider!r}")
    provider_key, provider_builder = builders[configured_provider]
    if not provider_key:
        raise RuntimeError(f"Missing API key for provider {configured_provider!r}")
    return provider_builder()
