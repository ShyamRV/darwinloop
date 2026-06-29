"""darwinloop llm/client.py — Unified LLM client with agentic tool-use loop."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── Message helpers ───────────────────────────────────────────────────────────

def _user(content: Any) -> dict:
    return {"role": "user", "content": content}


def _assistant(content: Any) -> dict:
    return {"role": "assistant", "content": content}


# ── Mock client (dry-run, zero cost) ─────────────────────────────────────────

class MockLLMClient:
    """Deterministic mock LLM for ``--dry-run`` mode.

    Cycles through a fixed set of realistic improvement proposals so the full
    darwinloop pipeline can be exercised without any API key or cost.
    """

    _PROPOSALS = [
        {
            "log_analysis": "Agent overwrites entire files on each edit, losing surrounding context.",
            "potential_improvements": ["Add str_replace for precise edits", "Add line-range view"],
            "chosen_improvement": "Add str_replace to editor tool for surgical code modifications",
            "implementation_hint": "Add a 'str_replace' command that finds unique text and replaces it.",
            "github_issue_description": "Add str_replace to editor tool for surgical code modifications",
        },
        {
            "log_analysis": "Agent views entire files even when only a small section is relevant.",
            "potential_improvements": ["Add view_range parameter", "Add grep-like search"],
            "chosen_improvement": "Add view_range=[start, end] to editor view command",
            "implementation_hint": "Modify _view() to accept optional view_range and slice the line list.",
            "github_issue_description": "Add view_range to editor view command to reduce context usage",
        },
        {
            "log_analysis": "Agent gives up after the first failed attempt.",
            "potential_improvements": ["Add retry logic", "Add exponential backoff"],
            "chosen_improvement": "Add retry loop (max 3 attempts) when initial solution fails",
            "implementation_hint": "Wrap the main solve loop in a for-loop with max_retries=3.",
            "github_issue_description": "Add retry logic: attempt up to 3 solutions before giving up",
        },
        {
            "log_analysis": "Agent generates one solution and submits it; ranking alternatives improves quality.",
            "potential_improvements": ["Generate N candidates and pick best", "Self-consistency voting"],
            "chosen_improvement": "Generate 3 candidate solutions and select the one that passes most tests",
            "implementation_hint": "Generate N=3 solutions, run quick tests on each, return the best.",
            "github_issue_description": "Add multi-candidate generation with best-of-N selection",
        },
    ]

    _call_count = 0

    def chat_with_tools(
        self,
        instruction: str,
        tools: list[dict],
        tool_functions: dict[str, Callable],
        model: str = "mock",
        msg_history: list[dict] | None = None,
        max_turns: int = 50,
        logging_fn: Callable = print,
    ) -> list[dict]:
        idx = min(MockLLMClient._call_count, len(self._PROPOSALS) - 1)
        MockLLMClient._call_count += 1
        proposal = self._PROPOSALS[idx]
        text = (
            f"[MOCK] Analysis complete.\n\n"
            f"**Chosen improvement**: {proposal['chosen_improvement']}\n\n"
            f"```json\n{json.dumps(proposal, indent=2)}\n```"
        )
        history = list(msg_history or [])
        history.append(_user(instruction))
        history.append(_assistant(text))
        return history


# ── Real LLM client ───────────────────────────────────────────────────────────

class LLMClient:
    """Unified LLM client supporting ASI:One, Anthropic Claude, and OpenAI GPT.

    Runs an agentic tool-use loop: calls the LLM repeatedly until it returns
    a text-only response (no more tool calls). Handles context overflow by
    summarising older messages and retrying.

    Args:
        api_key: API key for the provider.
        provider: One of ``"asi1"``, ``"anthropic"``, ``"openai"``.
        model: Model name override. Defaults to provider-specific default.
        base_url: Custom base URL (required for ASI:One).
    """

    _DEFAULTS = {
        "asi1": "asi1",
        "anthropic": "claude-3-5-sonnet-20241022",
        "openai": "gpt-4o",
    }

    def __init__(
        self,
        api_key: str,
        provider: str = "asi1",
        model: str = "",
        base_url: str = "",
    ) -> None:
        self.provider = provider
        self.default_model = model or self._DEFAULTS.get(provider, "gpt-4o")

        if provider in ("asi1", "openai"):
            try:
                import openai as _openai
            except ImportError:
                raise ImportError("Run: pip install openai")
            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            elif provider == "asi1":
                kwargs["base_url"] = "https://api.asi1.ai/v1"
            self._client = _openai.OpenAI(**kwargs)

        elif provider == "anthropic":
            try:
                import anthropic as _anthropic
            except ImportError:
                raise ImportError("Run: pip install anthropic")
            self._client = _anthropic.Anthropic(api_key=api_key)

        else:
            raise ValueError(f"Unknown provider: {provider!r}. Choose 'asi1', 'anthropic', or 'openai'.")

    def chat_with_tools(
        self,
        instruction: str,
        tools: list[dict],
        tool_functions: dict[str, Callable],
        model: str = "",
        msg_history: list[dict] | None = None,
        max_turns: int = 10,
        logging_fn: Callable = print,
    ) -> list[dict]:
        """Run the agentic tool-use loop.

        Keeps calling the LLM until it produces a text-only response (no more
        tool calls), then returns the full message history.

        Args:
            instruction: The initial user prompt.
            tools: List of tool descriptors in Anthropic schema format.
            tool_functions: ``{tool_name: callable}`` mapping.
            model: Override the default model for this call.
            msg_history: Existing message history to prepend.
            max_turns: Maximum tool-call rounds before stopping.
            logging_fn: Callable for progress logging (default ``print``).

        Returns:
            Full message history including all turns.
        """
        resolved_model = model or self.default_model
        messages = list(msg_history or [])
        messages.append(_user(instruction))

        for turn in range(max_turns):
            logging_fn(f"  [LLM turn {turn + 1}/{max_turns}]")
            try:
                content = self._call(resolved_model, messages, tools)
            except Exception as exc:
                err = str(exc)
                if "too long" in err.lower() or "context" in err.lower() or "tokens" in err.lower():
                    logging_fn("  [context overflow] Summarising older messages…")
                    messages = self._summarise(messages, resolved_model)
                    content = self._call(resolved_model, messages, tools)
                else:
                    raise

            messages.append(_assistant(content))

            tool_uses = (
                [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                if isinstance(content, list)
                else []
            )

            if not tool_uses:
                break

            results = []
            for tu in tool_uses:
                name = tu.get("name", "")
                inp = tu.get("input", {})
                tid = tu.get("id", "")
                logging_fn(f"    → {name}({list(inp.keys())})")
                fn = tool_functions.get(name)
                try:
                    out = fn(**inp) if fn else f"Error: unknown tool '{name}'"
                except Exception as exc:
                    out = f"Error calling '{name}': {exc}"
                short = str(out)[:200]
                logging_fn(f"    ← {short}{'…' if len(str(out)) > 200 else ''}")
                results.append({"type": "tool_result", "tool_use_id": tid, "content": str(out)})

            messages.append(_user(results))

        return messages

    # ── Internal ──────────────────────────────────────────────────────────────

    def _call(self, model: str, messages: list[dict], tools: list[dict]) -> Any:
        if self.provider == "anthropic":
            import anthropic
            normed = _norm_anthropic(messages)
            resp = self._client.messages.create(  # type: ignore[union-attr]
                model=model, max_tokens=8096, tools=tools, messages=normed
            )
            return [_block_to_dict(b) for b in resp.content]

        # openai / asi1
        oai_tools = _to_openai_tools(tools)
        normed = _norm_openai(messages)
        resp = self._client.chat.completions.create(  # type: ignore[union-attr]
            model=model,
            messages=normed,
            **({"tools": oai_tools} if oai_tools else {}),
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            return [
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]
        return [{"type": "text", "text": msg.content or ""}]

    def _summarise(self, messages: list[dict], model: str) -> list[dict]:
        if len(messages) <= 4:
            return messages
        recent = messages[-2:]
        older = messages[:-2]
        summary_prompt = (
            "Summarise the following conversation history. Preserve key decisions, "
            "code changes, and error messages:\n\n"
            + "\n".join(f"[{m['role']}]: {str(m['content'])[:800]}" for m in older)
        )
        try:
            content = self._call(model, [_user(summary_prompt)], [])
            summary = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        except Exception:
            summary = "[Earlier context truncated]"
        return [_user(f"[Context summary]:\n{summary}")] + recent


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _norm_anthropic(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        c = m["content"]
        out.append({"role": m["role"], "content": c if isinstance(c, (str, list)) else str(c)})
    return out


def _norm_openai(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        c = m["content"]
        if isinstance(c, list):
            text = " ".join(
                (item.get("content", "") if isinstance(item, dict) else str(item))
                for item in c
            )
            out.append({"role": m["role"], "content": text})
        else:
            out.append({"role": m["role"], "content": str(c)})
    return out


def _block_to_dict(block: Any) -> dict:
    if hasattr(block, "type"):
        if block.type == "text":
            return {"type": "text", "text": block.text}
        if block.type == "tool_use":
            return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": "unknown", "raw": str(block)}


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        }
        for t in tools
    ]


# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm_client(
    dry_run: bool = False,
    provider: str = "",
    api_key: str = "",
    model: str = "",
    base_url: str = "",
) -> "LLMClient | MockLLMClient":
    """Return the appropriate LLM client.

    Provider priority (when *provider* is not explicitly set):

    1. ``ASI1_API_KEY`` in environment → ASI:One (OpenAI-compatible)
    2. ``ANTHROPIC_API_KEY`` → Anthropic Claude
    3. ``OPENAI_API_KEY`` → OpenAI GPT
    4. None found → raise :class:`EnvironmentError` (or use ``dry_run=True``)

    Args:
        dry_run: Return a :class:`MockLLMClient` (free, no key needed).
        provider: Explicit provider override (``"asi1"``, ``"anthropic"``, ``"openai"``).
        api_key: API key override.
        model: Model name override.
        base_url: Base URL override (for self-hosted endpoints).

    Returns:
        :class:`LLMClient` or :class:`MockLLMClient`.
    """
    if dry_run:
        return MockLLMClient()

    # Auto-detect from environment
    if not provider:
        if os.getenv("ASI1_API_KEY", "").strip():
            provider = "asi1"
        elif os.getenv("ANTHROPIC_API_KEY", "").strip():
            provider = "anthropic"
        elif os.getenv("OPENAI_API_KEY", "").strip():
            provider = "openai"
        else:
            raise EnvironmentError(
                "No LLM API key found. Set ASI1_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY, "
                "or pass dry_run=True for a free mock simulation.\n"
                "Get an ASI:One key at https://asi1.ai"
            )

    resolved_key = api_key or {
        "asi1": os.getenv("ASI1_API_KEY", ""),
        "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
    }.get(provider, "")

    resolved_url = base_url or (
        os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1") if provider == "asi1" else ""
    )

    return LLMClient(
        api_key=resolved_key,
        provider=provider,
        model=model,
        base_url=resolved_url,
    )
