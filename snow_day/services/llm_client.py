from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass
from typing import List, Optional, Sequence

import httpx

from snow_day.services.scoring import ScoreResult


@dataclass
class ScoredResort:
    """Represents a resort and its computed score with condition details."""

    name: str
    score: float
    rationale: str
    # Condition details for LLM context
    snowfall_24h: Optional[float] = None
    snowfall_12h: Optional[float] = None
    base_depth: Optional[float] = None
    wind_speed: Optional[float] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    precip_type: Optional[str] = None
    powder: bool = False
    icy: bool = False
    is_operational: Optional[bool] = None
    lifts_open: Optional[int] = None
    lifts_total: Optional[int] = None
    trails_open: Optional[int] = None
    trails_total: Optional[int] = None

    @classmethod
    def from_result(
        cls,
        name: str,
        result: ScoreResult,
        *,
        snowfall_24h: Optional[float] = None,
        snowfall_12h: Optional[float] = None,
        base_depth: Optional[float] = None,
        wind_speed: Optional[float] = None,
        temp_min: Optional[float] = None,
        temp_max: Optional[float] = None,
        precip_type: Optional[str] = None,
        is_operational: Optional[bool] = None,
        lifts_open: Optional[int] = None,
        lifts_total: Optional[int] = None,
        trails_open: Optional[int] = None,
        trails_total: Optional[int] = None,
    ) -> "ScoredResort":
        return cls(
            name=name,
            score=result.score,
            rationale=result.rationale,
            snowfall_24h=snowfall_24h,
            snowfall_12h=snowfall_12h,
            base_depth=base_depth,
            wind_speed=wind_speed,
            temp_min=temp_min,
            temp_max=temp_max,
            precip_type=precip_type,
            powder=result.powder,
            icy=result.icy,
            is_operational=is_operational,
            lifts_open=lifts_open,
            lifts_total=lifts_total,
            trails_open=trails_open,
            trails_total=trails_total,
        )


class RuleBasedAdvisor:
    """Fallback generator that uses scores directly when the LLM is unavailable."""

    def summarize_top_resorts(self, resorts: Sequence[ScoredResort], top_n: int = 3) -> str:
        if not resorts:
            return "No resort scores are available to summarize yet."

        sorted_resorts = sorted(resorts, key=lambda resort: resort.score, reverse=True)
        picks = sorted_resorts[:top_n]
        
        # Build concise, review-style recommendations
        lines = []
        
        for resort in picks:
            # Get key highlights (max 2)
            highlights = []
            if resort.powder:
                highlights.append("powder")
            if resort.snowfall_24h and resort.snowfall_24h > 0:
                highlights.append(f"{resort.snowfall_24h:.1f}\" fresh")
            if resort.wind_speed is not None and resort.wind_speed < 15:
                highlights.append("calm winds")
            if resort.trails_open and resort.trails_total:
                pct = (resort.trails_open / resort.trails_total) * 100
                if pct > 70:
                    highlights.append("most trails open")
            
            highlight_str = " + ".join(highlights[:2]) if highlights else "decent conditions"
            score = resort.score
            
            # Short, punchy recommendation
            lines.append(f"{resort.name} ({score:.0f}): {highlight_str}. {resort.rationale}")
        
        return "\n".join(lines)

    def daily_recommendation(self, resorts: Sequence[ScoredResort]) -> str:
        if not resorts:
            return "No resort data is available to recommend a destination today."

        sorted_resorts = sorted(resorts, key=lambda resort: resort.score, reverse=True)
        best = sorted_resorts[0]
        alternates = sorted_resorts[1:3]

        # Build concise recommendation
        highlights = []
        if best.powder:
            highlights.append("powder")
        if best.snowfall_24h and best.snowfall_24h > 0:
            highlights.append(f"{best.snowfall_24h:.1f}\" fresh")
        if best.wind_speed is not None and best.wind_speed < 15:
            highlights.append("calm winds")
        
        highlight_str = " + ".join(highlights[:2]) if highlights else "solid conditions"
        
        line = f"{best.name} ({best.score:.0f}): {highlight_str}. {best.rationale}"
        
        if alternates:
            alt_names = [r.name for r in alternates[:2]]
            if len(alt_names) == 1:
                line += f" Backup: {alt_names[0]}."
            else:
                line += f" Backups: {alt_names[0]}, {alt_names[1]}."
        
        return line


