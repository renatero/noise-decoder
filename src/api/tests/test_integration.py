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
        self.assertEqual(report["technique_analysis"]["techniques"], [])
        self.assertEqual(report["technique_analysis"]["score_adjustment"]["score_delta"], 0)

    def test_cross_account_rhetorical_cues_are_reported_and_adjust_dashboard_score(self):
        events = [
            {"id": "a1", "platform": "bluesky", "actor_id": "account:a", "timestamp": "2026-06-01T12:00:00Z", "text": "Those vile traitors are harming our community.", "urls": ["https://news.example/one"]},
            {"id": "b1", "platform": "bluesky", "actor_id": "account:b", "timestamp": "2026-06-01T12:00:30Z", "text": "Those vile traitors are harming our community.", "urls": ["https://news.example/one"]},
            {"id": "a2", "platform": "bluesky", "actor_id": "account:a", "timestamp": "2026-06-02T12:00:00Z", "text": "Those corrupt traitors are harming our community.", "urls": ["https://news.example/two"]},
            {"id": "b2", "platform": "bluesky", "actor_id": "account:b", "timestamp": "2026-06-02T12:00:30Z", "text": "Those corrupt traitors are harming our community.", "urls": ["https://news.example/two"]},
        ]

        report = asyncio.run(analyze_events(events))

        techniques = {item["id"]: item for item in report["technique_analysis"]["techniques"]}
        self.assertEqual(set(techniques), {"loaded_language", "name_calling_labeling"})
        self.assertEqual(report["technique_analysis"]["score_adjustment"]["adjustment_fraction"], 0.1)
        self.assertGreater(report["permutation_analysis"]["heuristic_suspicion_score"], report["permutation_analysis"]["network_heuristic_suspicion_score"])
