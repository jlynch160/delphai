"""Model client for Microsoft Foundry, with a deterministic offline fallback.

Design principle: the *quantitative reasoning* is computed in readiness.py and is
identical in both modes. The model is used only to turn structured findings into
natural-language narration. So:
  * Offline (no endpoint)  -> agents narrate with their own templates. Demo still shines.
  * Foundry (endpoint set) -> the model enriches the narration in each agent's voice.

Connection options (set in .env):
  1. Foundry project endpoint + Entra ID login (recommended):
        AZURE_AI_PROJECT_ENDPOINT=https://<your-project>.services.ai.azure.com/...
        AZURE_AI_MODEL_DEPLOYMENT=gpt-4o
     Auth uses DefaultAzureCredential -> run `az login` as your account first.
  2. Azure OpenAI endpoint + key:
        AZURE_OPENAI_ENDPOINT=https://<res>.openai.azure.com/
        AZURE_OPENAI_API_KEY=<key>
        AZURE_AI_MODEL_DEPLOYMENT=gpt-4o
"""
from __future__ import annotations
from . import config


class ModelClient:
    def __init__(self) -> None:
        self.mode = "offline"
        self.detail = "deterministic demo brain (no model endpoint configured)"
        self._client = None
        self._kind = None
        self.total_tokens = 0       # cumulative across this run (real Foundry usage)
        self.last_tokens = 0
        self.last_latency_ms = 0
        self._connect()

    def _connect(self) -> None:
        # Option 2: Azure OpenAI key auth (simplest)
        if config.AZURE_OPENAI_ENDPOINT and config.AZURE_OPENAI_API_KEY:
            try:
                from openai import AzureOpenAI
                # Resilience: fail fast to the deterministic fallback under throttling
                # rather than hanging on the SDK's default long retry/backoff.
                self._client = AzureOpenAI(
                    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                    api_key=config.AZURE_OPENAI_API_KEY,
                    api_version=config.AZURE_OPENAI_API_VERSION,
                    timeout=22.0,
                    max_retries=1,
                )
                self._kind = "azure_openai"
                self.mode = "foundry"
                self.detail = f"Azure OpenAI · {config.AZURE_AI_MODEL_DEPLOYMENT}"
                return
            except Exception as e:  # pragma: no cover - depends on env
                self.detail = f"offline (Azure OpenAI init failed: {e})"

        # Option 1: Foundry project endpoint + Entra ID
        if config.AZURE_AI_PROJECT_ENDPOINT:
            try:
                from azure.ai.inference import ChatCompletionsClient
                from azure.identity import DefaultAzureCredential
                self._client = ChatCompletionsClient(
                    endpoint=config.AZURE_AI_PROJECT_ENDPOINT,
                    credential=DefaultAzureCredential(),
                )
                self._kind = "foundry_inference"
                self.mode = "foundry"
                self.detail = f"Microsoft Foundry · {config.AZURE_AI_MODEL_DEPLOYMENT}"
                return
            except Exception as e:  # pragma: no cover - depends on env
                self.detail = f"offline (Foundry init failed: {e})"

    # -----------------------------------------------------------------
    _DEPTH = (" Reason it through, don't just assert: reference the actual figures and the named "
              "candidates, weigh the trade-offs explicitly, and explain the 'why' behind your position "
              "in 3–5 substantive sentences. No generic filler — be specific to this team and cert.")

    def narrate(self, system_prompt: str, user_prompt: str, fallback: str) -> str:
        """Return model narration, or the deterministic fallback when offline.
        Records real latency + token usage for telemetry."""
        import time
        self.last_tokens = 0
        self.last_latency_ms = 0
        if self.mode != "foundry" or self._client is None:
            return fallback
        system_prompt = system_prompt + self._DEPTH
        t0 = time.time()
        try:
            if self._kind == "azure_openai":
                resp = self._client.chat.completions.create(
                    model=config.AZURE_AI_MODEL_DEPLOYMENT,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": user_prompt}],
                    temperature=0.5, max_tokens=600,
                )
                self.last_latency_ms = int((time.time() - t0) * 1000)
                self.last_tokens = int(getattr(resp.usage, "total_tokens", 0) or 0)
                self.total_tokens += self.last_tokens
                return resp.choices[0].message.content.strip()
            if self._kind == "foundry_inference":
                from azure.ai.inference.models import SystemMessage, UserMessage
                resp = self._client.complete(
                    model=config.AZURE_AI_MODEL_DEPLOYMENT,
                    messages=[SystemMessage(content=system_prompt), UserMessage(content=user_prompt)],
                    temperature=0.5, max_tokens=600,
                )
                self.last_latency_ms = int((time.time() - t0) * 1000)
                self.last_tokens = int(getattr(resp.usage, "total_tokens", 0) or 0)
                self.total_tokens += self.last_tokens
                return resp.choices[0].message.content.strip()
        except Exception as e:  # pragma: no cover
            return f"{fallback}\n  (live model call failed, used offline narration: {e})"
        return fallback


_CLIENT: ModelClient | None = None


def get_model() -> ModelClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = ModelClient()
    return _CLIENT
