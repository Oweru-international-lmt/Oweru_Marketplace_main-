import json
import logging
import re
from datetime import datetime, timezone


def redact(value):
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+", r"\1[REDACTED]", str(value))
    value = re.sub(r"(?i)([?&](?:token|key|signature|credential|password|secret|x-amz-[a-z-]+)=)[^&\s]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:password|secret_key|access_token|refresh_token|authorization)\s*[=:]\s*)[^\s,;]+", r"\1[REDACTED]", value)
    value = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        if record.exc_info:
            # Exception text and stack locals can contain provider credentials or
            # signed URLs. Correlate the error type with the request identifier.
            payload["exception_type"] = record.exc_info[0].__name__
        for field in ["request_id", "method", "route", "status", "duration_ms"]:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, default=str)
