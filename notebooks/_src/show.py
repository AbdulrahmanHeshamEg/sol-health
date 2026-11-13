"""Print the text outputs of an executed notebook: python notebooks/_src/show.py 01 [first_cell]"""
import sys
from pathlib import Path
import nbformat
nb_dir = Path(__file__).resolve().parents[1]
path = sorted(nb_dir.glob(sys.argv[1] + "*.ipynb"))[0]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
for i, c in enumerate(nbformat.read(path, as_version=4).cells):
    if c.cell_type != "code" or i < start:
        continue
    for o in c.get("outputs", []):
        text = o.get("text") or o.get("data", {}).get("text/plain", "")
        if text and "<Figure" not in text:
            print(f"--- cell {i}\n{text.rstrip()[:3000]}")
