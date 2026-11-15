import unittest

from src.api.main import AnalyzeRequest, Event, analyze


class TechniqueReportingApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_article_cues_are_reported_without_network_score_adjustment(self):
        articles = [
            Event(id=f"article:{index}", platform="news_context", actor_id=f"publisher:{index % 2}",
                  timestamp="2026-11-14T10:00:00Z", text="Before it's too late, this danger threatens us.",
                  urls=[f"https://news.example/{index}"])
            for index in range(2)
        ]

        report = await analyze(AnalyzeRequest(events=articles))

        self.assertEqual(report["status"], "news_context")
        self.assertEqual(report["technique_analysis"]["techniques"], [])
        self.assertEqual(report["news_context_technique_analysis"]["techniques"][0]["id"], "appeal_to_fear_prejudice")
        self.assertEqual(report["news_context_technique_analysis"]["score_adjustment"]["score_delta"], 0)

    async def test_normalized_social_events_use_the_scored_technique_analysis(self):
        events = [
            Event(id="a1", platform="bluesky", actor_id="account:a", timestamp="2026-11-14T10:00:00Z",
                  text="Those vile traitors are harming us.", urls=["https://news.example/one"]),
            Event(id="b1", platform="bluesky", actor_id="account:b", timestamp="2026-11-14T10:00:01Z",
                  text="Those vile traitors are harming us.", urls=["https://news.example/one"]),
            Event(id="a2", platform="bluesky", actor_id="account:a", timestamp="2026-11-15T10:00:00Z",
                  text="Those corrupt traitors are harming us.", urls=["https://news.example/two"]),
            Event(id="b2", platform="bluesky", actor_id="account:b", timestamp="2026-11-15T10:00:01Z",
                  text="Those corrupt traitors are harming us.", urls=["https://news.example/two"]),
        ]

        report = await analyze(AnalyzeRequest(events=events))

        self.assertEqual(report["status"], "suspicious")
        self.assertEqual(report["technique_analysis"]["score_adjustment"]["adjustment_fraction"], 0.1)
        self.assertEqual(report["permutation_analysis"]["heuristic_suspicion_score"], 2.2)
        self.assertEqual(report["permutation_analysis"]["network_heuristic_suspicion_score"], 2.0)


if __name__ == "__main__":
    unittest.main()
