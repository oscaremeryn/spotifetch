from datetime import datetime

from pydantic import BaseModel, field_serializer, field_validator


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