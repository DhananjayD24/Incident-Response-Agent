import json
import os
from datetime import datetime, timezone
from typing import Any

from .config import AUDIT_LOG_PATH


def audit_log(
    tool: str,
    args: dict[str, Any],
    result_size: int,
) -> None:
    """Write one audit event to the JSONL audit log."""

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "args": args,
        "result_size": result_size,
    }

    directory = os.path.dirname(AUDIT_LOG_PATH)

    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as file:
        file.write(json.dumps(event, default=str) + "\n")