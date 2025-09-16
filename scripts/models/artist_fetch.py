from datetime import datetime
from functools import cached_property
from pathlib import Path, PurePath
from typing import Literal, Optional

from more_itertools.more import first
from pydantic import BaseModel

from consts import STATE_DIR, OUT_DIR
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