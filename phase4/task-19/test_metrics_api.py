"""Focused API checks for Task 19."""

from __future__ import annotations

import unittest

from fastapi import HTTPException

from metrics_api import EXPOSED_METRICS, freshness, get_metric, list_metrics


class MetricsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metrics = list_metrics()

    def test_catalog_lists_five_metrics(self) -> None:
        self.assertEqual(len(self.metrics), 5)
        self.assertEqual({metric.metric_id for metric in self.metrics}, set(EXPOSED_METRICS))

    def test_each_metric_has_value_definition_source_and_refresh(self) -> None:
        for metric_id in ("M01", "M04", "M09", "M17", "M20"):
            with self.subTest(metric_id=metric_id):
                body = get_metric(metric_id)
                self.assertIsNotNone(body.value)
                self.assertIn("business_definition", body.definition)
                self.assertIn("raw_table", body.source)
                self.assertTrue(body.last_refresh.data_cutoff)

    def test_unknown_metric_is_not_success_shaped(self) -> None:
        with self.assertRaises(HTTPException) as context:
            get_metric("M99")
        self.assertEqual(context.exception.status_code, 404)

    def test_slug_and_filters_select_a_specific_value(self) -> None:
        body = get_metric("headcount", period="2026-09-01", department_id="D01")
        self.assertEqual(body.metric_id, "M01")
        self.assertEqual(body.period_start, "2026-09-01")

    def test_freshness_has_plain_language_statement(self) -> None:
        self.assertIn("available through", freshness().statement)


if __name__ == "__main__":
    unittest.main()
