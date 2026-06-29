# Reproducing Pointerbench-Pro

The benchmark is assembled from the `dream_click` generator's professional-app
click pools in the source repository.

```bash
# from the generator directory in the source repo:
python3 build_progui.py --n 500 --seed 90311 --out /path/to/pointerbench-pro
```

- Targets are sampled from the labeled professional-icon pool
  (`clicks_icons_pro_3k.ndjson`) and the general dreamed-GUI intent pool
  (`clicks_dreamed_gui_intent.ndjson`).
- Targets are labeled as `icon`, `text`, or `other` for analysis, but the public
  set does not force a fixed icon/text ratio.
- Icon-target instructions are rewritten with varied wrappers that explicitly
  ask for the icon itself, unless the original instruction already says "icon".
  This prevents nearby text labels from becoming plausible click targets.
- Candidates are balanced across applications by round-robin selection with a
  fixed seed, then shuffled. The current 500-example set contains 190 icon, 154
  text, and 156 other targets across 100 applications.
- Each application's name, slug, category, and platform come from the dreamed-GUI
  scenario indexes under `shared/data/dreamed_gui*/index.jsonl`, joined by the
  scene slug parsed from each `source_id`.

## Held-out usage

The examples are selected from existing generated pools, so they can overlap a
training set built from the same generator. The selected `source_id`s are
written to `heldout_source_ids.txt`. Exclude those IDs from training to keep the
benchmark held out.

Regenerating with the same seed reproduces the identical 500 examples. To grow
or refresh the set, change `--n` / `--seed` and bump the dataset version.
