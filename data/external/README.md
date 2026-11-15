# External research datasets

This directory is intentionally excluded from Git. Its contents can contain
third-party text, annotations, and licences that must be reviewed before any
redistribution or model training.

## QCRI ProBel

`scripts/fetch_probel.py` downloads the public
[QCRI/ProBel](https://huggingface.co/datasets/QCRI/ProBel) dataset into
`data/external/probel/`. It is a bilingual (English/Arabic) propaganda and
persuasion-technique benchmark with binary labels, technique labels, span
annotations, and explanations.

Its upstream license is **CC BY-NC-SA 4.0**. It is therefore for non-commercial
research and evaluation unless you obtain separate permission. The downloader
preserves the upstream licence/card and creates `provenance.json` with exact
files, byte sizes, and SHA-256 hashes. Do not commit its contents, treat a
technique label as an annotation rather than a fact about a person or outlet,
and do not use it to make automated accusations.
