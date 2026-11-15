import unittest

from src.engine.propaganda import detect_technique_cues


class PropagandaTechniqueCueTests(unittest.TestCase):
    def test_all_ptc_18_labels_have_positive_lexical_examples(self):
        samples = {
            "loaded_language": "This vile decision will hurt the city.",
            "name_calling_labeling": "The mayor is a parasite.",
            "repetition": "We will win, we will win.",
            "exaggeration_minimisation": "Everyone always agrees with us.",
            "doubt": "Can we trust this report?",
            "appeal_to_fear_prejudice": "Act before it's too late.",
            "flag_waving": "Defend our country today.",
            "causal_oversimplification": "The crisis happened solely because of this decision.",
            "slogans": "Make our country great again.",
            "appeal_to_authority": "Experts agree this plan will work.",
            "black_and_white_fallacy": "You are either with us or against us.",
            "thought_terminating_cliches": "Case closed.",
            "whataboutism": "What about their mistakes?",
            "reductio_ad_hitlerum": "That policy is just like Hitler.",
            "red_herring": "The real issue is the other party.",
            "bandwagon": "Everyone knows this is the right choice.",
            "obfuscation_vagueness": "Mistakes were made during the process.",
            "straw_man": "So you're saying all critics want to destroy the country.",
        }

        detected = detect_technique_cues([
            {"post_id": key, "actor_id": f"actor:{key}", "text": text}
            for key, text in samples.items()
        ])

        self.assertEqual({item["id"] for item in detected}, set(samples))
        self.assertTrue(all(item["confidence"] == "low" for item in detected))
        self.assertTrue(all(item["evidence"][0]["matched_text"] for item in detected))

    def test_evidence_offsets_point_to_original_text_after_whitespace_collapse(self):
        text = "  The report says:\n\tThis   vile decision was published.  "

        detected = detect_technique_cues([{"id": "offset-1", "text": text}])

        loaded_language = next(item for item in detected if item["id"] == "loaded_language")
        evidence = loaded_language["evidence"][0]
        self.assertEqual(text[evidence["start_offset"]:evidence["end_offset"]], "vile")

    def test_whitespace_collapse_preserves_offsets_for_matches_across_lines(self):
        text = "The slogan was:\n  enough   is enough today."

        detected = detect_technique_cues([{"id": "offset-2", "text": text}])

        slogan = next(item for item in detected if item["id"] == "slogans")
        evidence = slogan["evidence"][0]
        self.assertEqual(text[evidence["start_offset"]:evidence["end_offset"]], "enough   is enough")

    def test_neutral_reporting_language_produces_no_candidates(self):
        report_text = [
            {"post_id": "neutral-1", "actor_id": "reporter:1", "text": "The city council met on Tuesday and published its annual budget."},
            {"post_id": "neutral-2", "actor_id": "reporter:2", "text": "Officials said the next meeting is scheduled for Friday."},
        ]

        self.assertEqual(detect_technique_cues(report_text), [])


if __name__ == "__main__":
    unittest.main()
