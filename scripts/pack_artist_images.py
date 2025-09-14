import os
from datetime import datetime

from consts import PRODUCTS_DIR, PACK_IMAGES_SCRIPT, MAIN_DIR
from products import build_product
from processes import execute_script

TEMP_DESTINATION_PATH = '/tmp/artist_images.tar.gz'

def pack_artist_images() -> str:
    execute_script(f'{PACK_IMAGES_SCRIPT} {TEMP_DESTINATION_PATH}')

    product_name = f'artist_images_{datetime.now().strftime('%Y%m%d%H%M%S')}.tar'
    build_product(
        file_path=TEMP_DESTINATION_PATH,
        output_path=PRODUCTS_DIR / product_name,
        product_type='artist-images'
    )

    os.system(f'find {MAIN_DIR}/swingmusic/images/artists -type f -delete')

    return product_name
