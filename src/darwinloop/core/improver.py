"""darwinloop core/improver.py — LLM-driven self-improvement pipeline."""

from __future__ import annotations

import functools
import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from darwinloop.tools.bash_tool import BASH_TOOL, bash_tool
from darwinloop.tools.edit_tool import EDIT_TOOL, editor_tool

logger = logging.getLogger(__name__)

_TOOLS = [BASH_TOOL, EDIT_TOOL]

# ── Prompts ───────────────────────────────────────────────────────────────────

_DIAGNOSIS_PROMPT = """\
# Agent Self-Improvement Analysis

You are analysing an agent's source code and benchmark results.

## Agent Source Code
```python
{agent_code}
```

## Benchmark Results (what failed and why)
{eval_logs}

## Failed Tasks
{failed_tasks}

## Your Task
Identify ONE high-impact improvement to this agent's behaviour.

Focus on:
1. Logic gaps — cases it handles wrong or misses entirely
2. Missing keywords / patterns it should recognise
3. Context handling — does it correctly use session state?
4. Edge cases — abbreviations, typos, ambiguous phrasing

Do NOT suggest:
- Infrastructure changes (APIs, databases, Docker)
- Changes unrelated to the failing benchmark cases
- Prompt-only changes without code changes

Respond ONLY with valid JSON (no markdown fences):
{{
  "log_analysis": "What failed and why",
  "potential_improvements": ["option1", "option2", "option3"],
  "chosen_improvement": "The single highest-impact fix",
  "implementation_hint": "Exactly what code to add/change and where",
  "github_issue_description": "A clear description a developer could implement"
}}
"""

_IMPLEMENTATION_PROMPT = """\
You are implementing a specific improvement to a Python agent.

## Current Agent Source Code
```python
{agent_code}
```

## Improvement to Implement
**Issue**: {github_issue_description}

**What to change**: {implementation_hint}

## Instructions
1. Read the current source code carefully using the editor 'view' command.
2. Implement EXACTLY the improvement described — nothing more, nothing less.
3. Use the editor 'str_replace' command for precise, surgical changes.
4. After making the change, verify with 'view' that the file looks correct.
5. The file must remain syntactically valid Python.

When done, respond with: "Implementation complete."
"""


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class ImprovementProposal:
    """A diagnosed and proposed code improvement.

    Attributes:
        log_analysis: LLM's analysis of what failed and why.
        potential_improvements: Alternative improvements considered.
        chosen_improvement: The single chosen improvement.
        implementation_hint: Precise implementation guidance.
        github_issue_description: Issue description used in the implementation prompt.
        target_filename: Filename of the code being improved.
    """

    log_analysis: str
    potential_improvements: list[str]
    chosen_improvement: str
    implementation_hint: str
    github_issue_description: str
    target_filename: str = "agent.py"


# ── Self-improver ─────────────────────────────────────────────────────────────

