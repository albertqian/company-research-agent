"""Shared plumbing for every sub-agent: Claude call, JSON parsing, usage math."""
import json
import re

import anthropic

import config

JSON_ONLY = "Return ONLY one JSON object wrapped in <json></json> tags, no other prose."


class AgentError(Exception):
    pass


def new_usage() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "searches": 0}


def add_usage(*usages: dict) -> dict:
    total = new_usage()
    for u in usages:
        for k in total:
            total[k] += u.get(k, 0)
    return total


def cost_of(usage: dict) -> float:
    return (
        usage["input_tokens"] / 1e6 * config.PRICE_INPUT_PER_M
        + usage["output_tokens"] / 1e6 * config.PRICE_OUTPUT_PER_M
        + usage["searches"] * config.PRICE_PER_SEARCH
    )


def run_claude(api_key: str, agent: str, system: str, prompt: str,
               max_searches: int = 0) -> tuple[str, dict]:
    """Call Claude for one sub-agent. Web search is enabled only if max_searches > 0."""
    client = anthropic.Anthropic(api_key=api_key, max_retries=3)
    messages = [{"role": "user", "content": prompt}]
    kwargs = {}
    if max_searches > 0:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}]
    usage = new_usage()

    for _ in range(4):  # pause_turn continuations
        try:
            resp = client.messages.create(
                model=config.AGENT_MODELS.get(agent, config.DEFAULT_MODEL),
                max_tokens=config.MAX_OUTPUT_TOKENS,
                system=f"{system} {JSON_ONLY}",
                messages=messages,
                **kwargs,
            )
        except anthropic.APIError as e:
            raise AgentError(f"{agent}: Claude API error: {e}") from e

        usage["input_tokens"] += resp.usage.input_tokens or 0
        usage["output_tokens"] += resp.usage.output_tokens or 0
        stu = getattr(resp.usage, "server_tool_use", None)
        if stu is not None:
            usage["searches"] += getattr(stu, "web_search_requests", 0) or 0

        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        return "".join(b.text for b in resp.content if b.type == "text"), usage

    raise AgentError(f"{agent}: Claude did not finish. Try again.")


def parse_json(text: str, agent: str) -> dict:
    m = re.search(r"<json>(.*?)</json>", text, re.DOTALL)
    raw = (m.group(1) if m else text).strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    start = raw.find("{")
    if start == -1:
        raise AgentError(f"{agent}: no JSON returned. Try again.")
    raw = raw[start:]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = json.loads(raw[: raw.rfind("}") + 1])
        except json.JSONDecodeError as e:
            raise AgentError(f"{agent}: could not read response ({e}).") from e
    if not isinstance(data, dict):
        raise AgentError(f"{agent}: unexpected response shape.")
    return data


def profile_text(profile: dict) -> str:
    """Compact profile string passed to every downstream sub-agent instead of the full resume."""
    return json.dumps(profile, ensure_ascii=False, separators=(",", ":"))
