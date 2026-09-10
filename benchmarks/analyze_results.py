import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def save_line(df: pd.DataFrame, metric: str, ylabel: str, output: Path):
    fig, ax = plt.subplots()
    for scenario, group in df.groupby("scenario"):
        group = group.sort_values("users")
        ax.plot(group["users"], group[metric], marker="o", label=scenario)
    ax.set_xlabel("Concurrent users")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{ylabel} by concurrent users")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--prefix", default="benchmark")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    output_dir = Path(__file__).parents[1] / "docs" / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    save_line(df, "throughput_rps", "Throughput (RPS)", output_dir / f"{args.prefix}_throughput.png")
    save_line(df, "p95_ms", "p95 latency (ms)", output_dir / f"{args.prefix}_p95.png")
    save_line(df, "error_rate_pct", "Error rate (%)", output_dir / f"{args.prefix}_error_rate.png")


if __name__ == "__main__":
    main()
