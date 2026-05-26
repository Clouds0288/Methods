import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MODULES = [
    "network.case6",
    "opf.opf_ac",
    "opf.opf_dc",
    "opf.opf_sdp",
    "opf.opf_distflow",
    "opf.opf_lindistflow",
    "opf.opf_report",
]


if __name__ == "__main__":
    for module in MODULES:
        print(f"\n=== {module} ===", flush=True)
        subprocess.run([sys.executable, "-m", module], cwd=ROOT_DIR, check=True)
