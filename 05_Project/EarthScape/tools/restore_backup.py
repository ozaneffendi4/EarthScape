"""Stop server first. Restore an encrypted snapshot using its matching key."""
import argparse,sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
p=argparse.ArgumentParser();p.add_argument('backup');p.add_argument('--key',required=True);p.add_argument('--output',required=True);args=p.parse_args()
out=Path(args.output)
if out.exists():raise SystemExit('Refusing to overwrite existing database. Move it aside first.')
raw=Fernet(Path(args.key).read_bytes()).decrypt(Path(args.backup).read_bytes());out.write_bytes(raw)
with sqlite3.connect(out) as c:
 if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Integrity check failed')
print('Restored successfully:',out)
