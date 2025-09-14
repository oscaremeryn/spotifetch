import json
import os
import logging
import subprocess
import sys
import time
from functools import cached_property
from os import waitstatus_to_exitcode
from pathlib import Path, PurePath

import requests

from datetime import datetime
from typing import Literal, Optional, Any
from bs4 import BeautifulSoup
from more_itertools.more import first
from pydantic import BaseModel
from slugify import slugify

from consts import STATE_DIR, FETCH_ATTEMPT_COUNT, PACKER_LEEWAY_SINCE_FETCH, SWING_ACCESS_TOKEN, \
    FETCH_QUEUE_FILE, FetcherException, FETCH_EXECUTION_TIMEOUT, OUT_DIR, COOKIES_FILE
from packer import queue_packer_job, PackerJob
from processes import execute_script
from products import calculate_md5


class ArtistFetch(BaseModel):
    url: str
    name: Optional[str] = None
    status: Optional[Literal['FAILED']] = None
    error_log: Optional[str] = None
    ignore_errors: Optional[bool] = None

    class Config:
        ignored_types = (cached_property,)
        json_encoders = {PurePath: lambda path: str(path)}

    def generate_error_file(self) -> Path:
        return self.state_dir / f'error_{datetime.now().strftime("%Y%m%d-%H%M%S")}.log'

    def get_latest_error_file(self) -> Optional[Path]:
        return first(sorted(self.state_dir.glob('error*'), reverse=True), None)

    @cached_property
    def url_hash(self) -> str:
        return calculate_md5(self.url)

    @cached_property
    def state_dir(self) -> Path:
        _ = STATE_DIR / self.url_hash
        _.mkdir(parents=True, exist_ok=True)
        return _

    @cached_property
    def out_dir(self) -> Path:
        _ = OUT_DIR / self.url_hash
        _.mkdir(parents=True, exist_ok=True)
        return _


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
                f"spotdl --format mp3 --output '{artist.out_dir}/{{album-artist}}/{{album}}/{{title}}.{{output-ext}}' --yt-dlp-args '--format-sort-force -S abr,acodec --cookies {COOKIES_FILE} --extractor-args=\"youtube:player_client=default\"' --max-retries 1 --threads 6 --save-errors '{error_file}' --save-file '{artist.state_dir / "cache.spotdl"}' --preload --fetch-albums --id3-separator ', ' --log-level=DEBUG download {artist.url} --audio youtube youtube-music soundcloud --generate-lrc --lyrics synced genius musixmatch azlyrics --genius-access-token 'V1cJYvWbhzkZ8saefsEwi_ZVI1ZmPUjnNRb3XTvtgTN9YLEYNm5IuFrPqYbebjQQ'",
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
        artist.error_log = artist.get_latest_error_file()
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
