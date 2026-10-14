#!/bin/sh
set -eu
if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' 'Run this installer as root.' >&2
    exit 1
fi
test -f /opt/folio/media-library/server.py
python3 -c 'import PIL; import cryptography'
if ! id folio >/dev/null 2>&1; then
    useradd --system --user-group --home-dir /var/lib/folio --shell /usr/sbin/nologin folio
fi
install -d -m 0700 -o folio -g folio /var/lib/folio /var/lib/folio/private /var/lib/folio/backups
install -d -m 0700 -o root -g root /etc/folio
python3 - <<'PY'
from pathlib import Path
import os
p=Path('/etc/folio/nhentai-master')
if not p.exists():
    fd=os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(os.urandom(32)); stream.flush(); os.fsync(stream.fileno())
if p.stat().st_size != 32: raise SystemExit('Invalid existing master key; not overwritten')
os.chmod(p,0o600)
PY
install -m 0644 /opt/folio/media-library/deploy/linux/folio.service /etc/systemd/system/folio.service
install -m 0644 /opt/folio/media-library/deploy/linux/folio-cloud-backup.service /etc/systemd/system/folio-cloud-backup.service
install -m 0644 /opt/folio/media-library/deploy/linux/folio-cloud-backup.timer /etc/systemd/system/folio-cloud-backup.timer
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/folio.service /etc/systemd/system/folio-cloud-backup.service /etc/systemd/system/folio-cloud-backup.timer
systemctl enable --now folio
# The cloud timer is deliberately enabled after OneDrive authorization and a
# successful upload/restore check, not before external storage is configured.
