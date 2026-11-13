"""Download PMData (16 people, ~5 months, Fitbit Versa 2 + PMSys wellness) into data/raw/pmdata/.

    python data/fetch/fetch_pmdata.py

Source: Hugging Face mirror `aai530-group6/pmdata` (original: Simula, https://datasets.simula.no/pmdata/).
Food images are skipped (not used). Expected layout after download:
    data/raw/pmdata/p01 ... p16/{fitbit,pmsys,googledocs}/...
    data/raw/pmdata/participant-overview.xlsx
Cite: Thambawita et al., "PMData: A Sports Logging Dataset", MMSys 2020, doi:10.1145/3339825.3394926
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "pmdata"
REPO = "aai530-group6/pmdata"


def main():
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        sys.exit("pip install huggingface_hub")
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=REPO, repo_type="dataset", local_dir=OUT,
                      ignore_patterns=["*food-images*", "*.jpg", "*.jpeg", "*.png"])
    people = sorted(p.name for p in OUT.glob("p[0-9][0-9]") if p.is_dir())
    print(f"participants: {len(people)} -> {people}")
    for f in ("fitbit/resting_heart_rate.json", "fitbit/heart_rate.json", "fitbit/sleep.json",
              "fitbit/sleep_score.csv", "fitbit/exercise.json", "pmsys/wellness.csv", "pmsys/injury.csv"):
        have = sum((OUT / p / f).exists() for p in people)
        print(f"  {f:<35} present for {have}/{len(people)}")
    if len(people) < 16:
        print("WARNING: expected 16 participants. Check the repo layout or the Simula/OSF original.")


if __name__ == "__main__":
    main()
