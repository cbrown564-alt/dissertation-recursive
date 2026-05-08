from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResult:
    content: str
    model: str
    provider: str
    raw: dict[str, object] = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_name: str
    model: str

    def chat_json(self, messages: list[ChatMessage], schema: dict[str, object]) -> LLMResult:
        ...


def load_dotenv_keys(path: str | Path = ".env") -> set[str]:
    """Load .env into the process without returning or printing secret values."""
    env_path = Path(path)
    keys: set[str] = set()
    if not env_path.exists():
        return keys
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
        keys.add(key)
    return keys


class OpenAICompatibleProvider:
    """Provider for local OpenAI-compatible servers and OpenAI's chat endpoint."""

    provider_name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
        provider_name: str = "openai-compatible",
        timeout_seconds: int = 120,
        temperature: float | None = 0.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.provider_name = provider_name
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def chat_json(self, messages: list[ChatMessage], schema: dict[str, object]) -> LLMResult:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "seizure_frequency_extraction",
                "strict": True,
                "schema": schema,
            },
        }
        payload = {
            "model": self.model,
            "messages": [message.__dict__ for message in messages],
            "response_format": response_format,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        response = _post_json(
            f"{self.base_url}/chat/completions",
            payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout_seconds=self.timeout_seconds,
        )
        content = response["choices"][0]["message"]["content"]  # type: ignore[index]
        return LLMResult(
            content=str(content),
            model=self.model,
            provider=self.provider_name,
            raw=response,
        )


class AnthropicProvider:
    provider_name = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str,
        timeout_seconds: int = 120,
        temperature: float | None = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat_json(self, messages: list[ChatMessage], schema: dict[str, object]) -> LLMResult:
        system_messages = [message.content for message in messages if message.role == "system"]
        chat_messages = [
            message.__dict__
            for message in messages
            if message.role in {"user", "assistant"}
        ]
        payload: dict[str, object] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": chat_messages,
            "tools": [
                {
                    "name": "return_json",
                    "description": "Return the extraction result as schema-conformant JSON.",
                    "input_schema": schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": "return_json"},
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if system_messages:
            payload["system"] = "\n\n".join(system_messages)
        response = _post_json(
            "https://api.anthropic.com/v1/messages",
            payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout_seconds=self.timeout_seconds,
        )
        content_blocks = response.get("content", [])
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    return LLMResult(
                        content=json.dumps(block.get("input", {})),
                        model=self.model,
                        provider=self.provider_name,
                        raw=response,
                    )
        return LLMResult(
            content=json.dumps(response),
            model=self.model,
            provider=self.provider_name,
            raw=response,
        )


class OllamaProvider:
    provider_name = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/api",
        timeout_seconds: int = 120,
        temperature: float = 0.0,
        num_predict: int = 512,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.num_predict = num_predict

    def chat_json(self, messages: list[ChatMessage], schema: dict[str, object]) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [message.__dict__ for message in messages],
            "stream": False,
            "format": schema,
            "think": False,
            "options": {"temperature": self.temperature, "num_predict": self.num_predict},
        }
        response = _post_json(
            f"{self.base_url}/chat",
            payload,
            headers={},
            timeout_seconds=self.timeout_seconds,
        )
        content = response["message"]["content"]  # type: ignore[index]
        return LLMResult(content=str(content), model=self.model, provider=self.provider_name, raw=response)


def local_lmstudio_provider(
    model: str,
    base_url: str = "http://localhost:1234/v1",
    timeout_seconds: int = 120,
    temperature: float | None = 0.0,
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        provider_name="lmstudio",
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def local_vllm_provider(
    model: str,
    base_url: str = "http://localhost:8000/v1",
    timeout_seconds: int = 120,
    temperature: float | None = 0.0,
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        provider_name="vllm",
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def local_ollama_provider(
    model: str,
    base_url: str = "http://localhost:11434/api",
    timeout_seconds: int = 120,
    temperature: float = 0.0,
    num_predict: int = 512,
) -> OllamaProvider:
    return OllamaProvider(
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        num_predict=num_predict,
    )


def openai_provider(
    model: str,
    temperature: float | None = 0.0,
    timeout_seconds: int = 120,
) -> OpenAICompatibleProvider:
    load_dotenv_keys()
    api_key = os.environ.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured in .env or environment.")
    if model.startswith("gpt-5"):
        temperature = None
    return OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        model=model,
        api_key=api_key,
        provider_name="openai",
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def anthropic_provider(
    model: str,
    temperature: float | None = 0.0,
    timeout_seconds: int = 120,
) -> AnthropicProvider:
    load_dotenv_keys()
    api_key = os.environ.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Anthropic API key is not configured in .env or environment.")
    if model.endswith("-4-7"):
        temperature = None
    return AnthropicProvider(
        model=model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def probe_openai_compatible(base_url: str, timeout_seconds: int = 2) -> dict[str, object]:
    try:
        response = _get_json(f"{base_url.rstrip('/')}/models", timeout_seconds=timeout_seconds)
        return {"ok": True, "response": response}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def probe_ollama(base_url: str = "http://localhost:11434/api", timeout_seconds: int = 2) -> dict[str, object]:
    try:
        response = _get_json(f"{base_url.rstrip('/')}/tags", timeout_seconds=timeout_seconds)
        return {"ok": True, "response": response}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _post_json(
    url: str,
    payload: dict[str, object],
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, timeout_seconds: int) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))
