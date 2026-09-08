"""Public ephemeral analysis: bounded, never persisted or logged."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from yaounde_analyzer.api.deps import get_analyzer
from yaounde_analyzer.api.schemas import AnalyzeResponse
from yaounde_analyzer.core.analysis import PreparedAnalyzer, analyze_tokens_and_parse
from yaounde_analyzer.core.models import AnalysisRequest

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    payload: AnalysisRequest, analyzer: PreparedAnalyzer = Depends(get_analyzer)
) -> AnalyzeResponse:
    tokens, parse, topics = analyze_tokens_and_parse(payload.text, analyzer)
    return AnalyzeResponse(tokens=tokens, parse=parse, topics=topics)
