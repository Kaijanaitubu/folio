"""Package source/docs only; exclude databases, backups, logs, and QA data."""
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parent
target=root.parent/'Folio-local-app.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for file in sorted(root.rglob('*')):
        rel=file.relative_to(root)
        if not file.is_file() or any(p in ('data','backups','test-output','__pycache__','.git') for p in rel.parts) or file.suffix=='.pyc':continue
        z.write(file,'media-library/'+rel.as_posix())
    z.write(root.parent/'Personal-Media-Database-Requirements-v2.0.md','Personal-Media-Database-Requirements-v2.0.md')
print(target)
