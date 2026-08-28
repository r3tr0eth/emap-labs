"""Contratos de artefactos del benchmark multi-territorio."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
from run import result_filename  # noqa: E402


class EvalArtifactContractTest(unittest.TestCase):
    def test_el_nombre_separa_territorio_modelo_idioma_y_split(self) -> None:
        run_date = date(2026, 8, 28)

        madrid = result_filename("hybrid", "minilm", "madrid", "es", "dev", run_date)
        euskadi = result_filename("hybrid", "minilm", "euskadi", "es", "dev", run_date)

        self.assertEqual("hybrid-minilm-madrid-es-dev-2026-08-28.json", madrid)
        self.assertEqual("hybrid-minilm-euskadi-es-dev-2026-08-28.json", euskadi)
        self.assertNotEqual(madrid, euskadi)


if __name__ == "__main__":
    unittest.main()
