import anthropic
import httpx
from django.conf import settings
from abc import ABC, abstractmethod

# --- Anthropic backend ---
_anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# --- Ollama backend ---
_OLLAMA_BASE_URL = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:12434")
_OLLAMA_MODEL = getattr(settings, "OLLAMA_MODEL", "llama3.2:1b")
_LLM_BACKEND = getattr(settings, "LLM_BACKEND", "anthropic")

# Keep the old name for backwards-compat
client = _anthropic_client
DEFAULT_MODEL = DEFAULT_ANTHROPIC_MODEL


def _load_db_settings():
    """Load LLM settings from the database (if available)."""
    try:
        from website.models import LLMSettings
        return LLMSettings.get_settings()
    except Exception:
        return None


def get_llm_backend():
    """Return the current LLM backend name."""
    db = _load_db_settings()
    if db:
        return db.backend
    return _LLM_BACKEND


_VALID_BACKENDS = ("anthropic", "ollama", "lmstudio", "vllm", "llamacpp")
_LOCAL_BACKENDS = ("ollama", "lmstudio", "vllm", "llamacpp")


def set_llm_backend(backend: str):
    """Switch the active LLM backend at runtime and persist to DB."""
    global _LLM_BACKEND
    if backend not in _VALID_BACKENDS:
        raise ValueError(f"backend must be one of {_VALID_BACKENDS}")
    _LLM_BACKEND = backend
    try:
        from website.models import LLMSettings
        obj = LLMSettings.get_settings()
        obj.backend = backend
        obj.save(update_fields=['backend'])
    except Exception:
        pass


def get_ollama_model():
    """Return the configured Ollama model name."""
    db = _load_db_settings()
    if db and db.ollama_model:
        return db.ollama_model
    return _OLLAMA_MODEL


def get_ollama_base_url():
    """Return the configured Ollama base URL."""
    db = _load_db_settings()
    if db and db.ollama_base_url:
        return db.ollama_base_url
    return _OLLAMA_BASE_URL


def get_anthropic_client():
    """Return an Anthropic client using the DB-stored API key if available."""
    db = _load_db_settings()
    if db and db.anthropic_api_key:
        return anthropic.Anthropic(api_key=db.anthropic_api_key)
    return _anthropic_client


def _get_ollama_response(messages: list, system_prompt: str = None, model: str = None) -> str:
    """Send messages to a local Ollama instance and return the assistant's text."""
    ollama_messages = []
    if system_prompt:
        ollama_messages.append({"role": "system", "content": system_prompt})
    ollama_messages.extend(messages)

    payload = {
        "model": model or get_ollama_model(),
        "messages": ollama_messages,
        "stream": False,
    }
    base_url = get_ollama_base_url()
    url = f"{base_url}/api/chat"
    print(f"[Ollama] Connecting to {url} with model {payload['model']}")
    try:
        response = httpx.post(
            url,
            json=payload,
            timeout=300.0,
        )
        print(f"[Ollama] Response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
    except Exception as e:
        print(f"[Ollama] Error: {type(e).__name__}: {e}")
        raise


def _get_local_api_url():
    """Return the configured local OpenAI-compatible API URL."""
    db = _load_db_settings()
    if db and db.local_api_url:
        return db.local_api_url
    return "http://localhost:1234"


def _get_local_model():
    """Return the configured local model name."""
    db = _load_db_settings()
    if db and db.local_model:
        return db.local_model
    return "default"


def _get_openai_compat_response(messages: list, system_prompt: str = None, model: str = None) -> str:
    """Send messages to an OpenAI-compatible local server (LM Studio, vLLM, llama.cpp)."""
    api_messages = []
    if system_prompt:
        api_messages.append({"role": "system", "content": system_prompt})
    api_messages.extend(messages)

    base_url = _get_local_api_url()
    payload = {
        "model": model or _get_local_model(),
        "messages": api_messages,
        "stream": False,
    }
    response = httpx.post(
        f"{base_url}/v1/chat/completions",
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def get_anthropic_response(messages: list, model: str = DEFAULT_ANTHROPIC_MODEL, max_tokens: int = 1024, system_prompt: str = None) -> str:
    """Send messages to the configured LLM backend and return the assistant's response text.

    Routes to Ollama when LLM_BACKEND=ollama, otherwise uses the Anthropic API.
    Accepts an optional system_prompt to guide the LLM's behavior.
    """
    backend = get_llm_backend()

    if backend == "ollama":
        try:
            return _get_ollama_response(messages, system_prompt=system_prompt)
        except Exception as e:
            print(f"Error calling Ollama API: {e}")
            raise

    if backend in ("lmstudio", "vllm", "llamacpp"):
        try:
            return _get_openai_compat_response(messages, system_prompt=system_prompt)
        except Exception as e:
            print(f"Error calling {backend} API: {e}")
            raise

    try:
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        response = get_anthropic_client().messages.create(**kwargs)
        if response.content:
            return response.content[0].text
        raise Exception("Anthropic API returned an empty response.")
    except Exception as e:
        print(f"Error calling Anthropic API: {e}")
        raise


class BaseAgent(ABC):
    def __init__(self):
        self.model = DEFAULT_ANTHROPIC_MODEL
        self.system_prompt = self.get_system_prompt()

    @abstractmethod
    def get_system_prompt(self):
        pass

    async def get_response(self, message, context=None):
        messages = []
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})

        backend = get_llm_backend()

        if backend == "ollama":
            try:
                return _get_ollama_response(messages, system_prompt=self.system_prompt, model=get_ollama_model())
            except Exception as e:
                return f"Error: {str(e)}"

        if backend in ("lmstudio", "vllm", "llamacpp"):
            try:
                return _get_openai_compat_response(messages, system_prompt=self.system_prompt)
            except Exception as e:
                return f"Error: {str(e)}"

        try:
            response = get_anthropic_client().messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return f"Error: {str(e)}"
