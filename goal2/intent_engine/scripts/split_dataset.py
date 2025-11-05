"""Split the intent dataset into train/valid/test without leaking canonical groups."""
from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import pandas as pd

# Ensure we do not attempt to use an interactive backend when running headless.
plt.switch_backend("agg")


def split_dataset(
    input_path: Path,
    output_dir: Path,
    plot_path: Path,
    group_col: str = "canonical_query",
    intent_col: str = "intent",
    seed: int = 42,
) -> None:
    df = pd.read_csv(input_path)

    required_cols = {group_col, intent_col}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    ratios = {"train": 0.8, "valid": 0.1, "test": 0.1}

    assignments: Dict[str, List[int]] = {name: [] for name in ratios}

    rng = random.Random(seed)
    for intent_value, intent_df in df.groupby(intent_col):
        grouped_indices = [group.index.tolist() for _, group in intent_df.groupby(group_col, sort=False)]
        rng.shuffle(grouped_indices)

        total = sum(len(idx) for idx in grouped_indices)
        targets = {name: ratios[name] * total for name in ratios}
        counts = {name: 0 for name in ratios}

        for group_indices in grouped_indices:
            split_name = max(
                ratios.keys(),
                key=lambda name: (targets[name] - counts[name], -counts[name]),
            )
            assignments[split_name].extend(group_indices)
            counts[split_name] += len(group_indices)

    output_dir.mkdir(parents=True, exist_ok=True)
    split_frames = {}
    for split_name, indices in assignments.items():
        split_df = df.loc[indices].sort_values("id")
        split_frames[split_name] = split_df
        split_df.to_csv(output_dir / f"{split_name}.csv", index=False)

    _plot_distribution(split_frames, plot_path, intent_col)
    _print_summary(split_frames, intent_col)


def _plot_distribution(split_frames: Dict[str, pd.DataFrame], plot_path: Path, intent_col: str) -> None:
    intents = sorted({intent for frame in split_frames.values() for intent in frame[intent_col].unique()})
    x = range(len(intents))
    width = 0.25

    plt.figure(figsize=(10, 5))
    for idx, (split_name, frame) in enumerate(split_frames.items()):
        counts = frame[intent_col].value_counts().reindex(intents, fill_value=0)
        offsets = [xi + (idx - 1) * width for xi in x]
        plt.bar(offsets, counts.values, width=width, label=split_name)

    plt.xticks(list(x), intents, rotation=25, ha="right")
    plt.ylabel("Samples")
    plt.title("Intent distribution by split")
    plt.legend()
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(plot_path, dpi=200)
    plt.close()


def _print_summary(split_frames: Dict[str, pd.DataFrame], intent_col: str) -> None:
    total = sum(len(frame) for frame in split_frames.values())
    for split_name, frame in split_frames.items():
        size = len(frame)
        pct = (size / total) * 100 if total else 0
        print(f"{split_name}: {size} samples ({pct:.2f}%)")
        print(frame[intent_col].value_counts())
        print("-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split the intent dataset into train/valid/test sets.")
    parser.add_argument("--input", type=Path, default=Path("data/intent_dataset_zh_insurance_v1.csv"), help="Input CSV path")
    parser.add_argument("--output", type=Path, default=Path("data/splits"), help="Directory to store split CSVs")
    parser.add_argument("--plot", type=Path, default=Path("docs/intent_distribution.png"), help="Path to save the distribution plot")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    split_dataset(args.input, args.output, args.plot, seed=args.seed)


if __name__ == "__main__":
    main()
