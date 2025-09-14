import ast
import logging
import time

from rich.logging import RichHandler

from consts import SHOULD_STOP_FILE, SLEEP_IN_LOOP
from fetcher import fetch_a_pending_artist
from packer import execute_a_packer_job


def should_stop_running() -> bool:
    if not SHOULD_STOP_FILE.is_file():
        return False

    content = SHOULD_STOP_FILE.read_text().splitlines()[0].strip()
    should_stop = bool(ast.literal_eval(content))
    if should_stop:
        SHOULD_STOP_FILE.unlink()

    return should_stop


def main():
    # build_product(
    #     'the_plot_in_you.tar.gz',
    #     '/home/user/products/the_plot_in_you.tar',
    #     product_type='music',
    #     attributes={
    #         'artist': 'The Plot In You',
    #         'url': 'https://open.spotify.com./artist/7obLlvWcHU4oZjXm21IfpH'
    #     }
    # )

    logging.basicConfig(
        level="NOTSET", format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
    )

    logging.info('Listening for jobs')
    try:
        while not should_stop_running():
            if execute_a_packer_job() or fetch_a_pending_artist():
                logging.info('Listening for jobs')

            time.sleep(SLEEP_IN_LOOP)
    except KeyboardInterrupt:
        pass

    logging.info('heppi lisenin')


if __name__ == '__main__':
    main()
