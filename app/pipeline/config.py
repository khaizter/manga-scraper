import os
from pathlib import Path

PIPELINE_STATE_DIR = Path(os.getenv('PIPELINE_STATE_DIR', 'data/pipeline'))
PIPELINE_DAILY_LIMIT = int(os.getenv('PIPELINE_DAILY_LIMIT', '100'))
PIPELINE_DELAY_SECONDS = float(os.getenv('PIPELINE_DELAY_SECONDS', '30'))
PIPELINE_MAX_RETRIES = int(os.getenv('PIPELINE_MAX_RETRIES', '3'))
PIPELINE_DISCOVER_DELAY_SECONDS = float(os.getenv('PIPELINE_DISCOVER_DELAY_SECONDS', '2'))
PIPELINE_STORE = os.getenv('PIPELINE_STORE', 'json')  # json | firestore
