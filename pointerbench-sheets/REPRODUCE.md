# Reproducing Pointerbench-Sheets

The benchmark is generated programmatically from the
`spreadsheet-coordinate-grounding` generator in the source repository.

```bash
# from the generator directory in the source repo:
python3 build_pointerbench.py --n 500 --seed 90111 --out /path/to/pointerbench-sheets
```

- **Seed `90111`** is disjoint from the training-data seed (`7`), so every
  benchmark sheet is unseen during training.
- The build renders one distinct sheet per example, saves it as
  `data/test/<i>.png`, and writes one `data/test/metadata.jsonl` row with the
  instruction, the pixel `bbox`, the center `point`, and the category / UI-style
  / language tags.
- The benchmark includes ordinary object-like targets (cells, headers, colored
  regions) plus thin spreadsheet edge targets: column resize handles, row resize
  handles, right cell edges, bottom cell edges, and the four corners of visible
  cells. It also includes relative-navigation tasks such as "three rows below
  A5" and "two columns right and one row down from B7".
- Rendering is fully deterministic given the seed (pure PIL), so the box
  coordinates are pixel-exact and the set is byte-reproducible.

Regenerating with the same seed reproduces the identical 500 examples. To grow
or refresh the set, change `--n` / `--seed` and bump the dataset version.
