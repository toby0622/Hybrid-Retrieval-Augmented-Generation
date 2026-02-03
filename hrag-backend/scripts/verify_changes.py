import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.logger import logger
    logger.info("Verifying logger...")
    
    from app.api import app
    print("API module imported successfully.")
    
    from app.ingestion import ingest_document
    print("Ingestion module imported successfully.")
    
    logger.info("Verification script completed.")
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