class LLMClient:
    """Client wrapper for a local Ollama-compatible LLM server."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        model: str = "phi3",
        timeout: float = 30.0,  # Increased timeout for LLM generation
        client: Optional[httpx.Client] = None,
        fallback: Optional[RuleBasedAdvisor] = None,
    ) -> None:
        resolved_base_url = base_url or os.getenv("SNOWDAY_LLM_URL", "http://localhost:11434")
        self.base_url = resolved_base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=timeout)
        self.fallback = fallback or RuleBasedAdvisor()
        
        # Log initialization for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"LLMClient initialized: base_url={self.base_url}, model={self.model}, timeout={timeout}")

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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            url = f"{self.base_url}/api/generate"
            payload = {"model": self.model, "prompt": prompt, "stream": False}
            logger.debug(f"LLM request to {url} with model {self.model}")
            
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            result = data.get("response", "")
            output = result.strip()
            
            # Log if we got an empty response to help debug
            if not output:
                logger.warning(
                    f"LLM returned empty response for model {self.model}. "
                    f"Response data: {data}"
                )
            else:
                logger.debug(f"LLM response length: {len(output)} characters")
            
            return output
        except httpx.TimeoutException as e:
            logger.warning(
                f"LLM request timed out after {self.client.timeout}s. "
                f"URL: {self.base_url}, Model: {self.model}"
            )
            return ""
        except httpx.HTTPError as e:
            error_detail = ""
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = f" Response: {e.response.text[:200]}"
                except Exception:
                    pass
            logger.warning(
                f"LLM HTTP error: {type(e).__name__}: {e}{error_detail}. "
                f"URL: {self.base_url}, Model: {self.model}"
            )
            return ""
        except ValueError as e:
            logger.warning(
                f"LLM response parsing error: {type(e).__name__}: {e}. "
                f"URL: {self.base_url}, Model: {self.model}"
            )
            return ""
        except Exception as e:
            logger.warning(
                f"Unexpected LLM error: {type(e).__name__}: {e}. "
                f"URL: {self.base_url}, Model: {self.model}"
            )
            return ""

    def _summary_prompt(self, resorts: Sequence[ScoredResort], *, top_n: int) -> str:
        formatted_rows = self._format_resorts(resorts)
        return textwrap.dedent(
            f"""
            You're a ski expert giving quick, concise recommendations like a Google review. 
            Keep it short and punchy - one line per resort max. Focus on what matters: powder, 
            fresh snow, good conditions. Is it GNARLY?
            
            Format: Resort Name (score): key highlights. Brief why it's good.
            Use just the number for the score, not "/100".
            
            Resort conditions:
            {formatted_rows}
            
            List the top {top_n} resorts, one per line. Be concise - like you're texting a friend, 
            not writing an essay. No paragraphs, just quick hits. Don't include "/100" after scores.
            """
        ).strip()

    def _recommendation_prompt(self, resorts: Sequence[ScoredResort]) -> str:
        formatted_rows = self._format_resorts(resorts)
        return textwrap.dedent(
            f"""
            Give ONE quick recommendation like a skier's review. Short and to the point.
            
            Format: Resort Name (score): key highlights. Why it's good. Optional backup mention.
            Use just the number for the score, not "/100".
            
            Resort conditions:
            {formatted_rows}
            
            Pick the best resort and write ONE concise line. Mention powder, fresh snow, or 
            good conditions. If there's a solid backup, add it at the end. Keep it under 2 sentences.
            Don't include "/100" after scores.
            """
        ).strip()

    def _format_resorts(self, resorts: Sequence[ScoredResort]) -> str:
        """Format resorts into a detailed string for LLM prompts."""
        if not resorts:
            return "No resort data available."
        
        sorted_resorts = sorted(resorts, key=lambda r: r.score, reverse=True)
        lines = []
        for resort in sorted_resorts:
            # Build condition details
            conditions = []
            if resort.snowfall_24h is not None:
                conditions.append(f"24hr snow: {resort.snowfall_24h:.1f}in")
            if resort.snowfall_12h is not None:
                conditions.append(f"12hr snow: {resort.snowfall_12h:.1f}in")
            if resort.base_depth is not None:
                conditions.append(f"base: {resort.base_depth:.0f}in")
            if resort.wind_speed is not None:
                conditions.append(f"wind: {resort.wind_speed:.0f}mph")
            if resort.temp_min is not None and resort.temp_max is not None:
                conditions.append(f"temps: {resort.temp_min:.0f}°F to {resort.temp_max:.0f}°F")
            if resort.precip_type:
                conditions.append(f"precip: {resort.precip_type}")
            if resort.trails_open is not None:
                if resort.trails_total:
                    conditions.append(f"trails: {resort.trails_open}/{resort.trails_total}")
                else:
                    conditions.append(f"trails open: {resort.trails_open}")
            if resort.lifts_open is not None:
                if resort.lifts_total:
                    conditions.append(f"lifts: {resort.lifts_open}/{resort.lifts_total}")
                else:
                    conditions.append(f"lifts spinning: {resort.lifts_open}")
            if resort.powder:
                conditions.append("POWDER CONDITIONS")
            if resort.icy:
                conditions.append("ICY CONDITIONS")
            if resort.is_operational is False:
                conditions.append("STATUS: CLOSED")
            elif resort.is_operational is None:
                conditions.append("STATUS: UNKNOWN")
            else:
                conditions.append("STATUS: OPEN")
            
            condition_str = ", ".join(conditions) if conditions else "no detailed conditions"
            lines.append(f"- {resort.name}: Score {resort.score:.0f} | {condition_str}")
        return "\n".join(lines)


__all__ = ["LLMClient", "RuleBasedAdvisor", "ScoredResort"]
