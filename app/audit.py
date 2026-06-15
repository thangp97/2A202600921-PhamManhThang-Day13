from __future__ import annotations

"""Audit log độc lập với application log.

Chỉ ghi các sự kiện cần truy vết (compliance): mỗi lần agent được gọi — ai gọi,
feature gì, model nào, chi phí bao nhiêu. File này tách khỏi data/logs.jsonl để
có thể giữ lâu dài và phân quyền riêng.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))


def audit_log(action: str, **fields: Any) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        **fields,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
