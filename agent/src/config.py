import os
import logging
from dotenv import load_dotenv

# Set up paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
SRC_DIR = os.path.join(BASE_DIR, 'src')
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)

# Load environment variables
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()  # fallback to system env

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, 'agent.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger('upsc-agent')

# Configuration values
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
try:
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
except ValueError:
    SMTP_PORT = 587
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL', 'rajramkola796@gmail.com')

# Validate essential config
def validate_config(is_dry_run=False):
    errors = []
    if not GEMINI_API_KEY and not is_dry_run:
        logger.warning("GEMINI_API_KEY is not set. Running in mock mode.")
    
    if not is_dry_run:
        if not SMTP_USER:
            errors.append("SMTP_USER is not set.")
        if not SMTP_PASSWORD:
            errors.append("SMTP_PASSWORD is not set.")
        if not RECEIVER_EMAIL:
            errors.append("RECEIVER_EMAIL is not set.")
            
    if errors:
        for err in errors:
            logger.error(err)
        return False
    return True
