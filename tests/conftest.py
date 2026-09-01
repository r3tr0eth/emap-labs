"""Prepara sys.path para toda la suite.

Sin esto, `response_contract` solo resolvía si test_multiterritory_service.py
se coleccionaba antes (orden alfabético): `pytest tests/test_response_contract.py`
aislado fallaba con ModuleNotFoundError. Cada test debe poder ejecutarse solo.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for entry in (str(ROOT), str(ROOT / "service"), str(ROOT / "evals")):
    if entry not in sys.path:
        sys.path.insert(0, entry)
