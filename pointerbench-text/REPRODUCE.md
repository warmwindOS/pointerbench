# Reproducing Pointerbench-Text

The benchmark is generated programmatically from the
`text-coordinate-grounding` generator in the source repository.

```bash
# from the generator directory in the source repo:
python3 build_textbench.py --n 500 --seed 90211 --out /path/to/pointerbench-text
```

- **Seed `90211`** is disjoint from the training-data seed (`7`), so every
  benchmark page is unseen during training.
- The build renders one distinct page per example, saves it as
  `data/test/<i>.png`, and writes one `data/test/metadata.jsonl` row with the
  instruction, the pixel `bbox`, a reference `point`, `answer_type`, `eval`, and
  the data_type / category / surface / language / difficulty tags.
- Target kinds follow the generator's native `KIND_WEIGHTS`; bbox-answer kinds
  are preserved instead of being filtered out. This includes the invoice-field
  kinds (number, dates, sender/recipient, line items and the full line-item
  table, subtotal, tax / VAT ID, total, IBAN/BIC, bank details), which render on
  dedicated invoice surfaces so each target is unambiguous.
- Bbox-answer rows (text boxes and invoice fields) are scored with an asymmetric
  coverage/precision rule (`coverage >= 0.90`, `precision >= 0.70`) rather than
  plain IoU; the per-row thresholds are written into each row's `eval` object.
- Language mix is fixed by the builder: 50% English, then 10% each of German,
  French, Spanish, Italian, Dutch.
- Rendering is deterministic given the seed (pure PIL), and each instruction is
  re-resolved by an independent verifier to confirm a single matching target,
  so the box coordinates are pixel-exact.

Regenerating with the same seed reproduces the identical 500 examples. To grow
or refresh the set, change `--n` / `--seed` and bump the dataset version.
