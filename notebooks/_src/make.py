"""Build notebooks/NN_name.ipynb from notebooks/_src/NN_name.py (cells split on `# %%` / `# %% [markdown]`).

    python notebooks/_src/make.py 01            # build + execute headless every source starting with "01"
    python notebooks/_src/make.py 01 --no-run   # build only

Markdown cells are written as comment lines (`# text`) under `# %% [markdown]`.
"""
import subprocess
import sys
from pathlib import Path

import nbformat as nbf

SRC = Path(__file__).resolve().parent
NB = SRC.parent


def build(src: Path) -> Path:
    cells, kind, buf = [], None, []

    def flush():
        text = "\n".join(buf).strip("\n")
        if kind == "markdown":
            text = "\n".join(line[2:] if line.startswith("# ") else line.lstrip("#") for line in text.split("\n"))
            cells.append(nbf.v4.new_markdown_cell(text))
        elif kind == "code" and text:
            cells.append(nbf.v4.new_code_cell(text))

    for line in src.read_text(encoding="utf-8").split("\n"):
        if line.startswith("# %%"):
            flush()
            kind, buf = ("markdown" if "[markdown]" in line else "code"), []
        else:
            buf.append(line)
    flush()
    nb = nbf.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}})
    out = NB / (src.stem + ".ipynb")
    nbf.write(nb, out)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for prefix in args:
        for src in sorted(SRC.glob(f"{prefix}*.py")):
            if src.name == "make.py":
                continue
            out = build(src)
            print("built", out.name)
            if "--no-run" not in sys.argv:
                subprocess.run([sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
                                "--inplace", "--ExecutePreprocessor.timeout=3600", str(out)], check=True, cwd=NB)
