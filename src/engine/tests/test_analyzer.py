import asyncio
import unittest

from src.engine.analyzer import analyze, discover_communities


class DiscoverCommunitiesTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "events": [
                {"post_id": "a1", "actor_id": "x:alice", "platform": "x", "timestamp": "2026-05-01T12:00:00Z", "text": "First shared update", "url": "https://x.example/1"},
                {"post_id": "b1", "actor_id": "reddit:bob", "platform": "reddit", "timestamp": "2026-05-01T12:00:30Z", "text": "Second shared update", "url": "https://reddit.example/1"},
                {"post_id": "a2", "actor_id": "x:alice", "platform": "x", "timestamp": "2026-05-01T13:00:00Z", "text": "Third shared update", "url": "https://x.example/2"},
                {"post_id": "b2", "actor_id": "reddit:bob", "platform": "reddit", "timestamp": "2026-05-01T13:00:30Z", "text": "Fourth shared update", "url": "https://reddit.example/2"},
            ],
            "actor_graph": {
                "nodes": [
                    {"id": "x:alice", "platforms": ["x"], "post_count": 2},
                    {"id": "reddit:bob", "platforms": ["reddit"], "post_count": 2},
                    {"id": "mastodon:carol", "platforms": ["mastodon"], "post_count": 1},
                ],
                "edges": [
                    {
                        "source": "x:alice",
                        "target": "reddit:bob",
                        "weight": 2.5,
                        "repeated": True,
                        "content_groups": [
                            {
                                "id": "group-one",
                                "post_ids_by_account": {"x:alice": ["a1"], "reddit:bob": ["b1"]},
                                "evidence": [{"shared_urls": ["https://news.example/story-a"]}],
                            },
                            {
                                "id": "group-two",
                                "post_ids_by_account": {"x:alice": ["a2"], "reddit:bob": ["b2"]},
                                "evidence": [{"shared_urls": ["https://news.example/story-b"]}],
                            },
                        ],
                        "publication_bursts": [
                            {
                                "id": "burst-one",
                                "cluster_id": "group-one",
                                "window_start": "2026-05-01T12:00:00Z",
                                "window_end": "2026-05-01T12:01:30Z",
                                "post_ids_by_account": {"x:alice": ["a1"], "reddit:bob": ["b1"]},
                                "evidence": [{"shared_urls": ["https://news.example/story-a"]}],
                            }
                        ],
                    },
                    {
                        "source": "reddit:bob",
                        "target": "mastodon:carol",
                        "weight": 99,
                        "repeated": False,
                        "content_groups": [],
                        "publication_bursts": [],
                    },
                ],
            },
            "permutation_analysis": {
                "heuristic_suspicion_score": 2.5,
                "permutation_p_value": 0.025,
            },
        }

    def test_communities_use_repeated_weighted_edges_and_summarize_evidence(self):
        result = discover_communities(self.payload)

        self.assertEqual(len(result["communities"]), 1)
        community = result["communities"][0]
        self.assertEqual(community["cluster_size"], 2)
        self.assertEqual(community["repeated_coordination_events"], 3)
        self.assertEqual(community["repeated_content_groups"], 2)
        self.assertEqual(community["repeated_publication_bursts"], 1)
        self.assertEqual(community["participating_platforms"], ["reddit", "x"])
        self.assertEqual(community["weighted_edge_support"], 2.5)
        self.assertIn("2 distinct canonical URLs", community["explanation"])
        self.assertIn("lasting up to 90 seconds", community["explanation"])
        self.assertEqual(len(community["representative_examples"]), 3)
        self.assertEqual(result["statistics"]["repeated_actor_edges"], 1)

    def test_analyze_keeps_permutation_p_value_separate_from_heuristic_score(self):
        report = asyncio.run(analyze(self.payload))

        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["permutation_analysis"]["permutation_p_value"], 0.025)
        self.assertEqual(report["permutation_analysis"]["heuristic_suspicion_score"], 2.5)
        self.assertNotIn("probability", " ".join(report["limitations"]).lower())
        self.assertEqual(len(report["findings"]), 1)

    def test_missing_graph_returns_insufficient_data(self):
        report = asyncio.run(analyze({"events": []}))

        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["communities"], [])


if __name__ == "__main__":
    unittest.main()
