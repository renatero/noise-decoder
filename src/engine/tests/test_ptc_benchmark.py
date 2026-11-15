import os
import tempfile
import unittest
from pathlib import Path

from src.engine.benchmarks.ptc import Span, _evaluate_spans, run_benchmark


class PtcBenchmarkMetricTests(unittest.TestCase):
    def test_partial_character_overlap_gets_credit_but_exact_span_does_not(self):
        gold = [Span("1", 10, 20, "Loaded_Language")]
        predicted = [Span("1", 12, 18, "Loaded_Language")]

        result = _evaluate_spans(gold, predicted, classified=True)

        self.assertEqual(result["exact_span"]["f1"], 0)
        self.assertEqual(result["character_overlap"]["precision"], 1)
        self.assertEqual(result["character_overlap"]["recall"], 0.6)

    def test_semieval_label_groups_use_corpus_superclasses(self):
        gold = [Span("1", 0, 15, "Bandwagon,Reductio_ad_hitlerum")]
        predicted = [Span("1", 3, 10, "Bandwagon,Reductio_ad_hitlerum")]

        result = _evaluate_spans(gold, predicted, classified=True)

        self.assertEqual(result["character_overlap"]["precision"], 1)
        self.assertEqual(result["character_overlap"]["recall"], round(7 / 15, 6))

    def test_dataset_runner_reads_labeled_articles_and_negative_sentences(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "datasets"
            articles_dir = root / "train-articles"
            si_dir = root / "train-labels-task1-span-identification"
            tc_dir = root / "train-labels-task2-technique-classification"
            for directory in (articles_dir, si_dir, tc_dir):
                directory.mkdir(parents=True)

            text = "Example title\n\nThis vile plan is dangerous.\nOfficials met on Tuesday.\n"
            article_id = "123456789"
            (articles_dir / f"article{article_id}.txt").write_text(text, encoding="utf-8")
            start = text.index("vile")
            end = start + len("vile")
            (si_dir / f"article{article_id}.task1-SI.labels").write_text(
                f"{article_id}\t{start}\t{end}\n", encoding="utf-8"
            )
            (tc_dir / f"article{article_id}.task2-TC.labels").write_text(
                f"{article_id}\tLoaded_Language\t{start}\t{end}\n", encoding="utf-8"
            )

            report = run_benchmark(root)

        self.assertEqual(report["articles"], 1)
        self.assertEqual(report["span_identification"]["exact_span"]["f1"], 1)
        self.assertEqual(report["end_to_end_technique_labeling"]["exact_span"]["f1"], 1)
        self.assertEqual(report["sentence_detection"]["true_negative"], 1)

    @unittest.skipUnless(os.environ.get("PTC_DATA_DIR"), "Set PTC_DATA_DIR to run the external PTC corpus benchmark")
    def test_current_detector_on_labeled_ptc_partition(self):
        report = run_benchmark(Path(os.environ["PTC_DATA_DIR"]))

        self.assertGreater(report["articles"], 0)
        self.assertGreater(report["gold_span_identification_spans"], 0)
        self.assertGreater(report["gold_technique_instances"], 0)
        self.assertEqual(report["end_to_end_technique_labeling"]["supported_classes"], 14)


if __name__ == "__main__":
    unittest.main()
