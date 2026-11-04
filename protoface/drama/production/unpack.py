"""Restore reference frames stored as text in GitHub; verify their hashes."""
import base64
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def unpack():
    dest=ROOT/"assets/panels"
    dest.mkdir(parents=True,exist_ok=True)
    count=0
    for page in sorted((ROOT/"packed").glob("board-*.json")):
        for identifier,entry in json.loads(page.read_text()).items():
            if not identifier.startswith("ep04-") or not identifier[5:].isdigit():
                raise ValueError("Unexpected reference name")
            data=base64.b64decode(entry["data"],validate=True)
            if hashlib.sha256(data).hexdigest()!=entry["sha256"]:
                raise ValueError("Reference checksum mismatch")
            (dest/f"{identifier}.jpg").write_bytes(data)
            count+=1
    if count!=30: raise ValueError(f"Expected 30 reference frames, found {count}")
    print("Restored 30 clean reference frames.")

if __name__=="__main__": unpack()
