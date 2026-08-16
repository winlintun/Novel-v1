"""Offline Ollama client (SPEC §2.4, AGENTS.md backend contract).

- POST /api/generate with ``think=false``, ``keep_alive=-1``, temperature 0.2
- exponential backoff on connection/HTTP errors (2s, 4s, 8s)
- empty output retried once at temperature 0.5 (TEST-OLL-003)
- timeout -> E_TIMEOUT after 3 attempts (TEST-OLL-002)
- **single-resident-model discipline**: the pipeline runs several role models
  (analyzer / draft / polish / auditor).  Ollama can usually keep only one
  large model resident at a time, so when a call targets a *different* model
  than the previously loaded one, the old model is explicitly unloaded first
  (``keep_alive=0``) before the new generation loads.  ``unload()`` releases
  the last model at the end of a run.  Both can be disabled by passing
  ``auto_unload=False``.
- testable without a server: pass a fake ``session`` adapter
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests

from . import jsonparse


class OllamaError(IOError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code}] {self.message}"


DEFAULT_BACKOFF = (2, 4, 8)
MAX_ATTEMPTS = 3


class OllamaClient:
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "padauk-gemma:q8_0",
        timeout: int = 600,
        temperature: float = 0.2,
        session: Optional[Any] = None,
        auto_unload: bool = True,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = float(temperature)
        self.session = session if session is not None else requests.Session()
        self.auto_unload = auto_unload
        self.loaded_model: Optional[str] = None
        self.retry_count = 0
        self.last_payloads: List[Dict[str, Any]] = []

    # -- server metadata ---------------------------------------------------- #
    def ping(self) -> bool:
        try:
            resp = self.session.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def models(self) -> List[str]:
        resp = self.session.get(f"{self.host}/api/tags", timeout=10)
        resp.raise_for_status()
        return [str(m.get("name", "")) for m in resp.json().get("models", [])]

    def check_model(self) -> bool:
        return self.ping() and self.model in self.models()

    # -- generation ---------------------------------------------------------- #
    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
        timeout: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generate text. Retries per SPEC §6 error matrix; raises OllamaError.

        ``model`` optionally overrides the client's default model per call so a
        single client can serve role-specific models (MP1 analyzer / MP2 draft /
        MP3 polish / auditor etc per NEW_TODO role assignment).
        """
        effective = model or self.model
        if self.auto_unload and self.loaded_model is not None and self.loaded_model != effective:
            self.unload(self.loaded_model)
            self.loaded_model = None

        payload = self._payload(prompt, system, temperature, num_predict, model=effective)
        self.retry_count = 0
        self.last_payloads = [dict(payload)]
        attempts = 0

        while True:
            attempts += 1
            self.retry_count = attempts
            try:
                data = self._post("/api/generate", payload, timeout or self.timeout)
                text = str(data.get("response", "") or "").strip()
                if not text:
                    # empty output -> retry once at temperature 0.5
                    if attempts == 1:
                        payload["options"]["temperature"] = 0.5
                        self.last_payloads.append(dict(payload))
                        continue
                    raise OllamaError("E_EMPTY", "model returned empty output")
                self.loaded_model = effective
                return text
            except requests.Timeout as exc:
                if attempts >= MAX_ATTEMPTS:
                    raise OllamaError("E_TIMEOUT", f"generation timed out after {attempts} attempts") from exc
            except requests.ConnectionError as exc:
                if attempts >= MAX_ATTEMPTS:
                    raise OllamaError("E_CONN", f"cannot reach Ollama at {self.host}") from exc
            except requests.HTTPError as exc:
                if attempts >= MAX_ATTEMPTS:
                    raise OllamaError("E_HTTP", f"HTTP error calling Ollama: {exc}") from exc
            if attempts < MAX_ATTEMPTS:
                time.sleep(DEFAULT_BACKOFF[min(attempts - 1, len(DEFAULT_BACKOFF) - 1)])

    def _payload(
        self,
        prompt: str,
        system: str,
        temperature: Optional[float],
        num_predict: Optional[int],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        total_tokens = max(512, int(len(prompt) * 1.5) + 512)
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": -1,
            "options": {
                "temperature": float(temperature) if temperature is not None else self.temperature,
                "num_predict": int(num_predict) if num_predict is not None else min(8192, total_tokens),
            },
        }
        if system:
            payload["system"] = system
        return payload

    def _post(self, path: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        resp = self.session.post(f"{self.host}{path}", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def unload(self, model: Optional[str] = None) -> None:
        """Best-effort unload a model (``keep_alive=0``) to free VRAM.

        Defaults to the client's ``model``.  Requires a live session; never
        raises — a failed unload just means Ollama keeps the model warm.
        """
        target = model or self.model
        try:
            self.session.post(
                f"{self.host}/api/generate",
                json={"model": target, "prompt": "", "keep_alive": 0, "stream": False},
                timeout=30,
            )
        except requests.RequestException:
            pass
        if self.loaded_model == target:
            self.loaded_model = None

    # -- response parsing passthrough -------------------------------------- #
    def parse_translations(self, raw: str) -> List[str]:
        return jsonparse.parse_translations(raw)

    def parse_results(self, raw: str) -> List[Dict[str, Any]]:
        return jsonparse.parse_results(raw)