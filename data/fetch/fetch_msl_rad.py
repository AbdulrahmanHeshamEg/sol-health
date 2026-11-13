"""Download Curiosity (MSL) RAD level-2 daily CDF files from NASA CDAWeb into data/raw/msl_rad/<year>/.

    python data/fetch/fetch_msl_rad.py                 # 2026 (default)
    python data/fetch/fetch_msl_rad.py 2024 2026       # several years (2024 contains the May-2024 solar storm)
    python data/fetch/fetch_msl_rad.py 2026 --limit 30 # quick test: first 30 days only

Directory listing: https://cdaweb.gsfc.nasa.gov/sp_phys/data/msl/rad/cdf/obs-l2/<year>/
File name: msl_rad_obs-l2_<YYYY><DOY>_v<NN>.cdf  (DOY = day of year, 001 = 1 Jan).
The version suffix differs per file and some days have two versions -> keep only the HIGHEST version per day.
Backup source if CDAWeb is down: PDS PPI node (MSL RAD archive).
This is Mars-SURFACE data (2015 onward), not the Earth->Mars cruise.
"""
from __future__ import annotations

import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "msl_rad"
BASE = "https://cdaweb.gsfc.nasa.gov/sp_phys/data/msl/rad/cdf/obs-l2/{year}/"
PATTERN = re.compile(r"msl_rad_obs-l2_(\d{4})(\d{3})_v(\d+)\.cdf")


def latest_versions(listing_html: str) -> dict[tuple[int, int], str]:
    """{(year, doy): filename} keeping the highest version for each day."""
    best: dict[tuple[int, int], tuple[int, str]] = {}
    for m in PATTERN.finditer(listing_html):
        key, ver = (int(m.group(1)), int(m.group(2))), int(m.group(3))
        if key not in best or ver > best[key][0]:
            best[key] = (ver, m.group(0))
    return {k: v[1] for k, v in sorted(best.items())}


def fetch(url: str, dest: Path, tries: int = 3) -> bool:
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                dest.write_bytes(r.read())
            return True
        except Exception as e:  # network hiccup: back off and retry
            print(f"  retry {i + 1}/{tries} {dest.name}: {e}")
            time.sleep(2 * (i + 1))
    return False


def main(argv: list[str]):
    limit = None
    if "--limit" in argv:
        i = argv.index("--limit"); limit = int(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    years = [int(a) for a in argv] or [2026]
    for year in years:
        url = BASE.format(year=year)
        html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
        files = list(latest_versions(html).values())[:limit]
        dest_dir = OUT / str(year); dest_dir.mkdir(parents=True, exist_ok=True)
        got = skipped = 0
        for name in files:
            dest = dest_dir / name
            if dest.exists() and dest.stat().st_size > 0:
                skipped += 1; continue
            got += fetch(url + name, dest)
        print(f"{year}: {len(files)} days listed, {got} downloaded, {skipped} already present -> {dest_dir}")


if __name__ == "__main__":
    main(sys.argv[1:])
