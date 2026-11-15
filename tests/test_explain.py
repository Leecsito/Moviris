# -*- coding: utf-8 -*-
"""Pruebas del endpoint Explain sin llamar a Groq."""

import unittest

import backend.explain as explain
from backend.app import app


class ExplainTests(unittest.TestCase):
    def setUp(self):
        self._load_env = explain.load_env
        self._llamar_groq = explain._llamar_groq
        explain.load_env = lambda: {
            "GROQ_LLM_TOKEN": "test-token",
            "GROQ_MODEL": "test-model",
        }
        explain._llamar_groq = lambda *args, **kwargs: "Test explanation."
        self.client = app.test_client()

    def tearDown(self):
        explain.load_env = self._load_env
        explain._llamar_groq = self._llamar_groq

    def payload(self, **overrides):
        payload = {
            "chart": "years",
            "title": "Activity by year",
            "filters": {"confidence": "0"},
            "data": {"metric": "active cell-days", "top_years": [{"year": 2024, "value": 10}]},
            "lang": "en",
        }
        payload.update(overrides)
        return payload

    def test_explain_ok(self):
        response = self.client.post("/api/explain", json=self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["text"], "Test explanation.")

    def test_invalid_chart(self):
        response = self.client.post("/api/explain", json=self.payload(chart="not-a-chart"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "invalid")

    def test_payload_too_large(self):
        response = self.client.post(
            "/api/explain",
            json=self.payload(data={"blob": "x" * 15000}),
        )
        self.assertEqual(response.status_code, 413)

    def test_missing_model(self):
        explain.load_env = lambda: {"GROQ_LLM_TOKEN": "test-token"}
        response = self.client.post("/api/explain", json=self.payload(lang="es"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "not_configured")
        self.assertIn("Explain", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
