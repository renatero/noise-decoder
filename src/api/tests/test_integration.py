import asyncio
import json
import unittest
from pathlib import Path

from src.api.integration import analyze_events


ROOT = Path(__file__).resolve().parents[3]


class SyntheticIntegrationTests(unittest.TestCase):
    def report_for(self, dataset_name):
        payload = json.loads((ROOT / "datasets" / f"{dataset_name}.json").read_text(encoding="utf-8"))
        return asyncio.run(analyze_events(payload["events"]))

    def test_recurring_synthetic_bursts_produce_a_candidate_network(self):
        report = self.report_for("synthetic_coordinated")
        self.assertEqual(report["status"], "suspicious")
        self.assertEqual(report["statistics"]["repeated_relationships"], 66)
        self.assertEqual(len(report["clusters"]), 1)

    def test_one_off_benign_breaking_news_response_stays_inconclusive(self):
        report = self.report_for("synthetic_benign")
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["statistics"]["repeated_relationships"], 0)
