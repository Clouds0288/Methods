import subprocess
import sys
from pathlib import Path


ENV_NAME = "methods"
SCRIPT_DIR = Path(__file__).resolve().parent


def in_methods_env():
    return Path(sys.executable).parent.name.lower() == ENV_NAME


if not in_methods_env():
    print(f"Restarting in conda environment: {ENV_NAME}", flush=True)
    subprocess.run(["conda", "run", "-n", ENV_NAME, "python", str(Path(__file__).name), *sys.argv[1:]], cwd=SCRIPT_DIR, check=True)
    raise SystemExit


targets = sys.argv[1:] or ["all"]
modules = []
if "all" in targets or "opf" in targets:
    modules.append("opf.opf_main")
if "all" in targets or "planning" in targets:
    modules.append("planning.misocp_storage")
if not modules:
    raise ValueError("Use one of: all, opf, planning")

for module in modules:
    print(f"\n=== {module} ===", flush=True)
    subprocess.run([sys.executable, "-m", module], cwd=SCRIPT_DIR, check=True)
