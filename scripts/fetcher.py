import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from os import waitstatus_to_exitcode

import requests
from bs4 import BeautifulSoup
from slugify import slugify

from consts import FETCH_ATTEMPT_COUNT, PACKER_LEEWAY_SINCE_FETCH, SWING_ACCESS_TOKEN, \
    FETCH_QUEUE_FILE, FetcherException, COOKIES_FILE
from models.artist_fetch import ArtistFetch
from packer import queue_packer_job, PackerJob


def extract_artist_name_from_page(content: str) -> str:
    return BeautifulSoup(content, 'html.parser').title.text.removesuffix(' | Spotify')


def fetch_artist_name(url: str) -> str:
    page_content = subprocess.check_output(
        f'chromium-browser --disable-gpu --headless --dump-dom {url} 2>/dev/null',
        shell=True
    ).decode()
    return extract_artist_name_from_page(page_content)


def sanitize_artist_name(name: str) -> str:
    return slugify(name, max_length=120, separator='_', allow_unicode=True)


def fetch_artist(artist: ArtistFetch) -> bool:
    if artist.name is None:
        artist.name = fetch_artist_name(artist.url)
        update_artist_fetch(artist)

    if artist.status == 'FAILED' and not artist.ignore_errors:
        logging.warning(f"Skipping failed artist '{artist.name}'")
        return False

    logging.info(f"Fetching artist '{artist.name}' - {artist.url}")

    logging.info('Checking for yt-dlp updates')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'yt-dlp'])

    logging.info(f'Output directory: {artist.out_dir}')
    for attempt_count in range(FETCH_ATTEMPT_COUNT):
        try:
            error_file = artist.generate_error_file()
            return_code = waitstatus_to_exitcode(os.system(
                # f"spotdl --format mp3 --output '{out_dir}/{{album-artist}}/{{album}}/{{title}}.{{output-ext}}' --yt-dlp-args '-f bestaudio* --cookies {COOKIES_FILE} --extractor-args \"youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416\"' --max-retries 1 --threads 6 --save-errors '{error_file}' --id3-separator ', ' --log-level=DEBUG download {artist.url} --audio youtube youtube-music soundcloud --generate-lrc --lyrics synced genius azlyrics musixmatch --genius-access-token 'V1cJYvWbhzkZ8saefsEwi_ZVI1ZmPUjnNRb3XTvtgTN9YLEYNm5IuFrPqYbebjQQ'",
                f"spotdl --format mp3 --output '{artist.out_dir}/{{album-artist}}/{{album}}/{{title}}.{{output-ext}}' --yt-dlp-args '--format-sort-force -S abr,acodec --format bestaudio* --cookies {COOKIES_FILE} --extractor-args=\"youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416\"' --max-retries 1 --threads 5 --save-errors '{error_file}' --save-file '{artist.state_dir / "cache.spotdl"}' --preload --fetch-albums --id3-separator ', ' --log-level=DEBUG download {artist.url} --audio youtube-music youtube --generate-lrc --lyrics synced genius azlyrics --genius-access-token 'V1cJYvWbhzkZ8saefsEwi_ZVI1ZmPUjnNRb3XTvtgTN9YLEYNm5IuFrPqYbebjQQ' --client-id '2f2a55464aed4ad19abf145795e65dfc' --client-secret 'a3fb18b7b2a648a5bd32fa6f09f81b84'",
            ))

            if artist.ignore_errors:
                break

            if return_code > 0:
                raise FetcherException('Fetch command failed')

            if not error_file.is_file():
                raise FetcherException('Error file was not created, fetch did not finish')

            if error_file.stat().st_size == 0:  # No errors occurred
                break

        except Exception:
            logging.exception('Exception occurred while fetching artist')

        if attempt_count < FETCH_ATTEMPT_COUNT - 1:
            logging.info(f"Fetching '{artist.name}', attempt {attempt_count + 2}/{FETCH_ATTEMPT_COUNT}")
            continue

        artist.status = 'FAILED'

    if artist.status == 'FAILED' and not artist.ignore_errors:
        artist.error_log = str(artist.get_latest_error_file())
        artist.ignore_errors = False
        return False

    # Trigger re-scan of Swing Music, for syncing artist images
    logging.info('Triggering scan of Swing Music')
    requests.get(
        'http://localhost:1970/notsettings/trigger-scan',
        cookies={'access_token_cookie': SWING_ACCESS_TOKEN},
        verify=False
    ).raise_for_status()

    time_to_pack = datetime.now() + PACKER_LEEWAY_SINCE_FETCH
    logging.info(f'Scheduling a packer job for {time_to_pack.isoformat(sep=" ", timespec="seconds")}')
    queue_packer_job(PackerJob(
        url_hash=artist.url_hash,
        product_name=f'{sanitize_artist_name(artist.name)}.tar',
        time_to_pack=time_to_pack,
        attributes={
            'artist': artist.name,
            'url': artist.url
        }
    ))

    return True


def read_pending_artist_fetches() -> list[ArtistFetch]:
    if not FETCH_QUEUE_FILE.is_file():
        FETCH_QUEUE_FILE.write_text('[]')
        return []

    return [ArtistFetch(**fetch_json) for fetch_json in json.loads(FETCH_QUEUE_FILE.read_text())]


def write_pending_artist_fetches(fetches: list[ArtistFetch]):
    FETCH_QUEUE_FILE.write_text(
        json.dumps(
            [json.loads(artist.model_dump_json(exclude_none=True)) for artist in fetches],
            indent=2,
        )
    )


def remove_artist_fetch(to_remove: ArtistFetch):
    fetches = [artist for artist in read_pending_artist_fetches() if artist.url != to_remove.url]
    write_pending_artist_fetches(fetches)


def update_artist_fetch(to_update: ArtistFetch):
    fetches = [artist for artist in read_pending_artist_fetches() if artist.url != to_update.url]
    fetches.append(to_update)
    write_pending_artist_fetches(fetches)


def fetch_a_pending_artist() -> bool:
    if not (queued_artists := read_pending_artist_fetches()):
        return False

    artist = queued_artists[0]
    if fetch_artist(artist):
        remove_artist_fetch(artist)
    else:
        update_artist_fetch(artist)

    return True
