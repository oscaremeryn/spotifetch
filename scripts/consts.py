import os
from datetime import timedelta
from pathlib import Path


class FetcherException(Exception):
    pass


DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

MAIN_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent

OUT_DIR = MAIN_DIR / 'out'
MUSIC_DIR = MAIN_DIR / 'music'
STATE_DIR = MAIN_DIR / 'state'

IMPORT_SCRIPT = SCRIPTS_DIR / 'import'
PACK_SCRIPT = SCRIPTS_DIR / 'pack'
PACK_IMAGES_SCRIPT = SCRIPTS_DIR / 'pack_images'

PRODUCTS_DIR = Path(os.environ['PRODUCTS_DIR'])

COOKIES_FILE = Path(os.environ['COOKIES_FILE'])

SLEEP_IN_LOOP = 5

FETCH_QUEUE_FILE = SCRIPTS_DIR / 'artist_queue.json'
FETCH_ATTEMPT_COUNT = 3
FETCH_EXECUTION_TIMEOUT = timedelta(minutes=40)

PACKER_QUEUE_FILE = SCRIPTS_DIR / '.packer_jobs.json'

MUSIC_FILE_GLOB = '*.mp3'

SHOULD_STOP_FILE = SCRIPTS_DIR / '.should_stop.txt'

# Leeway to let Swing sync all songs before packing them, for fetching artist images
PACKER_LEEWAY_SINCE_FETCH = timedelta(minutes=30)

# Acquired from the cookie "access_token_cookie"
SWING_ACCESS_TOKEN = os.environ['SWING_ACCESS_TOKEN']