class SelfImprover:
    """Orchestrates the two-step LLM-driven improvement cycle.

    Step 1 — **Diagnose**: LLM analyses code + benchmark failures → structured proposal.
    Step 2 — **Implement**: LLM uses editor/bash tools to apply the change.

    Args:
        llm_client: A :class:`~darwinloop.llm.client.LLMClient` or
            :class:`~darwinloop.llm.client.MockLLMClient`.
        target_filename: Filename of the agent code being evolved (e.g. ``"router.py"``).
    """

    def __init__(self, llm_client: object, target_filename: str = "agent.py") -> None:
        self.llm = llm_client
        self.target_filename = target_filename

    def propose(
        self,
        agent_code: str,
        eval_logs: list[str],
        failed_tasks: list[dict],
    ) -> ImprovementProposal:
        """Step 1: Diagnose failures and propose one improvement.

        Args:
            agent_code: Current source code of the agent.
            eval_logs: Log lines from the benchmark run.
            failed_tasks: Failed task dicts from :class:`~darwinloop.core.benchmark.BenchmarkResult`.

        Returns:
            :class:`ImprovementProposal`.
        """
        prompt = _DIAGNOSIS_PROMPT.format(
            agent_code=agent_code,
            eval_logs="\n".join(eval_logs) if eval_logs else "No logs.",
            failed_tasks=json.dumps(failed_tasks, indent=2) if failed_tasks else "[]",
        )
        history = self.llm.chat_with_tools(  # type: ignore[union-attr]
            instruction=prompt,
            tools=[],
            tool_functions={},
            logging_fn=lambda m: logger.debug(m),
        )
        raw = _last_text(history)
        proposal = _parse_proposal(raw)
        proposal.target_filename = self.target_filename
        return proposal

    def implement(
        self,
        parent_code: str,
        proposal: ImprovementProposal,
    ) -> str:
        """Step 2: Apply the proposed improvement and return the new code.

        Writes *parent_code* to a temp sandbox, lets the LLM edit it using
        the bash and editor tools, then reads back the result.

        Args:
            parent_code: Current source code.
            proposal: The :class:`ImprovementProposal` to implement.

        Returns:
            New source code (unchanged *parent_code* if implementation failed).
        """
        sandbox = Path(tempfile.gettempdir()) / f"darwinloop_impl_{uuid.uuid4().hex[:8]}"
        sandbox.mkdir(parents=True, exist_ok=True)
        target = sandbox / proposal.target_filename

        try:
            target.write_text(parent_code, encoding="utf-8")

            prompt = _IMPLEMENTATION_PROMPT.format(
                agent_code=parent_code,
                github_issue_description=proposal.github_issue_description,
                implementation_hint=proposal.implementation_hint,
            )

            bound_tools = _bind(
                {
                    "bash": bash_tool,
                    "editor": editor_tool,
                },
                cwd=str(sandbox),
            )

            self.llm.chat_with_tools(  # type: ignore[union-attr]
                instruction=prompt,
                tools=_TOOLS,
                tool_functions=bound_tools,
                logging_fn=lambda m: logger.info(m),
            )

            return target.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Implementation failed: %s", exc)
            return parent_code
        finally:
            import shutil
            shutil.rmtree(sandbox, ignore_errors=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _last_text(history: list[dict]) -> str:
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block["text"]
            elif isinstance(content, str):
                return content
    return ""


def _parse_proposal(raw: str) -> ImprovementProposal:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        try:
            data = json.loads(m.group()) if m else {}
        except json.JSONDecodeError:
            data = {}
    return ImprovementProposal(
        log_analysis=data.get("log_analysis", "Could not parse analysis."),
        potential_improvements=data.get("potential_improvements", []),
        chosen_improvement=data.get("chosen_improvement", "Unknown improvement"),
        implementation_hint=data.get("implementation_hint", "No hint."),
        github_issue_description=data.get(
            "github_issue_description", data.get("chosen_improvement", "Unnamed")
        ),
    )


def _bind(tool_functions: dict[str, Callable], cwd: str) -> dict[str, Callable]:
    """Bind tool functions to a specific sandbox directory."""
    bound: dict[str, Callable] = {}
    for name, fn in tool_functions.items():
        if name == "bash":
            @functools.wraps(fn)
            def _bash(command: str, _fn: Callable = fn, _cwd: str = cwd) -> str:
                return _fn(command=command, cwd=_cwd)
            bound[name] = _bash
        elif name == "editor":
            @functools.wraps(fn)
            def _editor(_fn: Callable = fn, _cwd: str = cwd, **kwargs: object) -> str:
                path = str(kwargs.get("path", ""))
                if path and not os.path.isabs(path):
                    kwargs["path"] = os.path.join(_cwd, path)
                kwargs["cwd"] = _cwd
                return _fn(**kwargs)
            bound[name] = _editor
        else:
            bound[name] = fn
    return bound
