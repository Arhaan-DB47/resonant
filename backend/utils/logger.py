"""
logger.py -- Structured Logging with Loguru

Usage anywhere in the project:
    from backend.utils.logger import logger

    logger.info("Server started")
    logger.debug("Processing audio file", filename="test.wav", size_kb=245)
    logger.error("Whisper transcription failed", error=str(e))
"""

import sys
from loguru import logger as _logger
from backend.config import settings

# Remove the default handler (loguru adds one automatically)
_logger.remove()

# Add a console handler with colored output
_logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
    colorize=True,
)

# Add a file handler for persistent logs
_logger.add(
    "logs/resonant.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
    rotation="10 MB",       # Create a new file when it reaches 10 MB
    retention="7 days",     # Keep logs for 7 days
    compression="zip",      # Compress old logs
)

# Export as 'logger' for clean imports
logger = _logger
