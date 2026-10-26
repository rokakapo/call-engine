from dataclasses import dataclass
from urllib.parse import urljoin
import requests


@dataclass
class ProviderConfig:
    base_url: str = "https://api.openai.com/v1/"
    api_key: str = ""
    role: str = "You are a concise phone assistant."
    model: str = ""


class AiConversationEngine:
    """OpenAI-compatible STT -> LLM -> TTS client. Credentials remain in memory."""
    def __init__(self):
        self.config = ProviderConfig()

    def set_config(self, raw: dict):
        base = raw.get("base_url", "").strip().rstrip("/") + "/"
        if not base.startswith(("https://", "http://")):
            raise ValueError("Base URL must start with http:// or https://")
        self.config = ProviderConfig(base, raw.get("api_key", "").strip(), raw.get("role", ""), raw.get("model", ""))

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}

    def fetch_models(self):
        response = requests.get(urljoin(self.config.base_url, "models"), headers=self._headers, timeout=10)
        response.raise_for_status()
        return sorted(item["id"] for item in response.json().get("data", []) if item.get("id"))

    def test_connection(self):
        try:
            models = self.fetch_models()
            return {"ok": True, "message": "Provider reachable", "models": models}
        except requests.RequestException as exc:
            return {"ok": False, "message": str(exc), "models": []}

    def reply(self, transcript: str) -> str:
        if not self.config.api_key or not self.config.model:
            return "AI is not configured."
        payload = {"model": self.config.model, "messages": [{"role": "system", "content": self.config.role}, {"role": "user", "content": transcript}]}
        response = requests.post(urljoin(self.config.base_url, "chat/completions"), headers={**self._headers, "Content-Type": "application/json"}, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
