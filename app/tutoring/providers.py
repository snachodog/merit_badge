"""Provider interface for the AI tutor (PLAN.md 9.4).

A provider turns a system prompt and a message list into text. Business logic
only calls `complete`. Add a provider by writing another class with the same
method. Tests set `HTTP_TRANSPORT` to a fake endpoint.
"""
import logging
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

HTTP_TRANSPORT = None  # tests only
HTTP_TIMEOUT = 60.0
MAX_REPLY_CHARS = 8000


class ProviderError(Exception):
    """A failed model call. The message is safe to show to the learner."""


def base_url_problem(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "Enter a full URL that starts with http:// or https://."
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "The URL must not contain a login, query or fragment."
    return ""


class OpenAICompatibleProvider:
    """Any server with POST {base_url}/chat/completions (Ollama, llama.cpp, vLLM, hosted APIs)."""

    name = "openai-compatible"

    def __init__(self, base_url, model, api_key=None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    def complete(self, system, messages, max_tokens=700):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "stream": False,
        }
        kwargs = {"timeout": HTTP_TIMEOUT}
        if HTTP_TRANSPORT is not None:
            kwargs["transport"] = HTTP_TRANSPORT
        try:
            with httpx.Client(**kwargs) as client:
                response = client.post(self.base_url + "/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException:
            raise ProviderError("The AI tutor took too long to answer. Try again in a moment.")
        except httpx.HTTPError:
            log.warning("AI provider request failed", exc_info=False)
            raise ProviderError("The AI tutor could not be reached. Your records are safe. Try again later.")
        if response.status_code in (401, 403):
            raise ProviderError("The AI tutor refused the request. Ask an admin to check the key in Settings.")
        if response.status_code != 200:
            log.warning("AI provider returned HTTP %s", response.status_code)
            raise ProviderError("The AI tutor returned an error. Your records are safe. Try again later.")
        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("The AI tutor sent an answer the app could not read.")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("The AI tutor sent an empty answer. Try again.")
        return text.strip()[:MAX_REPLY_CHARS]
