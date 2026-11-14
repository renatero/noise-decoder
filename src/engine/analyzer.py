"""Temporary analyzer interface for the noise decoder engine.

The implementation is intentionally deterministic until the real analysis
pipeline is integrated. Keep the report fields stable for API integration.
"""

from typing import TypedDict


class AnalysisReport(TypedDict):
    """Machine-readable result returned by :func:`analyze`."""

    status: str
    summary: str
    findings: list[str]


async def analyze() -> AnalysisReport:
    """Return a schema-valid placeholder analysis report."""
    return {
        "status": "complete",
        "summary": "Analysis completed using the placeholder engine.",
        "findings": [],
    }
