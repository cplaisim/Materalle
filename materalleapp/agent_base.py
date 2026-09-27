import anthropic
import httpx
from django.conf import settings
from abc import ABC, abstractmethod

LLM_TIMEOUT_SECONDS = 60.0
LLM_UNAVAILABLE_WARNING = "**Warning:** The LLM is not responding right now. This is a prewritten fallback response."

AGENT_FALLBACK_CATALOG = {
    'grace': [
        {
            'keywords': ('feeling', 'emotion', 'sad', 'angry', 'upset'),
            'answer': """**Title:** Name That Feeling
**Activity Type:** EMOTIONAL
**Age Range:** 3-4
**Description:** Show a child a few feeling faces or make expressions together in a mirror. Invite the child to name or point to a feeling, then ask what might help someone feel safe and supported.
**Developmental Goal:** Builds emotion vocabulary and helps children notice feelings in themselves and others.
**Materials:** A mirror or hand-drawn feeling faces
**Duration:** 5 minutes
**Group Size:** Individual or small group""",
        },
        {
            'keywords': ('sharing', 'taking turns', 'turn-taking', 'wait'),
            'answer': """**Title:** Roll and Take Turns
**Activity Type:** SHARING
**Age Range:** 2-3
**Description:** Sit together with a large soft ball. One child rolls it to a friend, then waits while the friend rolls it back. Name each turn and offer calm support while children wait.
**Developmental Goal:** Practices turn-taking, patience, and friendly back-and-forth play.
**Materials:** One large soft ball
**Duration:** 10 minutes
**Group Size:** 2-4 children""",
        },
        {
            'keywords': ('calm', 'breath', 'conflict', 'frustrated', 'self-regulation'),
            'answer': """**Title:** Smell the Flower, Cool the Soup
**Activity Type:** SELF_REG
**Age Range:** 3-4
**Description:** Invite children to imagine smelling a flower with a slow breath in, then cooling warm soup with a slow breath out. Practice together a few times when everyone is calm, and offer it as one option when a child feels overwhelmed.
**Developmental Goal:** Introduces a simple calming strategy and helps children pause before responding.
**Materials:** None
**Duration:** 3 minutes
**Group Size:** Individual or small group""",
        },
    ],
    'patience': [
        {
            'keywords': ('fine motor', 'grasp', 'draw', 'pinch', 'finger'),
            'answer': """**Title:** Build and Place
**Activity Type:** FINE
**Age Range:** 2-3
**Description:** Offer a few large, age-safe blocks and invite the child to pick them up, stack them, and place them in a short tower. Let the child choose whether to build or knock it down.
**Developmental Goal:** Practices grasping, hand control, and coordinated release.
**Materials:** Large blocks with no small detachable parts
**Safety Notes:** Supervise closely and use materials too large to present a choking risk.
**Duration:** 10 minutes""",
        },
        {
            'keywords': ('gross motor', 'run', 'jump', 'movement', 'walk', 'active'),
            'answer': """**Title:** Animal Movement Path
**Activity Type:** GROSS
**Age Range:** 3-4
**Description:** In a clear, open space, invite children to take a few steps like a bear, hop like a bunny, or stretch like a cat. Let each child choose a movement and take breaks as needed.
**Developmental Goal:** Encourages balance, body awareness, and large-muscle coordination.
**Materials:** Clear floor space
**Safety Notes:** Keep the path free of obstacles; avoid climbing on furniture and adapt movements to each child's ability.
**Duration:** 8 minutes""",
        },
        {
            'keywords': ('sensory', 'texture', 'balance', 'coordination', 'touch'),
            'answer': """**Title:** Texture Discovery
**Activity Type:** SENSORY
**Age Range:** 2-3
**Description:** Offer two or three large, clean fabric squares with different textures. Let the child touch, compare, and describe them, following the child's interest without forcing contact.
**Developmental Goal:** Supports sensory exploration, hand use, and descriptive language.
**Materials:** Large clean fabric squares
**Safety Notes:** Check for sensitivities, supervise throughout, and avoid small items that could be mouthed.
**Duration:** 5-10 minutes""",
        },
    ],
    'sage': [
        {
            'keywords': ('learn', 'learning', 'milestone', 'curriculum', 'plan', 'skill'),
            'answer': "Start with one skill the child is curious about, then offer a short play-based activity at a comfortable level. Observe what the child can do independently and what support helps; use those observations to plan the next small step. Development varies, so this is guidance rather than a diagnosis.",
        },
        {
            'keywords': ('food', 'meal', 'nutrition', 'menu', 'snack', 'eat'),
            'answer': "For a balanced meal, offer an age-appropriate mix of vegetables or fruit, a whole grain, and a protein, with water available. Check each child's allergy and feeding plan, and adapt textures and portions to their developmental stage. Consult the family's clinician for individual nutrition concerns.",
        },
        {
            'keywords': ('health', 'wellness', 'sick', 'symptom', 'safety', 'wellbeing'),
            'answer': "For a child's health concern, follow your center's safety and family-notification procedures, record observable facts, and contact the child's caregiver. Seek urgent medical help for emergency symptoms. I can offer general information, but I can't diagnose or replace a clinician.",
        },
    ],
}


def get_agent_fallback(agent_name: str, messages: list) -> str:
    """Select a short, role-specific canned response when an LLM is unavailable."""
    catalog = AGENT_FALLBACK_CATALOG.get(agent_name, AGENT_FALLBACK_CATALOG['sage'])
    latest_user_message = next(
        (str(message.get('content', '')) for message in reversed(messages)
         if message.get('role') == 'user'),
        '',
    ).casefold()
    answer = catalog[0]['answer']
    for item in catalog:
        if any(keyword in latest_user_message for keyword in item['keywords']):
            answer = item['answer']
            break
    return f"{LLM_UNAVAILABLE_WARNING}\n\n{answer}"


def get_agent_response(agent_name: str, messages: list, system_prompt: str = None):
    """Call the configured LLM, returning a canned answer if the call fails."""
    try:
        response = get_anthropic_response(messages=messages, system_prompt=system_prompt)
        if not response or not response.strip():
            raise RuntimeError('The LLM returned an empty response.')
        return response, False
    except Exception as exc:
        print(f"{agent_name.title()} LLM unavailable; using fallback: {exc}")
        return get_agent_fallback(agent_name, messages), True


# --- Anthropic backend ---
_anthropic_client = anthropic.Anthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=0,
)
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
        return anthropic.Anthropic(
            api_key=db.anthropic_api_key,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )
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
            timeout=LLM_TIMEOUT_SECONDS,
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
        timeout=LLM_TIMEOUT_SECONDS,
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
        agent_name = self.__class__.__module__.split('.', maxsplit=1)[0]
        response, _ = get_agent_response(agent_name, messages, self.system_prompt)
        return response
