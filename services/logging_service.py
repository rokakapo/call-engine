import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> logging.Logger:
    logs = Path(__file__).parents[1] / "logs"
    logs.mkdir(exist_ok=True)
    logger = logging.getLogger("call_engine")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(logs / "call-engine.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    return logger
