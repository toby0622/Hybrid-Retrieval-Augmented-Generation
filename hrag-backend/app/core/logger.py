import logging
import sys
from app.core.config import settings

def setup_logger(name: str = "hrag_backend"):
    logger = logging.getLogger(name)
    
    # If logger already has handlers, assume it's set up
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO if not settings.debug else logging.DEBUG)
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

logger = setup_logger()
