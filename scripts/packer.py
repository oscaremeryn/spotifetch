import contextlib
import json
import logging
import os
from datetime import datetime

from pydantic import BaseModel, field_serializer, field_validator

from consts import OUT_DIR, MUSIC_FILE_GLOB, PRODUCTS_DIR, PACKER_QUEUE_FILE, IMPORT_SCRIPT, PACK_SCRIPT, MUSIC_DIR
from products import build_product
from processes import execute_script


class PackerJob(BaseModel):
    url_hash: str
    product_name: str
    time_to_pack: datetime
    attributes: dict[str, str] = {}

    @field_validator('time_to_pack', mode='before')
    @classmethod
    def parse_human_readable_datetime(cls, v):
        if isinstance(v, str):
            try:
                return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
            except ValueError as ex:
                raise ValueError(f"Invalid datetime format. Expected 'YYYY-MM-DD HH:MM:SS'. Got: {v}") from ex
        return v

    @field_serializer('time_to_pack')
    def serialize_human_readable_datetime(self, dt: datetime, _info):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def __hash__(self) -> str:
        return self.url_hash


def execute_packer_job(job: PackerJob):
    logging.info(f"Importing artist with hash '{job.url_hash}'")

    out_dir = OUT_DIR / job.url_hash
    out_dir.mkdir(parents=True, exist_ok=True)
    music_dir = MUSIC_DIR / job.url_hash / 'music'
    music_dir.mkdir(parents=True, exist_ok=True)

    out_dir_has_files = any(out_dir.rglob(MUSIC_FILE_GLOB))
    music_dir_has_files = any(music_dir.rglob(MUSIC_FILE_GLOB))

    if not out_dir_has_files and not music_dir_has_files:
        logging.info('Artist directory does not have any music files, skipping')
        # Send to end of queue
        remove_packer_job(job)
        queue_packer_job(job)
        return

    if out_dir_has_files:
        if music_dir_has_files:
            logging.info('Found some music files in the artist\'s import folder, trying to continue where we left off')

        execute_script(f'{IMPORT_SCRIPT} {job.url_hash}')
    elif music_dir_has_files:
        logging.info('All artist music has already been imported, skipping to packing')

    gzip_name = f'{job.product_name}.gz'

    logging.info(f'Packing songs into {gzip_name}')
    with contextlib.chdir(music_dir.parent):
        execute_script(f'{PACK_SCRIPT} {gzip_name}')

        logging.info(f'Building product into {PRODUCTS_DIR / job.product_name}')
        build_product(
            file_path=gzip_name,
            output_path=PRODUCTS_DIR / job.product_name,
            product_type='music',
            attributes=job.attributes
        )

    os.system(f'rm -rfv {music_dir}/* {gzip_name}')
    remove_packer_job(job)


def read_packer_queue() -> list[PackerJob]:
    if not PACKER_QUEUE_FILE.is_file():
        return []

    return [PackerJob(**packer) for packer in json.loads(PACKER_QUEUE_FILE.read_text())]


def set_packer_queue(queue: list[PackerJob]):
    PACKER_QUEUE_FILE.write_text(json.dumps([job.model_dump() for job in queue], indent=2))


def queue_packer_job(new_job: PackerJob):
    queue = read_packer_queue()
    if any(new_job.url_hash == job.url_hash for job in queue):
        return

    queue.append(new_job)
    set_packer_queue(queue)


def get_packer_job() -> PackerJob | None:
    for job in read_packer_queue():
        if datetime.now() >= job.time_to_pack:
            return job
    return None


def remove_packer_job(job_to_remove: PackerJob):
    set_packer_queue([job for job in read_packer_queue() if job.url_hash != job_to_remove.url_hash])


def execute_a_packer_job() -> bool:
    if job := get_packer_job():
        execute_packer_job(job)
        return True

    return False
