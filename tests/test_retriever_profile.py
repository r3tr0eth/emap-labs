"""Regresión del bug 2026-09-01: SemanticEncoder ignoraba
EMAP_RETRIEVER_PROFILE y todos los resultados "e5large" del harness
ejecutaron MiniLM con etiqueta falsa (prod no: el factory pasa el nombre).

Vive en fichero propio porque importa semantic_local (numpy/fastembed):
el job baseline de CI corre test_eval_contract.py con deps mínimas.
"""
from __future__ import annotations

import os
import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))


class SemanticEncoderProfileTest(unittest.TestCase):
    def test_encoder_honra_el_perfil_del_entorno(self) -> None:
        import semantic_local

        class _FakeModel:
            def __init__(self, model_name: str) -> None:
                self.model_name = model_name

            def embed(self, texts):
                return [[1.0, 0.0] for _ in texts]

        env = {"EMAP_RETRIEVER_PROFILE": "e5large"}
        cleared = {k: os.environ.pop(k, None)
                   for k in ("EMAP_SIM_TAU", "EMAP_TIE_WIN", "EMAP_EMBED_MODEL")}
        try:
            with unittest.mock.patch.object(semantic_local, "TextEmbedding", _FakeModel), \
                 unittest.mock.patch.dict(os.environ, env):
                encoder = semantic_local.SemanticEncoder()
                self.assertEqual("e5large", encoder.profile_name)
                self.assertEqual("intfloat/multilingual-e5-large", encoder.model)
                self.assertEqual(encoder.model, encoder._model.model_name)
                self.assertEqual(0.8, encoder.sim_threshold)

                # El argumento explícito gana al entorno (camino de producción).
                explicito = semantic_local.SemanticEncoder("minilm")
                self.assertEqual("minilm", explicito.profile_name)
        finally:
            for key, value in cleared.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
