from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass
from typing import List, Optional, Sequence

import httpx

from snow_day.services.scoring import ScoreResult


@dataclass
class ScoredResort:
    """Represents a resort and its computed score."""

    name: str
    score: float
    rationale: str

    @classmethod
    def from_result(cls, name: str, result: ScoreResult) -> "ScoredResort":
        return cls(name=name, score=result.score, rationale=result.rationale)


class RuleBasedAdvisor:
    """Fallback generator that uses scores directly when the LLM is unavailable."""

    def summarize_top_resorts(self, resorts: Sequence[ScoredResort], top_n: int = 3) -> str:
        if not resorts:
            return "No resort scores are available to summarize yet."

        sorted_resorts = sorted(resorts, key=lambda resort: resort.score, reverse=True)
        picks = sorted_resorts[:top_n]
        lines = ["Top resort highlights:"]
        for resort in picks:
            lines.append(f"- {resort.name} ({resort.score:.1f}): {resort.rationale}")
        if len(sorted_resorts) > len(picks):
            remaining = len(sorted_resorts) - len(picks)
            lines.append(f"...and {remaining} more resorts ranked after the top {top_n}.")
        return "\n".join(lines)

    def daily_recommendation(self, resorts: Sequence[ScoredResort]) -> str:
        if not resorts:
            return "No resort data is available to recommend a destination today."

        sorted_resorts = sorted(resorts, key=lambda resort: resort.score, reverse=True)
        best = sorted_resorts[0]
        alternates = sorted_resorts[1:3]

        lines = [
            f"Best option: {best.name} leads with a {best.score:.1f} score thanks to {best.rationale}.",
        ]
        if alternates:
            alt_lines = "; ".join(
                f"{resort.name} ({resort.score:.1f})" for resort in alternates
            )
            lines.append(f"Consider these backups if you want variety: {alt_lines}.")
        return "\n".join(lines)


class LLMClient:
    """Client wrapper for a local Ollama-compatible LLM server."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        model: str = "phi3",
        timeout: float = 8.0,
        client: Optional[httpx.Client] = None,
        fallback: Optional[RuleBasedAdvisor] = None,
    ) -> None:
        resolved_base_url = base_url or os.getenv("SNOWDAY_LLM_URL", "http://localhost:11434")
        self.base_url = resolved_base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=timeout)
        self.fallback = fallback or RuleBasedAdvisor()

    def summarize_top_resorts(self, resorts: Sequence[ScoredResort], top_n: int = 3) -> str:
        prompt = self._summary_prompt(resorts, top_n=top_n)
        output = self._generate(prompt)
        if output:
            return output
        return self.fallback.summarize_top_resorts(resorts, top_n=top_n)

    def daily_recommendation(self, resorts: Sequence[ScoredResort]) -> str:
        prompt = self._recommendation_prompt(resorts)
        output = self._generate(prompt)
        if output:
            return output
        return self.fallback.daily_recommendation(resorts)

    def _generate(self, prompt: str) -> str:
        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("response", "")
            return result.strip()
        except (httpx.TimeoutException, httpx.HTTPError, ValueError):
            # Fail gracefully to the rule-based backup when the LLM is unreachable.
            return ""

    def _summary_prompt(self, resorts: Sequence[ScoredResort], *, top_n: int) -> str:
        formatted_rows = self._format_resorts(resorts)
        return textwrap.dedent(
            f"""
            You are an enthusiastic ski trip planner.
            Use the scoring table below to recommend the top {top_n} resorts. Summarize
            the headline reasons in two short paragraphs and include a bulleted list of
            the top picks with their scores.

            Resort scores:
            {formatted_rows}

            Keep the tone concise and actionable.
            """
        ).strip()

    def _recommendation_prompt(self, resorts: Sequence[ScoredResort]) -> str:
        formatted_rows = self._format_resorts(resorts)
        return textwrap.dedent(
            f"""
            You create a single daily ski recommendation using the scoring table.
            Highlight the strongest destination and mention up to two alternates with
            one line each. Avoid repeating the numeric rationale verbatim.

            Resort scores:
            {formatted_rows}

            Return 3-6 sentences focused on today's best call to action.
            """
        ).strip()

    @staticmethod
    def _format_resorts(resorts: Sequence[ScoredResort]) -> str:
        if not resorts:
            return "(no resort scores provided)"
        lines: List[str] = []
        for resort in sorted(resorts, key=lambda resort: resort.score, reverse=True):
            lines.append(f"- {resort.name}: score={resort.score:.1f} | {resort.rationale}")
        return "\n".join(lines)


__all__ = ["LLMClient", "RuleBasedAdvisor", "ScoredResort"]
