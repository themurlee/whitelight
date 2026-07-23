import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        standard_attrs = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
            'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
            'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
            'processName', 'process', 'message'
        }
        context = {}
        for k, v in record.__dict__.items():
            if k not in standard_attrs and not k.startswith('_'):
                context[k] = v
        if context:
            log_data["context"] = context
            
        return json.dumps(log_data)

def setup_structured_logging(level=logging.INFO):
    """Overrides system logging handlers with JSONFormatter to output structured logs."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
