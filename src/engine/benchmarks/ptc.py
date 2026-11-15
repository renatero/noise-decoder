"""Evaluate the current lexical technique detector on labeled PTC v2 data.

The corpus is not bundled. Download the Zenodo archive and pass either its
extracted ``datasets`` directory or the parent directory to this module.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from src.engine.propaganda import detect_technique_cues


DATASET_NAME = "PTC v2 / SemEval-2020 Task 11"
DATASET_RECORD = "https://zenodo.org/records/3952415"
DATASET_ARCHIVE_URL = "https://zenodo.org/records/3952415/files/datasets-v2.tgz?download=1"
DATASET_ARCHIVE_MD5 = "a67b730067e275da627ed6753586b98e"

# SemEval 2020 merges the original 18 labels into 13 usable classes and omits
# Obfuscation, Intentional Vagueness, Confusion. Predictions from either rule
# in a merged class count as that superclass, matching the corpus inventory.
DETECTOR_TO_PTC = {
    "loaded_language": "Loaded_Language",
    "name_calling_labeling": "Name_Calling,Labeling",
    "repetition": "Repetition",
    "exaggeration_minimisation": "Exaggeration,Minimisation",
    "doubt": "Doubt",
    "appeal_to_fear_prejudice": "Appeal_to_fear-prejudice",
    "flag_waving": "Flag-Waving",
    "causal_oversimplification": "Causal_Oversimplification",
    "slogans": "Slogans",
    "appeal_to_authority": "Appeal_to_Authority",
    "black_and_white_fallacy": "Black-and-White_Fallacy",
    "thought_terminating_cliches": "Thought-terminating_Cliches",
    "bandwagon": "Bandwagon,Reductio_ad_hitlerum",
    "reductio_ad_hitlerum": "Bandwagon,Reductio_ad_hitlerum",
    "whataboutism": "Whataboutism,Straw_Men,Red_Herring",
    "straw_man": "Whataboutism,Straw_Men,Red_Herring",
    "red_herring": "Whataboutism,Straw_Men,Red_Herring",
}

PTC_LABELS = (
    "Loaded_Language",
    "Name_Calling,Labeling",
    "Repetition",
    "Exaggeration,Minimisation",
    "Doubt",
    "Appeal_to_fear-prejudice",
    "Flag-Waving",
    "Causal_Oversimplification",
    "Slogans",
    "Appeal_to_Authority",
    "Black-and-White_Fallacy",
    "Thought-terminating_Cliches",
    "Bandwagon,Reductio_ad_hitlerum",
    "Whataboutism,Straw_Men,Red_Herring",
)

PTC_LABEL_NAMES = {
    "Loaded_Language": "Loaded Language",
    "Name_Calling,Labeling": "Name Calling / Labeling",
    "Repetition": "Repetition",
    "Exaggeration,Minimisation": "Exaggeration / Minimization",
    "Doubt": "Doubt",
    "Appeal_to_fear-prejudice": "Appeal to Fear / Prejudice",
    "Flag-Waving": "Flag Waving",
    "Causal_Oversimplification": "Causal Oversimplification",
    "Slogans": "Slogans",
    "Appeal_to_Authority": "Appeal to Authority",
    "Black-and-White_Fallacy": "Black and White Fallacy",
    "Thought-terminating_Cliches": "Thought Terminating Cliches",
    "Bandwagon,Reductio_ad_hitlerum": "Bandwagon / Reductio ad Hitlerum",
    "Whataboutism,Straw_Men,Red_Herring": "Whataboutism / Straw Men / Red Herring",
}


@dataclass(frozen=True)
class Span:
    article_id: str
    start: int
    end: int
    technique: str | None = None


def _dataset_root(path: Path) -> Path:
    for candidate in (path, path / "datasets"):
        if (candidate / "train-articles").is_dir() and (
            candidate / "train-labels-task2-technique-classification"
        ).is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not find PTC train-articles and train-labels-task2-technique-classification under {path}"
    )


def _article_id(path: Path) -> str:
    match = re.fullmatch(r"article(\d+)\.txt", path.name)
    if not match:
        raise ValueError(f"Unexpected PTC article filename: {path.name}")
    return match.group(1)


def _read_labels(path: Path, article_id: str, has_technique: bool) -> list[Span]:
    spans: list[Span] = []
    if not path.is_file():
        raise FileNotFoundError(f"Missing PTC labels file: {path}")
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        columns = line.split("\t")
        expected = 4 if has_technique else 3
        if len(columns) != expected:
            raise ValueError(f"Malformed PTC label at {path}:{line_number}")
        row_id = columns[0]
        if row_id != article_id:
            raise ValueError(f"Article id mismatch at {path}:{line_number}: {row_id}")
        if has_technique:
            technique, start, end = columns[1], int(columns[2]), int(columns[3])
            if technique not in PTC_LABELS:
                raise ValueError(f"Unsupported PTC technique at {path}:{line_number}: {technique}")
        else:
            technique, start, end = None, int(columns[1]), int(columns[2])
        spans.append(Span(article_id, start, end, technique))
    return spans


def load_ptc(path: Path) -> tuple[dict[str, str], list[Span], list[Span]]:
    """Load article texts and official train Task 1 / Task 2 labels."""
    root = _dataset_root(path)
    articles_dir = root / "train-articles"
    si_dir = root / "train-labels-task1-span-identification"
    tc_dir = root / "train-labels-task2-technique-classification"
    articles: dict[str, str] = {}
    si_gold: list[Span] = []
    tc_gold: list[Span] = []
    for article_path in sorted(articles_dir.glob("article*.txt")):
        article_id = _article_id(article_path)
        text = article_path.read_text(encoding="utf-8")
        articles[article_id] = text
        if not text:
            raise ValueError(f"Empty PTC article: {article_path}")
        si_path = si_dir / f"article{article_id}.task1-SI.labels"
        tc_path = tc_dir / f"article{article_id}.task2-TC.labels"
        for span in _read_labels(si_path, article_id, has_technique=False):
            if not (0 <= span.start < span.end <= len(text)):
                raise ValueError(f"PTC SI offsets are out of bounds for article {article_id}")
            si_gold.append(span)
        for span in _read_labels(tc_path, article_id, has_technique=True):
            if not (0 <= span.start < span.end <= len(text)):
                raise ValueError(f"PTC TC offsets are out of bounds for article {article_id}")
            tc_gold.append(span)
    if not articles:
        raise ValueError(f"No PTC train article files found under {articles_dir}")
    return articles, si_gold, tc_gold


def predict_ptc(articles: dict[str, str]) -> list[Span]:
    predictions: list[Span] = []
    for article_id, text in articles.items():
        techniques = detect_technique_cues([{"id": article_id, "text": text}])
        for technique in techniques:
            ptc_label = DETECTOR_TO_PTC.get(technique["id"])
            if ptc_label is None:
                continue
            for evidence in technique["evidence"]:
                start, end = evidence.get("start_offset"), evidence.get("end_offset")
                if not isinstance(start, int) or not isinstance(end, int) or start >= end:
                    raise ValueError(f"Detector returned invalid offsets for article {article_id}")
                predictions.append(Span(article_id, start, end, ptc_label))
    return predictions


def _merge(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    ordered = sorted(intervals)
    if not ordered:
        return []
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _overlap_length(left: list[tuple[int, int]], right: list[tuple[int, int]]) -> int:
    overlap = 0
    left_index = right_index = 0
    while left_index < len(left) and right_index < len(right):
        left_start, left_end = left[left_index]
        right_start, right_end = right[right_index]
        overlap += max(0, min(left_end, right_end) - max(left_start, right_start))
        if left_end <= right_end:
            left_index += 1
        else:
            right_index += 1
    return overlap


def _scores(true_positive: int, predicted: int, gold: int) -> dict[str, float | int]:
    precision = true_positive / predicted if predicted else 0.0
    recall = true_positive / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "matched": true_positive,
        "predicted": predicted,
        "gold": gold,
    }


def _evaluate_spans(gold_spans: list[Span], predicted_spans: list[Span], *, classified: bool) -> dict:
    gold_keys = {
        (span.article_id, span.technique, span.start, span.end)
        if classified else (span.article_id, span.start, span.end)
        for span in gold_spans
    }
    predicted_keys = {
        (span.article_id, span.technique, span.start, span.end)
        if classified else (span.article_id, span.start, span.end)
        for span in predicted_spans
    }
    exact = _scores(len(gold_keys & predicted_keys), len(predicted_keys), len(gold_keys))

    def grouped(spans: list[Span]) -> dict[tuple[str, str | None], list[tuple[int, int]]]:
        groups: dict[tuple[str, str | None], list[tuple[int, int]]] = defaultdict(list)
        for span in spans:
            groups[(span.article_id, span.technique if classified else None)].append((span.start, span.end))
        return {key: _merge(intervals) for key, intervals in groups.items()}

    gold_groups = grouped(gold_spans)
    predicted_groups = grouped(predicted_spans)
    gold_chars = predicted_chars = matched_chars = 0
    for key in gold_groups.keys() | predicted_groups.keys():
        gold = gold_groups.get(key, [])
        predicted = predicted_groups.get(key, [])
        gold_chars += sum(end - start for start, end in gold)
        predicted_chars += sum(end - start for start, end in predicted)
        matched_chars += _overlap_length(gold, predicted)
    return {
        "exact_span": exact,
        "character_overlap": _scores(matched_chars, predicted_chars, gold_chars),
    }


def _sentence_metrics(
    articles: dict[str, str], gold_spans: list[Span], predicted_spans: list[Span]
) -> dict[str, int | float]:
    gold_by_article: dict[str, list[tuple[int, int]]] = defaultdict(list)
    predicted_by_article: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for span in gold_spans:
        gold_by_article[span.article_id].append((span.start, span.end))
    for span in predicted_spans:
        predicted_by_article[span.article_id].append((span.start, span.end))

    tp = fp = fn = tn = total = 0
    for article_id, text in articles.items():
        gold_intervals = gold_by_article.get(article_id, [])
        predicted_intervals = predicted_by_article.get(article_id, [])
        cursor = 0
        for line_number, line in enumerate(text.splitlines(keepends=True)):
            content = line.rstrip("\r\n")
            line_start, line_end = cursor, cursor + len(content)
            cursor += len(line)
            # PTC text files start with a title and a blank line; article body
            # lines are sentence-split by the corpus authors.
            if line_number < 2 or not content.strip():
                continue
            gold_positive = any(start < line_end and end > line_start for start, end in gold_intervals)
            predicted_positive = any(start < line_end and end > line_start for start, end in predicted_intervals)
            total += 1
            if gold_positive and predicted_positive:
                tp += 1
            elif predicted_positive:
                fp += 1
            elif gold_positive:
                fn += 1
            else:
                tn += 1
    scores = _scores(tp, tp + fp, tp + fn)
    scores.update({"true_negative": tn, "total_sentences": total})
    scores["specificity"] = round(tn / (tn + fp), 6) if tn + fp else 0.0
    return scores


def evaluate_ptc(articles: dict[str, str], si_gold: list[Span], tc_gold: list[Span]) -> dict:
    predictions = predict_ptc(articles)
    si_predictions = [Span(span.article_id, span.start, span.end) for span in predictions]
    si = _evaluate_spans(si_gold, si_predictions, classified=False)
    tc = _evaluate_spans(tc_gold, predictions, classified=True)

    per_technique = []
    supported_f1 = []
    for technique in PTC_LABELS:
        technique_gold = [span for span in tc_gold if span.technique == technique]
        technique_predictions = [span for span in predictions if span.technique == technique]
        metrics = _evaluate_spans(technique_gold, technique_predictions, classified=True)["character_overlap"]
        per_technique.append({
            "id": technique,
            "name": PTC_LABEL_NAMES[technique],
            "gold_spans": len({(s.article_id, s.start, s.end) for s in technique_gold}),
            "predicted_spans": len({(s.article_id, s.start, s.end) for s in technique_predictions}),
            **metrics,
        })
        if technique_gold:
            supported_f1.append(float(metrics["f1"]))

    return {
        "dataset": DATASET_NAME,
        "dataset_record": DATASET_RECORD,
        "dataset_archive_url": DATASET_ARCHIVE_URL,
        "dataset_archive_md5": DATASET_ARCHIVE_MD5,
        "evaluation_date": date.today().isoformat(),
        "split": "labeled training partition; diagnostic evaluation, not held-out performance",
        "articles": len(articles),
        "gold_span_identification_spans": len({(s.article_id, s.start, s.end) for s in si_gold}),
        "gold_technique_instances": len({(s.article_id, s.technique, s.start, s.end) for s in tc_gold}),
        "predicted_spans": len({(s.article_id, s.start, s.end) for s in si_predictions}),
        "predicted_technique_instances": len({(s.article_id, s.technique, s.start, s.end) for s in predictions}),
        "span_identification": si,
        "end_to_end_technique_labeling": {
            **tc,
            "macro_f1_supported_classes": round(sum(supported_f1) / len(supported_f1), 6) if supported_f1 else 0.0,
            "supported_classes": len(supported_f1),
            "classes": per_technique,
        },
        "sentence_detection": _sentence_metrics(articles, tc_gold, predictions),
        "metric_definitions": {
            "exact_span": "A true positive requires the same article, exact character offsets, and (for technique labeling) the same PTC class.",
            "character_overlap": "Overlapping intervals are unioned per article (and per technique for technique labeling); correctly labeled overlapping characters count toward precision and recall.",
            "sentence_detection": "Each non-empty article-body line is treated as one sentence; gold positive means a PTC technique span overlaps it, predicted positive means a detector cue overlaps it.",
        },
        "limitations": [
            "Only the labeled training partition is publicly included in this archive; these numbers are not held-out test results.",
            "SemEval 2020 merges rare labels into two superclasses and omits Obfuscation, Intentional Vagueness, Confusion; merged rules are scored against their superclass.",
            "The application uses transparent lexical cues, not a trained PTC model; it returns at most one matching span per technique per article.",
            "Exact-span and character-overlap scores are project-defined diagnostics, not the organizers' official SI or conditional TC scorer.",
            "Sentence-level scores are derived from the corpus's sentence-per-line article format and technique spans; they are diagnostic, not official SLC scores.",
            "Technique-labeled scores are end-to-end over predicted spans and labels; they are not the official conditional TC score on supplied gold spans.",
            "The benchmark measures technique-cue detection on news articles, not the network score adjustment or coordination analysis.",
        ],
    }


def run_benchmark(data_dir: Path) -> dict:
    articles, si_gold, tc_gold = load_ptc(data_dir)
    return evaluate_ptc(articles, si_gold, tc_gold)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True, help="PTC v2 extracted datasets directory")
    parser.add_argument("--output", type=Path, help="Write JSON report to this path (stdout if omitted)")
    args = parser.parse_args()
    report = run_benchmark(args.data_dir)
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
        print(f"Wrote benchmark report to {args.output}")
        print(json.dumps({
            "articles": report["articles"],
            "span_identification_character_overlap": report["span_identification"]["character_overlap"],
            "end_to_end_technique_labeling_character_overlap": report["end_to_end_technique_labeling"]["character_overlap"],
            "sentence_detection": report["sentence_detection"],
        }, indent=2))
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
