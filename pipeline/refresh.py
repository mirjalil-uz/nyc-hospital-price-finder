"""Bring the data up to date in one command.

Hospitals replace their price files during the year. This script finds the
files that changed on the hospitals' servers, downloads only those, converts
them, rebuilds the database and reports what is different.

Run:  python pipeline/refresh.py --check   (only report which files changed)
      python pipeline/refresh.py           (update everything that changed)
      python pipeline/refresh.py --all     (also re-download files whose size the server will not report)
"""

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb

import discover
import download
import load
from paths import DATA, DATABASE, RAW, REGISTRY

# The size each server reported when its file was last downloaded.
SEEN = DATA / "remote-sizes.json"


def snapshot():
    """What the database holds now, per hospital file: its date and how many prices it has."""
    if not DATABASE.exists():
        return {}
    con = duckdb.connect(str(DATABASE), read_only=True)
    rows = con.execute(
        """SELECT f.file_id, f.last_updated, q.rates_kept,
                  (SELECT count(*) FROM items i WHERE i.file_id = f.file_id)
           FROM files f LEFT JOIN quality q USING (file_id)"""
    ).fetchall()
    con.close()
    return {file_id: {"date": date, "rates": rates, "items": items} for file_id, date, rates, items in rows}


def registry_files():
    """file id -> (url, size the server reports or None, hospitals that use the file)."""
    files = {}
    for row in csv.DictReader(REGISTRY.open(encoding="utf-8")):
        url, size, hospitals = files.get(row["file_id"], (row["mrf_url"], None, []))
        files[row["file_id"]] = (url, int(row["size_bytes"]) if row["size_bytes"] else size,
                                 hospitals + [row["hospital"]])
    return files


def load_seen():
    return json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}


def classify(files, seen):
    """Sort every file into: changed, unchanged, unknown (server gives no size) or missing (never downloaded).

    A file counts as changed when the size its server reports differs from the size reported when
    we last downloaded it. The size on disk cannot be used, because servers often send files
    compressed. The first run has nothing to compare with, so it records today's sizes as the baseline.
    """
    groups = {"changed": [], "unchanged": [], "unknown": [], "missing": []}
    for file_id, (_, remote_size, _) in sorted(files.items()):
        if download.existing(file_id) is None:
            groups["missing"].append(file_id)
        elif remote_size is None:
            groups["unknown"].append(file_id)
        elif file_id not in seen:
            seen[file_id] = remote_size
            groups["unchanged"].append(file_id)
        elif seen[file_id] != remote_size:
            groups["changed"].append(file_id)
        else:
            groups["unchanged"].append(file_id)
    return groups


def replace_file(file_id, url):
    """Download a fresh copy, keeping the old one until the new one has arrived."""
    old = download.existing(file_id)
    backup = old.with_name(old.name + ".old") if old else None
    if old:
        old.rename(backup)
    try:
        download.download(file_id, url)
    except Exception:
        if backup:
            backup.rename(old)
        raise
    if backup:
        backup.unlink()
        # A zip's old contents were unpacked into a folder that download() has just refilled.
    return download.existing(file_id)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report what changed without downloading anything")
    parser.add_argument("--all", action="store_true", help="also re-download files of unknown size")
    args = parser.parse_args()

    before = snapshot()
    print("Looking up each hospital's current price file ...", flush=True)
    discover.main()
    files = registry_files()
    seen = load_seen()
    first_run = not seen
    groups = classify(files, seen)
    SEEN.write_text(json.dumps(seen, indent=2), encoding="utf-8")
    if first_run:
        print("\nFirst run: recorded each file's current size as the baseline for future checks.")

    print(f"\n{len(groups['unchanged'])} files unchanged, {len(groups['changed'])} changed, "
          f"{len(groups['unknown'])} of unknown size, {len(groups['missing'])} never downloaded")
    for label, note in (("changed", "a new file is on the hospital's server"),
                        ("unknown", "the server does not report a size; use --all to re-download"),
                        ("missing", "not downloaded yet")):
        for file_id in groups[label]:
            print(f"  {label:8s} {file_id}  ({note})")
    if args.check:
        return

    todo = groups["changed"] + groups["missing"] + (groups["unknown"] if args.all else [])
    if not todo:
        print("\nNothing to update.")
        return

    updated, failed = [], []
    for file_id in todo:
        try:
            # Remove unpacked zip contents first so stale files cannot be picked up again.
            shutil.rmtree(RAW / file_id, ignore_errors=True)
            path = replace_file(file_id, files[file_id][0])
            print(f"downloaded {path.name} ({path.stat().st_size / 1e6:,.0f} MB)", flush=True)
            print(load.convert(file_id, force=True), flush=True)
            if files[file_id][1] is not None:
                seen[file_id] = files[file_id][1]
            updated.append(file_id)
        except Exception as e:
            failed.append(file_id)
            print(f"FAILED {file_id}: {type(e).__name__}: {str(e)[:160]}", flush=True)
    SEEN.write_text(json.dumps(seen, indent=2), encoding="utf-8")
    if not updated:
        print("\nNo file could be updated, so the database was left as it is.")
        return

    print("\nRebuilding the database ...", flush=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name("build.py"))], check=True)

    after = snapshot()
    print("\nWhat changed")
    for file_id in updated:
        old, new = before.get(file_id), after.get(file_id, {})
        hospitals = ", ".join(files[file_id][2])
        if old is None:
            print(f"  NEW      {hospitals}: {new.get('rates') or 0:,} insurer prices, file dated {new.get('date')}")
        else:
            print(f"  UPDATED  {hospitals}: file dated {old['date']} -> {new.get('date')}, "
                  f"insurer prices {old['rates'] or 0:,} -> {new.get('rates') or 0:,}, "
                  f"items {old['items']:,} -> {new.get('items') or 0:,}")
    if failed:
        print("  Could not update: " + ", ".join(failed)
              + ". Sites that block scripts need their file downloaded in a browser (see README).")


if __name__ == "__main__":
    main()
