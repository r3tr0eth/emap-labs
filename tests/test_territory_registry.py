"""Contrato del seam territorial compartido por servicio y evals."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from regions import list_territories, load_territory, resolve_layer_path  # noqa: E402
from retriever_config import RetrieverConfigError, resolve_profile  # noqa: E402


class TerritoryRegistryTest(unittest.TestCase):
    def test_euskadi_define_la_misma_superficie_de_22_capas(self) -> None:
        territory = load_territory("euskadi")

        self.assertEqual((-3.4, 42.4, -1.6, 43.5), territory.bbox)
        self.assertEqual("0.2.0", territory.version)
        self.assertEqual(22, len(territory.layers))
        self.assertEqual("e5large", territory.production_retriever_profile)
        self.assertEqual(
            Path("/data/pois-euskadi/defib.json"),
            resolve_layer_path(Path("/data"), territory, "defib"),
        )
        self.assertEqual(["euskadi", "madrid"], list_territories(runnable_only=True))

    def test_madrid_reutiliza_el_contrato_con_una_capa_oficial(self) -> None:
        territory = load_territory("madrid")

        self.assertEqual("Municipio de Madrid", territory.territory)
        self.assertEqual({"fountains": "madrid/pois/fountains.json"}, dict(territory.layers))
        self.assertEqual(2, territory.freshness_sla_days["fountains"])
        self.assertEqual("e5large", territory.production_retriever_profile)

    def test_perfil_e5_incluye_modelo_y_calibracion(self) -> None:
        profile = resolve_profile("e5large")

        self.assertEqual("intfloat/multilingual-e5-large", profile.model)
        self.assertEqual(0.8, profile.sim_threshold)
        self.assertEqual(0.01, profile.tie_window)

    def test_rechaza_modelo_sin_calibracion_versionada(self) -> None:
        with self.assertRaises(RetrieverConfigError):
            resolve_profile(model="modelo/experimental-sin-calibrar")


class FreshnessContractTest(unittest.TestCase):
    def test_source_updated_es_fecha_de_frescura_valida(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "emap_freshness_contract_test", ROOT / "service" / "data_freshness.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            module.DATA_DIR = Path(tmp)
            path = resolve_layer_path(module.DATA_DIR, module.TERRITORY, "fountains")
            assert path is not None
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "source_updated": date.today().isoformat(),
                        "source": "fuente-oficial",
                        "license": "CC-BY-4.0",
                        "pois": [],
                    }
                )
            )

            info = module.check_layer_freshness("fountains")

        self.assertEqual("fresh", info["status"])
        self.assertEqual(0, info["age_days"])
        self.assertEqual("fuente-oficial", info["source"])


if __name__ == "__main__":
    unittest.main()
