import tarfile
from base64 import b64encode
from datetime import datetime
from io import BytesIO
from os import PathLike
import hashlib
from pathlib import Path
from tarfile import TarInfo

ATTRIBUTE_FILE_FORMAT = '__{}__.txt'


def calculate_md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def calculate_file_md5(file_path: PathLike, chunk_size: int = 65536) -> str:
    with open(file_path, "rb") as file:
        file_hash = hashlib.md5()
        while chunk := file.read(chunk_size):
            file_hash.update(chunk)

    return file_hash.hexdigest()


def build_product(
        file_path: str | Path,
        output_path: str | Path,
        product_type: str,
        custom_date: datetime | None = None,
        attributes: dict[str, str] | None = None,
        **kwargs
):
    file_path = Path(file_path)
    output_path = Path(output_path)
    attributes = attributes or {}

    attributes.update({
        'date': (custom_date or datetime.now()).isoformat(sep=' ', timespec='seconds'),
        'md5sum': calculate_file_md5(file_path),
        'type': product_type,
        **{k: str(v) for k, v in kwargs.items()}
    })

    with tarfile.open(output_path, mode='w') as tar:
        for attr_name, value in attributes.items():
            tar_info = TarInfo(ATTRIBUTE_FILE_FORMAT.format(attr_name))
            content = value.encode('utf-8')
            tar_info.size = len(content)
            tar.addfile(tarinfo=tar_info, fileobj=BytesIO(content))

        tar.add(file_path, arcname=file_path.name)


if __name__ == '__main__':
    build_product(
        '/home/user/products/noam_klinshtein.tar.gz',
        '/home/user/products/noam_klinshtein.tar',
        'music',
        attributes={
            'artist': 'נועם קלינשטיין',
            'url': 'https://open.spotify.com./artist/0fApsdhIzCLZQh7hZShlqV'
        }
    )
