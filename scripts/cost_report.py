"""So sánh chi phí trước/sau khi áp dụng model routing (Bonus: Cost Optimization).

Chạy cùng một tập câu hỏi mẫu qua 2 chiến lược:
  - BEFORE: mọi request dùng Sonnet (mặc định)
  - AFTER : route tác vụ nhẹ (summary / câu hỏi ngắn) sang Haiku rẻ hơn

In ra tổng chi phí mỗi chiến lược và % tiết kiệm.
"""

import json
import logging
from pathlib import Path

# Script benchmark offline — tắt log noise của Langfuse (không có keys khi chạy CLI).
logging.disable(logging.WARNING)

from app.agent import MODEL_PRICING, LabAgent

SAMPLE_PATH = Path("data/sample_queries.jsonl")


def estimate(model: str, tokens_in: int, tokens_out: int) -> float:
    pricing = MODEL_PRICING[model]
    return tokens_in / 1_000_000 * pricing["input"] + tokens_out / 1_000_000 * pricing["output"]


def main() -> None:
    agent = LabAgent()
    queries = [
        json.loads(line)
        for line in SAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    before_cost = 0.0
    after_cost = 0.0
    routed_to_haiku = 0

    for q in queries:
        feature = q.get("feature", "qa")
        message = q.get("message", "")
        result = agent.run(
            user_id=q.get("user_id", "u_bench"),
            feature=feature,
            session_id=q.get("session_id", "s_bench"),
            message=message,
        )
        tin, tout = result.tokens_in, result.tokens_out

        # BEFORE: ép dùng Sonnet cho mọi request
        before_cost += estimate("claude-sonnet-4-5", tin, tout)
        # AFTER: dùng model mà router đã chọn
        after_cost += estimate(result.model, tin, tout)
        if result.model == "claude-haiku-4-5":
            routed_to_haiku += 1

    total = len(queries)
    savings = before_cost - after_cost
    pct = (savings / before_cost * 100) if before_cost else 0.0

    print("=== Cost Optimization Report (model routing) ===")
    print(f"Total requests          : {total}")
    print(f"Routed to Haiku (cheap) : {routed_to_haiku} ({routed_to_haiku / total * 100:.0f}%)")
    print(f"BEFORE (all Sonnet)     : ${before_cost:.6f}")
    print(f"AFTER  (with routing)   : ${after_cost:.6f}")
    print(f"Savings                 : ${savings:.6f} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
