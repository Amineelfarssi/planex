"""Planex configuration — read, write, detect, test.

Central module for all config I/O.  Reads/writes ~/.planex/.env and
provides detection logic and connection testing for the Settings UI.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

PLANEX_DIR = Path.home() / ".planex"
ENV_FILE = PLANEX_DIR / ".env"

# Keys we manage in the .env file
_CONFIG_KEYS = [
    "PLANEX_PROVIDER",
    "OPENAI_API_KEY",
    "AWS_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "PLANEX_USER_NAME",
    "PLANEX_FAST_MODEL",
    "PLANEX_SMART_MODEL",
    "PLANEX_STRATEGIC_MODEL",
    "PLANEX_EMBEDDING_MODEL",
]

_SECRET_KEYS = {"OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY"}


def mask_key(value: str) -> str:
    """Mask a secret value for display: 'sk-abc...xyz'."""
    if not value or len(value) < 8:
        return "***" if value else ""
    return value[:6] + "..." + value[-4:]


def _read_env_file() -> dict[str, str]:
    """Parse ~/.planex/.env into a dict."""
    result: dict[str, str] = {}
    if not ENV_FILE.exists():
        return result
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key:
            result[key] = val
    return result


def _write_env_file(data: dict[str, str]) -> None:
    """Write config dict to ~/.planex/.env, preserving unknown keys."""
    PLANEX_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in ("memory", "sources", "outputs", "sessions"):
        (PLANEX_DIR / subdir).mkdir(exist_ok=True)

    existing = _read_env_file()
    existing.update(data)
    # Remove empty values
    existing = {k: v for k, v in existing.items() if v}

    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")


def detect_provider() -> dict:
    """Detect which provider would be used and why."""
    explicit = os.environ.get("PLANEX_PROVIDER", "").lower()
    if explicit == "bedrock":
        return {"provider": "bedrock", "reason": "PLANEX_PROVIDER=bedrock"}
    if explicit == "openai":
        return {"provider": "openai", "reason": "PLANEX_PROVIDER=openai"}

    if os.environ.get("OPENAI_API_KEY"):
        return {"provider": "openai", "reason": "OPENAI_API_KEY found in environment"}

    region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
    sagemaker = os.environ.get("SAGEMAKER_APP_TYPE")
    if region or sagemaker:
        reasons = []
        if sagemaker:
            reasons.append(f"SAGEMAKER_APP_TYPE={sagemaker}")
        if region:
            reasons.append(f"AWS_REGION={region}")
        return {"provider": "bedrock", "reason": "AWS environment detected: " + ", ".join(reasons)}

    return {"provider": "none", "reason": "No provider configured (no API key or AWS environment)"}


def get_config() -> dict:
    """Return current config with masked secrets."""
    env_data = _read_env_file()
    detection = detect_provider()

    config: dict = {}
    for key in _CONFIG_KEYS:
        val = os.environ.get(key, "") or env_data.get(key, "")
        if key in _SECRET_KEYS and val:
            config[key] = mask_key(val)
        else:
            config[key] = val

    config["_detected"] = detection
    return config


def save_config(data: dict) -> None:
    """Save config from the frontend, update os.environ, write .env file."""
    env_updates: dict[str, str] = {}
    for key in _CONFIG_KEYS:
        if key in data:
            val = data[key]
            # Don't overwrite secrets with masked values
            if key in _SECRET_KEYS and val and "..." in val:
                continue
            env_updates[key] = val
            if val:
                os.environ[key] = val
            elif key in os.environ:
                del os.environ[key]

    _write_env_file(env_updates)


async def test_connection(provider: str, **creds) -> dict:
    """Test a provider connection without saving config.

    Temporarily sets env vars, creates a provider, makes a lightweight call,
    then restores the original env.
    """
    # Save and temporarily set env vars
    saved = {}
    temp_vars = {}
    if provider == "openai":
        temp_vars["OPENAI_API_KEY"] = creds.get("OPENAI_API_KEY", "")
    elif provider == "bedrock":
        if creds.get("AWS_REGION"):
            temp_vars["AWS_REGION"] = creds["AWS_REGION"]
        if creds.get("AWS_ACCESS_KEY_ID"):
            temp_vars["AWS_ACCESS_KEY_ID"] = creds["AWS_ACCESS_KEY_ID"]
        if creds.get("AWS_SECRET_ACCESS_KEY"):
            temp_vars["AWS_SECRET_ACCESS_KEY"] = creds["AWS_SECRET_ACCESS_KEY"]

    for k, v in temp_vars.items():
        saved[k] = os.environ.get(k)
        if v:
            os.environ[k] = v

    try:
        if provider == "openai":
            from core.llm import OpenAIProvider
            llm = OpenAIProvider()
        elif provider == "bedrock":
            from core.llm_bedrock import BedrockAnthropicProvider
            llm = BedrockAnthropicProvider()
        else:
            return {"ok": False, "error": f"Unknown provider: {provider}"}

        resp = await llm.chat(
            messages=[{"role": "user", "content": "Say 'ok' in one word."}],
            tools=None,
            tier="fast",
        )
        if resp.content:
            return {"ok": True, "response": resp.content[:100]}
        return {"ok": False, "error": "Empty response from model"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        # Restore original env
        for k, orig in saved.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig


def get_health() -> dict:
    """Build health response with provider info and needs_setup flag."""
    detection = detect_provider()
    provider = detection["provider"]
    needs_setup = provider == "none"

    models = {}
    if provider == "bedrock":
        try:
            from core.llm_bedrock import _tier_default
            models = {
                "fast": os.environ.get("PLANEX_FAST_MODEL", "") or _tier_default("fast"),
                "smart": os.environ.get("PLANEX_SMART_MODEL", "") or _tier_default("smart"),
                "strategic": os.environ.get("PLANEX_STRATEGIC_MODEL", "") or _tier_default("strategic"),
            }
        except Exception:
            pass
    elif provider == "openai":
        from core.llm import _TIER_DEFAULT
        models = {
            "fast": os.environ.get("PLANEX_FAST_MODEL", "") or _TIER_DEFAULT.get("fast", ""),
            "smart": os.environ.get("PLANEX_SMART_MODEL", "") or _TIER_DEFAULT.get("smart", ""),
            "strategic": os.environ.get("PLANEX_STRATEGIC_MODEL", "") or _TIER_DEFAULT.get("strategic", ""),
        }

    provider_name = {
        "openai": "OpenAI",
        "bedrock": "AWS Bedrock",
        "none": "Not configured",
    }.get(provider, provider)

    return {
        "status": "ok" if not needs_setup else "needs_setup",
        "service": "planex",
        "version": "0.1.0",
        "provider": provider,
        "provider_name": provider_name,
        "models": models,
        "needs_setup": needs_setup,
        "auto_detected": detection,
    }
