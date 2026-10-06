"""
One small model layer for the whole lab - OPEN EDITION.

    LLM_PROVIDER=local -> any OpenAI-compatible server running open-weight models:
                          Ollama (default, http://localhost:11434/v1), vLLM, llama.cpp server, LM Studio
    LLM_PROVIDER=mock  -> fully offline, deterministic answers (safety net for flaky Wi-Fi / no GPU)

The three building blocks of an agent (Module 1) are visible here:
    PROMPT  -> the `system` + `prompt` strings
    MODEL   -> LLM_MODEL (text + tools) and VISION_MODEL (images), both open-weight
    TOOLS   -> the `Tool` objects passed to `run_agent`, executed in a loop

Only open-source client code is used: httpx talks plain HTTP to the server.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import mimetypes
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

try:  # optional: load .env if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass


# Model tags are examples - check `ollama list` / your vLLM config. Defaults are Apache-2.0 licensed open-weight models.
def _cfg(name, default):
    return os.getenv(name, default)


def base_url() -> str:
    return _cfg("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")


def text_model() -> str:
    return _cfg("LLM_MODEL", "qwen3:8b")


def vision_model() -> str:
    return _cfg("VISION_MODEL", "qwen2.5vl:7b")


def embed_model() -> str:
    return _cfg("EMBED_MODEL", "nomic-embed-text")


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").strip().lower()


def model_name(p: Optional[str] = None) -> str:
    return "mock-model-v1" if (p or provider()) == "mock" else text_model()


# --------------------------------------------------------------------------- tools
@dataclass
class Tool:
    """A tool = a name + a description the model reads + a JSON schema + a python function."""

    name: str
    description: str
    parameters: dict
    fn: Callable[..., Any]
    # Used ONLY in mock mode to pretend the model decided to call this tool.
    mock_trigger: Optional[Callable[[str], Optional[dict]]] = None


@dataclass
class AgentResult:
    text: str
    trace: list = field(default_factory=list)
    provider: str = ""
    model: str = ""
    seconds: float = 0.0


# --------------------------------------------------------------------------- helpers
def load_image(img) -> dict:
    """Accepts a path, raw bytes, or {'data': bytes, 'mime': str, 'name': str}."""
    if isinstance(img, dict):
        return img
    if isinstance(img, (bytes, bytearray)):
        return {"data": bytes(img), "mime": "image/png", "name": "upload.png"}
    p = Path(img)
    return {"data": p.read_bytes(), "mime": mimetypes.guess_type(p.name)[0] or "image/png", "name": p.name}


THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def clean(text: str) -> str:
    """Remove reasoning blocks some open models (e.g. Qwen3) emit before the answer."""
    return THINK_RE.sub("", text or "").strip()


def parse_json(text: str) -> Any:
    """Robustly pull JSON out of a model reply."""
    text = clean(text)
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s, e = text.find(open_c), text.rfind(close_c)
        if s != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except Exception:
                continue
    raise ValueError(f"Model did not return valid JSON:\n{text[:500]}")


def _post(path: str, body: dict) -> dict:
    import httpx

    headers = {"Authorization": f"Bearer {os.getenv('LLM_API_KEY', 'not-needed')}"}
    r = httpx.post(base_url() + path, json=body, headers=headers, timeout=float(os.getenv("LLM_TIMEOUT", "180")))
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} from {base_url()}{path}: {r.text[:300]}")
    return r.json()


def _user_content(prompt: str, imgs: list[dict]):
    if not imgs:
        return prompt
    parts = [{"type": "image_url", "image_url": {"url": f"data:{i['mime']};base64,{base64.b64encode(i['data']).decode()}"}} for i in imgs]
    parts.append({"type": "text", "text": prompt})
    return parts


# --------------------------------------------------------------------------- generate
def generate(
    prompt: str,
    system: Optional[str] = None,
    images: Optional[list] = None,
    schema: Optional[dict] = None,
    temperature: float = 0.2,
    mock: Optional[Callable[[], Any]] = None,
    model: Optional[str] = None,
) -> Any:
    """Single model call. Returns str, or parsed JSON when `schema` is given."""
    p = provider()
    imgs = [load_image(i) for i in (images or [])]

    if p == "mock":
        return mock() if mock else f"[mock reply] I received: {prompt[:120]}"

    if p == "local":
        text = prompt
        if schema:  # small open models follow the schema better when they also SEE it
            text += "\n\nReturn ONLY valid JSON (no prose, no code fences) matching this JSON Schema:\n" + json.dumps(schema)
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": _user_content(text, imgs)}]
        body = {"model": model or (vision_model() if imgs else text_model()), "messages": msgs, "temperature": temperature}
        if schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "output", "schema": schema}}
        try:
            out = _post("/chat/completions", body)
        except RuntimeError:
            if not schema:
                raise
            body["response_format"] = {"type": "json_object"}  # older servers: plain JSON mode
            out = _post("/chat/completions", body)
        content = out["choices"][0]["message"].get("content") or ""
        return parse_json(content) if schema else clean(content)

    raise ValueError(f"Unknown LLM_PROVIDER '{p}'. Use local or mock.")


# --------------------------------------------------------------------------- agent loop
def run_agent(
    prompt: str,
    tools: list[Tool],
    system: str = "You are a helpful automotive assistant. Use tools whenever they can give you facts.",
    max_steps: int = 6,
    mock_answer: Optional[Callable[[str, list], str]] = None,
    model: Optional[str] = None,
) -> AgentResult:
    """The classic agent loop: model -> (tool call -> tool result)* -> final answer."""
    p, t0, trace = provider(), time.time(), []
    by_name = {t.name: t for t in tools}

    def call_tool(name, args):
        try:
            result = by_name[name].fn(**(args or {}))
        except Exception as e:  # tools fail - agents must cope
            result = {"error": str(e)}
        trace.append({"type": "tool_call", "name": name, "args": args, "result": result})
        return result

    if p == "mock":
        for t in tools:
            args = t.mock_trigger(prompt) if t.mock_trigger else None
            if args is not None:
                call_tool(t.name, args)
        if mock_answer:
            text = mock_answer(prompt, trace)
        elif trace:
            text = "Based on my tools:\n" + "\n".join(f"- {s['name']}: {json.dumps(s['result'], default=str)}" for s in trace)
        else:
            text = "[mock] No tool was relevant, so this answer comes from the model's own knowledge only."
        trace.append({"type": "final", "text": text})
        return AgentResult(text, trace, p, model_name(p), time.time() - t0)

    if p == "local":
        specs = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        m = model or text_model()
        for _ in range(max_steps):
            body = {"model": m, "messages": messages, "temperature": 0.1}
            if specs:
                body["tools"] = specs
            msg = _post("/chat/completions", body)["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            if not calls:
                text = clean(msg.get("content") or "")
                trace.append({"type": "final", "text": text})
                return AgentResult(text, trace, p, m, time.time() - t0)
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for i, c in enumerate(calls):
                fn = c.get("function", {})
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args or "{}")
                    except json.JSONDecodeError:
                        args = {}
                result = call_tool(fn.get("name"), args)
                messages.append({"role": "tool", "tool_call_id": c.get("id") or f"call_{i}", "name": fn.get("name"),
                                 "content": json.dumps(result, default=str)})
        return AgentResult("Stopped: step budget exhausted.", trace, p, m, time.time() - t0)

    raise ValueError(f"Unknown LLM_PROVIDER '{p}'")


# --------------------------------------------------------------------------- embeddings
def _local_embed(text: str, dims: int = 512) -> list[float]:
    """Tiny offline embedding (hashed bag of words + bigrams). Good enough to demo retrieval."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    feats = words + [a + "_" + b for a, b in zip(words, words[1:])]
    v = [0.0] * dims
    for f in feats:
        h = int(hashlib.md5(f.encode()).hexdigest(), 16)
        v[h % dims] += 1.0 if (h >> 9) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list[str]) -> list[list[float]]:
    if provider() == "local":
        try:
            r = _post("/embeddings", {"model": embed_model(), "input": texts})
            return [d["embedding"] for d in sorted(r["data"], key=lambda d: d.get("index", 0))]
        except Exception as e:  # fall back so the lab never blocks
            print(f"[embed] server embeddings failed ({e}); using local embeddings")
    return [_local_embed(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
