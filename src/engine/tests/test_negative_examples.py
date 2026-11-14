import asyncio
import unittest

from src.engine.analyzer import analyze


def campaign_payload():
    account_ids = [f"account:{index}" for index in range(7)]
    platforms = {actor: ("x" if index < 4 else "reddit") for index, actor in enumerate(account_ids)}
    events = []
    groups = []
    bursts = []
    shared_urls_by_occasion = [
        ["https://news.example/story-one", "https://news.example/story-two"],
        ["https://news.example/story-three"],
        ["https://news.example/story-four"],
    ]
    for occasion in range(3):
        post_ids = {}
        start = f"2026-06-0{occasion + 1}T12:00:00Z"
        for actor in account_ids:
            post_id = f"{actor.rsplit(':', 1)[1]}-{occasion}"
            post_ids[actor] = [post_id]
            events.append(
                {
                    "post_id": post_id,
                    "actor_id": actor,
                    "platform": platforms[actor],
                    "timestamp": start,
                    "text": f"Coordinated campaign message {occasion}",
                    "url": f"https://social.example/{post_id}",
                }
            )
        groups.append(
            {
                "id": f"group-{occasion}",
                "cluster_id": f"group-{occasion}",
                "post_ids_by_account": post_ids,
                "evidence": [{"shared_urls": shared_urls_by_occasion[occasion]}],
            }
        )
        bursts.append(
            {
                "id": f"burst-{occasion}",
                "cluster_id": f"group-{occasion}",
                "window_start": start,
                "window_end": f"2026-06-0{occasion + 1}T12:01:30Z",
                "post_ids_by_account": post_ids,
                "evidence": [{"shared_urls": shared_urls_by_occasion[occasion]}],
            }
        )

    edges = []
    for left_index, source in enumerate(account_ids):
        for target in account_ids[left_index + 1 :]:
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "weight": 3.0,
                    "repeated": True,
                    "content_group_count": 3,
                    "publication_burst_count": 3,
                    "content_groups": groups,
                    "publication_bursts": bursts,
                }
            )
    return {
        "events": events,
        "actor_graph": {
            "directed": False,
            "nodes": [
                {"id": actor, "platforms": [platforms[actor]], "post_count": 3}
                for actor in account_ids
            ],
            "edges": edges,
        },
        "permutation_analysis": {"heuristic_suspicion_score": 63.0, "permutation_p_value": 0.005},
    }


def viral_news_payload():
    actor_ids = [f"account:{index}" for index in range(7)]
    shared_url = "https://news.example/breaking-story"
    events = [
        {
            "post_id": f"viral-{index}",
            "actor_id": actor,
            "platform": "x",
            "timestamp": f"2026-06-10T12:00:{index:02d}Z",
            "text": "Breaking news: a major event is unfolding",
            "url": f"https://social.example/{index}",
        }
        for index, actor in enumerate(actor_ids)
    ]
    return {
        "events": events,
        "actor_graph": {
            "nodes": [{"id": actor, "platforms": ["x"]} for actor in actor_ids],
            "edges": [
                {
                    "source": actor_ids[left],
                    "target": actor_ids[right],
                    "weight": 1,
                    "repeated": False,
                    "content_group_count": 1,
                    "publication_burst_count": 1,
                    "content_groups": [
                        {
                            "id": "viral-group",
                            "post_ids_by_account": {
                                actor_ids[left]: [f"viral-{left}"],
                                actor_ids[right]: [f"viral-{right}"],
                            },
                            "evidence": [{"shared_urls": [shared_url]}],
                        }
                    ],
                    "publication_bursts": [],
                }
                for left in range(len(actor_ids))
                for right in range(left + 1, len(actor_ids))
            ],
        },
    }


class SyntheticNetworkValidationTests(unittest.TestCase):
    def test_repeated_synchronized_campaign_is_discovered_with_representative_summary(self):
        report = asyncio.run(analyze(campaign_payload()))

        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["communities"]), 1)
        community = report["communities"][0]
        self.assertEqual(community["cluster_size"], 7)
        self.assertEqual(community["repeated_content_groups"], 3)
        self.assertEqual(community["repeated_publication_bursts"], 3)
        self.assertEqual(community["participating_platforms"], ["reddit", "x"])
        self.assertIn("7 accounts", community["explanation"])
        self.assertIn("4 distinct canonical URLs", community["explanation"])
        self.assertIn("3 detected publication bursts lasting up to 90 seconds", community["explanation"])
        self.assertEqual(report["permutation_analysis"]["permutation_p_value"], 0.005)
        self.assertEqual(report["permutation_analysis"]["heuristic_suspicion_score"], 63.0)

    def test_single_viral_news_response_does_not_form_repeated_network(self):
        report = asyncio.run(analyze(viral_news_payload()))

        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["communities"], [])
        self.assertEqual(report["statistics"]["repeated_actor_edges"], 0)
        self.assertFalse(any("deceptive" in finding.lower() for finding in report["findings"]))

    def test_empty_dataset_returns_insufficient_data(self):
        report = asyncio.run(analyze({"events": [], "actor_graph": {"nodes": [], "edges": []}}))

        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["communities"], [])

    def test_duplicate_post_ids_are_deduplicated_in_examples(self):
        payload = campaign_payload()
        first_group = payload["actor_graph"]["edges"][0]["content_groups"][0]
        first_group["post_ids_by_account"]["account:5"].append("5-0")

        report = asyncio.run(analyze(payload))
        example = next(
            item
            for item in report["communities"][0]["representative_examples"]
            if item["context_id"] == "group-0" and item["context_type"] == "content_group"
        )

        self.assertEqual(example["post_count"], len({post["post_id"] for post in example["posts"]}))
        self.assertEqual(len(example["posts"]), len({post["post_id"] for post in example["posts"]}))
        self.assertEqual({post["post_id"] for post in example["posts"]}, {"5-0", "6-0"})

    def test_malformed_timestamps_do_not_generate_duration_claims(self):
        payload = campaign_payload()
        for edge in payload["actor_graph"]["edges"]:
            for burst in edge["publication_bursts"]:
                burst["window_start"] = "not-a-timestamp"
                burst["window_end"] = "also-not-a-timestamp"

        report = asyncio.run(analyze(payload))

        explanation = report["communities"][0]["explanation"]
        self.assertIn("3 detected publication bursts", explanation)
        self.assertNotIn("lasting up to", explanation)

    def test_single_actor_input_does_not_form_a_community(self):
        payload = {
            "events": [{"post_id": "only", "actor_id": "account:only", "platform": "x"}],
            "actor_graph": {
                "nodes": [{"id": "account:only", "platforms": ["x"]}],
                "edges": [
                    {"source": "account:only", "target": "account:only", "weight": 100, "repeated": True}
                ],
            },
        }

        report = asyncio.run(analyze(payload))

        self.assertEqual(report["communities"], [])
        self.assertEqual(report["statistics"]["repeated_actor_edges"], 0)
        self.assertNotIn("deceptive", " ".join(report["findings"]).lower())


if __name__ == "__main__":
    unittest.main()
