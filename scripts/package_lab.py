"""Empaqueta solo fuentes necesarias, sin credenciales, datasets ni bases locales."""
import hashlib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root.parent / 'shopfast-aws-lab.zip'
files = [root / p for p in ['Dockerfile.ep2', '.dockerignore', 'requirements.txt', 'requirements-api.txt', 'requirements-ep2.txt', 'requirements-dev.txt',
                           'README.md', 'LEER_PRIMERO.md', 'docs/COSTOS.md']]
for directory in ['src', 'worker', 'scripts', 'infra', 'tests', 'out/models', 'docs', '.github']:
    files.extend(p for p in (root / directory).rglob('*') if p.is_file() and
                 '__pycache__' not in p.parts and p.suffix not in ['.pyc', '.db'])
with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        archive.write(path, Path('shopfast-aws-lab') / path.relative_to(root))
print(destination)
print('bytes:', destination.stat().st_size)
print('sha256:', hashlib.sha256(destination.read_bytes()).hexdigest())
