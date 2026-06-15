from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .tracing import langfuse_context, observe


# Bảng giá theo từng model (USD / 1M tokens). Haiku rẻ hơn Sonnet nhiều lần.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
}


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float
    model: str


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    def pick_model(self, feature: str, message: str) -> str:
        # Cost optimization: route tác vụ nhẹ (summary / câu hỏi ngắn) sang Haiku rẻ hơn.
        if feature == "summary" or len(message) < 60:
            return "claude-haiku-4-5"
        return self.model

    @observe()
    def run(
        self, user_id: str, feature: str, session_id: str, message: str, model: str | None = None
    ) -> AgentResult:
        chosen_model = model or self.pick_model(feature, message)
        started = time.perf_counter()
        docs = retrieve(message)
        prompt = f"Feature={feature}\nDocs={docs}\nQuestion={message}"
        response = self.llm.generate(prompt)
        quality_score = self._heuristic_quality(message, response.text, docs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost_usd = self._estimate_cost(chosen_model, response.usage.input_tokens, response.usage.output_tokens)

        langfuse_context.update_current_trace(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, chosen_model],
        )
        langfuse_context.update_current_observation(
            metadata={"doc_count": len(docs), "query_preview": summarize_text(message)},
            usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        )

        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
            model=chosen_model,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
            model=chosen_model,
        )

    def _estimate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-5"])
        input_cost = (tokens_in / 1_000_000) * pricing["input"]
        output_cost = (tokens_out / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
