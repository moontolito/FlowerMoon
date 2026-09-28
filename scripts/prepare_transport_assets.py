"""Restore the bundled GEM raster and verify its recorded SHA-256."""
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'apps/transport/assets/datasets/gem-gshm-2023.1'


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(folder=DATA):
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    target = folder / manifest['filename']
    expected = manifest['sha256']
    if target.is_file() and checksum(target) == expected:
        print('GEM seismic dataset verified.')
        return target
    # A failed extraction leaves any existing raster intact.
    with tempfile.NamedTemporaryFile(dir=folder, suffix='.tmp', delete=False) as output:
        temporary = Path(output.name)
        try:
            with gzip.open(str(target) + '.gz', 'rb') as source:
                while block := source.read(1024 * 1024):
                    output.write(block)
        except BaseException:
            output.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        if checksum(temporary) != expected:
            raise ValueError('Bundled GEM raster failed SHA-256 verification.')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print('GEM seismic dataset restored and verified.')
    return target


if __name__ == '__main__':
    prepare()
