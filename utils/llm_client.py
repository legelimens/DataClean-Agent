from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple


def llm_strategy_enabled() -> bool:
    """Read feature switch from env, default OFF to keep local demo stable."""
    value = os.getenv("DATACLEAN_ENABLE_LLM", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _extract_text_from_responses_api(payload: Dict) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    output = payload.get("output", [])
    chunks = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                text = c.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _extract_text_from_chat_completions(payload: Dict) -> str:
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""


def _post_json(url: str, body: Dict, api_key: str, timeout: int = 30) -> Dict:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize_chat_endpoint(base_or_full: str) -> str:
    raw = base_or_full.strip().rstrip("/")
    if raw.endswith("/chat/completions"):
        return raw
    if raw.endswith("/v1"):
        return raw + "/chat/completions"
    return raw + "/chat/completions"


def _normalize_responses_endpoint(base_or_full: str) -> str:
    raw = base_or_full.strip().rstrip("/")
    if raw.endswith("/responses"):
        return raw
    if raw.endswith("/v1"):
        return raw + "/responses"
    return raw + "/responses"


def _resolve_provider_and_config() -> Tuple[str, str, str, str]:
    """
    Returns: provider, api_key, api_url, model
    provider: auto/openai/qwen
    """
    provider = os.getenv("DATACLEAN_PROVIDER", "auto").strip().lower()
    api_key = os.getenv("DATACLEAN_API_KEY", "").strip() or os.getenv("DASHSCOPE_API_KEY", "").strip()
    api_url = os.getenv("DATACLEAN_API_URL", "").strip()
    model = os.getenv("DATACLEAN_MODEL", "gpt-4.1-mini").strip()

    if not api_url:
        if provider == "qwen":
            api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        else:
            api_url = "https://api.openai.com/v1/responses"

    if provider == "auto":
        url_lower = api_url.lower()
        if "dashscope" in url_lower or model.lower().startswith("qwen"):
            provider = "qwen"
        else:
            provider = "openai"

    return provider, api_key, api_url, model


def generate_strategy_advice(issue_counts: Dict) -> Optional[str]:
    """
    Generate short strategy advice.

    OpenAI-compatible env:
    - DATACLEAN_ENABLE_LLM=1
    - DATACLEAN_API_KEY
    - DATACLEAN_API_URL (optional)
    - DATACLEAN_MODEL (optional)
    - DATACLEAN_PROVIDER=auto/openai/qwen (optional)

    Qwen supports DASHSCOPE key fallback:
    - DASHSCOPE_API_KEY
    """
    provider, api_key, api_url, model = _resolve_provider_and_config()
    if not api_key:
        return None

    prompt = (
        "你是企业数据治理顾问。基于以下订单数据质量问题统计，"
        "请给出 3 条精炼、可执行的清洗优化建议，每条不超过 30 字：\n"
        f"{json.dumps(issue_counts, ensure_ascii=False)}"
    )

    try:
        if provider == "qwen":
            endpoint = _normalize_chat_endpoint(api_url)
            body = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
            payload = _post_json(endpoint, body, api_key=api_key)
            text = _extract_text_from_chat_completions(payload)
            return text if text else None

        # OpenAI path (or other Responses-compatible providers)
        responses_endpoint = _normalize_responses_endpoint(api_url)
        body = {
            "model": model,
            "input": [{"role": "user", "content": prompt}],
        }
        try:
            payload = _post_json(responses_endpoint, body, api_key=api_key)
            text = _extract_text_from_responses_api(payload)
            if text:
                return text
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
            # fallback to chat completions for compatibility
            pass

        chat_endpoint = _normalize_chat_endpoint(api_url)
        chat_body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        payload = _post_json(chat_endpoint, chat_body, api_key=api_key)
        text = _extract_text_from_chat_completions(payload)
        return text if text else None
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None

