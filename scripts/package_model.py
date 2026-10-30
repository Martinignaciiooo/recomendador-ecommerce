from pathlib import Path
import tarfile
root=Path(__file__).resolve().parents[1]
version=(root/'out/models/current').read_text().strip()
source=root/'out/models'/version
with tarfile.open(root/'model.tar.gz','w:gz') as tar:
 for name in ['factors.npz','meta.json']:tar.add(source/name,arcname=name)
print('model.tar.gz creado para',version)
