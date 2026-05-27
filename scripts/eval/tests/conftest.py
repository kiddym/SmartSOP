"""pytest path setup：把 backend/ 和 repo_root 注入 sys.path，便于:
   from app.parser import ...
   from scripts.eval.metrics import ...
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]  # repo root
for p in (_ROOT / "backend", _ROOT):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
