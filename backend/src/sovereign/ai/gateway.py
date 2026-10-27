"""One interface for every model provider.

The rest of the app streams text from a ChatModel and never imports a provider SDK, so
adding a provider (or an EU-hosted endpoint) touches only this file.
"""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
import httpx

from sovereign.config import Settings
from sovereign.models import ModelProfile, Provider


class ModelError(Exception):
    """A failure safe to show the user (no keys, no stack traces)."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


class ChatModel(Protocol):
    provider: str
    model: str
    usage: Usage

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        """Yield answer text. `usage` is filled in once the stream is exhausted."""
        ...


class AnthropicChatModel:
    provider = "anthropic"

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        self.client = client
        self.model = model
        self.usage = Usage()

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=messages,
                # Grounded Q&A over provided sources doesn't need deep reasoning.
                output_config={"effort": "low"},
            ) as stream:
                yield from stream.text_stream
                final = stream.get_final_message()
        except anthropic.AuthenticationError:
            raise ModelError("The Anthropic API key is missing or invalid.") from None
        except anthropic.RateLimitError:
            raise ModelError("The model provider is rate limiting requests. Try again.") from None
        except anthropic.BadRequestError as exc:
            if "credit balance" in str(exc):
                raise ModelError("The Anthropic account is out of credits.") from None
            raise ModelError("The model provider rejected the request.") from exc
        except anthropic.APIStatusError as exc:
            raise ModelError(f"The model provider returned an error ({exc.status_code}).") from exc
        except anthropic.APIConnectionError:
            raise ModelError("Could not reach the model provider.") from None

        self.usage = Usage(final.usage.input_tokens, final.usage.output_tokens)
        if final.stop_reason == "refusal":
            raise ModelError("The model declined to answer this request.")


class OllamaChatModel:
    """A model served by Ollama on your own hardware. Nothing leaves the network."""

    provider = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.usage = Usage()

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": True,
        }
        try:
            with httpx.stream(
                "POST", f"{self.base_url}/api/chat", json=body, timeout=self.timeout
            ) as response:
                if response.status_code == 404:
                    raise ModelError(
                        f"Ollama has no model '{self.model}'. Run: ollama pull {self.model}"
                    )
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if text := event.get("message", {}).get("content"):
                        yield text
                    if event.get("done"):
                        self.usage = Usage(
                            event.get("prompt_eval_count", 0), event.get("eval_count", 0)
                        )
        except httpx.ConnectError:
            raise ModelError(f"Could not reach Ollama at {self.base_url}. Is it running?") from None
        except httpx.HTTPError as exc:
            raise ModelError(f"Ollama request failed: {exc}") from exc


@dataclass
class FakeChatModel:
    """Scripted answers for tests. Records exactly what the model was shown."""

    respond: Callable[[str, list[dict]], str] = lambda system, messages: "No answer."
    provider: str = "fake"
    model: str = "fake"
    usage: Usage = field(default_factory=Usage)
    calls: list[tuple[str, list[dict]]] = field(default_factory=list)

    def stream(self, system: str, messages: list[dict]) -> Iterator[str]:
        self.calls.append((system, messages))
        answer = self.respond(system, messages)
        for start in range(0, len(answer), 20):
            yield answer[start : start + 20]
        self.usage = Usage(len(system) // 4, len(answer) // 4)


class Gateway:
    def __init__(self, settings: Settings, fake: FakeChatModel | None = None) -> None:
        self.settings = settings
        self.fake = fake
        self._anthropic: anthropic.Anthropic | None = None

    def model_for(self, profile: ModelProfile) -> ChatModel:
        match profile.provider:
            case Provider.ANTHROPIC:
                return AnthropicChatModel(self._anthropic_client(), profile.model)
            case Provider.OLLAMA:
                return OllamaChatModel(
                    self.settings.ollama_url, profile.model, self.settings.llm_timeout_s
                )
            case Provider.FAKE:
                if self.fake is None:
                    raise ModelError("The test model is not available in this deployment.")
                return self.fake
        raise ModelError(f"Unknown provider {profile.provider}")

    def _anthropic_client(self) -> anthropic.Anthropic:
        if self._anthropic is None:
            key = self.settings.anthropic_api_key
            self._anthropic = anthropic.Anthropic(
                **({"api_key": key.get_secret_value()} if key else {}),
                timeout=self.settings.llm_timeout_s,
            )
        return self._anthropic
