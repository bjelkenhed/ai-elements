import logging

# Auto-configure logging when module is imported
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Suppress HTTP request logs
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name):
    """Get a logger with the given name."""
    return logging.getLogger(name)