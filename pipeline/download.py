"""Step 2: download the price files listed in data/registry.csv into the raw data folder.

Files already on disk are skipped, so the script can be re-run safely.
Zip archives are unpacked next to the download.

Run:  python pipeline/download.py              (everything)
      python pipeline/download.py --max-mb 300 (only files up to 300 MB)
"""

import argparse
import csv
import sys
import zipfile

import requests

from paths import RAW, REGISTRY

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def sniff_extension(head):
    """Guess the file type from its first bytes: zip, json or csv."""
    if head[:2] == b"PK":
        return "zip"
    text = head.lstrip(b"\xef\xbb\xbf \r\n\t")
    return "json" if text[:1] in (b"{", b"[") else "csv"


def existing(file_id):
    done = [p for p in RAW.glob(f"{file_id}.*") if p.suffix != ".part"]
    return done[0] if done else None


def download(file_id, url):
    part = RAW / f"{file_id}.part"
    with requests.get(url, headers=HEADERS, stream=True, timeout=(30, 300)) as r:
        r.raise_for_status()
        chunks = r.iter_content(1 << 20)
        first = next(chunks, b"")
        if first.lstrip()[:1] == b"<":
            raise RuntimeError("server returned a web page, not a data file")
        with part.open("wb") as f:
            f.write(first)
            for chunk in chunks:
                f.write(chunk)
    target = RAW / f"{file_id}.{sniff_extension(first)}"
    part.replace(target)
    if target.suffix == ".zip":
        with zipfile.ZipFile(target) as z:
            z.extractall(RAW / file_id)
    return target


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-mb", type=float, help="skip files known to be larger than this")
    parser.add_argument("--only", nargs="*", help="file ids to download")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    files = {}
    for row in csv.DictReader(REGISTRY.open(encoding="utf-8")):
        files[row["file_id"]] = (row["mrf_url"], int(row["size_bytes"] or 0))

    failed = []
    for file_id, (url, size) in sorted(files.items(), key=lambda kv: kv[1][1]):
        if args.only and file_id not in args.only:
            continue
        if args.max_mb and not args.only and size > args.max_mb * 1e6:
            continue
        if existing(file_id):
            continue
        try:
            target = download(file_id, url)
            print(f"ok    {target.name:70s} {target.stat().st_size / 1e6:9.1f} MB", flush=True)
        except Exception as e:
            failed.append(file_id)
            print(f"FAIL  {file_id:70s} {type(e).__name__}: {e}", flush=True)
    print(f"done, {len(failed)} failed: {failed}")


if __name__ == "__main__":
    main()
