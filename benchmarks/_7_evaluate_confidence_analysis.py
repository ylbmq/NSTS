import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from _5_evaluate_results import safe_parse_date

CONFIDENCE_ORDER = ["high", "low", "conflicted", "none"]


def normalize_confidence(confidence: Optional[str]) -> str:
    confidence = (confidence or "").strip().lower()
    return confidence if confidence in CONFIDENCE_ORDER else "none"


def load_confidence_analysis_data(
    label_dir: Path,
    results_dir: Path,
    label_suffix: str,
    results_suffix: str,
) -> pd.DataFrame:
    """Loads labels and NSTS internals into one dataframe keyed by URL."""
    nsts_by_url = {}
    nsts_dir = results_dir / "nsts"

    for result_file in nsts_dir.glob(f"*{results_suffix}"):
        with open(result_file, "r", encoding="utf-8") as f:
            for item in json.load(f):
                nsts_by_url[item["url"]] = item

    records = []
    for label_file in label_dir.glob(f"*{label_suffix}"):
        source = label_file.name.removesuffix(label_suffix)
        with open(label_file, "r", encoding="utf-8") as f:
            label_data = json.load(f)

        for label_item in label_data:
            url = label_item.get("url")
            nsts_item = nsts_by_url.get(url)
            if not nsts_item:
                continue

            label = safe_parse_date(label_item.get("timestamp"))
            if pd.isna(label):
                continue

            records.append({
                "url": url,
                "source": source,
                "label": label,
                "confidence": normalize_confidence(nsts_item.get("system_confidence")),
                "psr_timestamp": safe_parse_date(nsts_item.get("psr_timestamp")),
                "cpe_timestamp": safe_parse_date(nsts_item.get("cpe_timestamp")),
                "nsts_timestamp": safe_parse_date(nsts_item.get("timestamp")),
            })

    return pd.DataFrame(records)


def calculate_confidence_distribution_by_domain(df: pd.DataFrame) -> pd.DataFrame:
    """Returns confidence-state percentages with confidence states as rows and domains as columns."""
    distribution = pd.crosstab(
        index=df["confidence"],
        columns=df["source"],
        normalize="columns",
    )
    distribution = distribution.reindex(index=CONFIDENCE_ORDER, fill_value=0)

    overall = df["confidence"].value_counts(normalize=True).reindex(CONFIDENCE_ORDER, fill_value=0)
    distribution["Overall"] = overall
    distribution["Average"] = distribution[
        [col for col in distribution.columns if col != "Overall"]
    ].mean(axis=1)

    source_cols = sorted([col for col in distribution.columns if col not in ["Overall", "Average"]])
    distribution = distribution[source_cols + ["Overall", "Average"]]

    return distribution.map(lambda x: f"{x * 100:.2f}%")


def calculate_accuracy_by_confidence(df: pd.DataFrame) -> pd.DataFrame:
    """Returns PSR, CPE, and NSTS accuracy by confidence state."""
    working_df = df.copy()
    working_df["label"] = pd.to_datetime(working_df["label"], errors="coerce")

    module_columns = {
        "PSR Accuracy": "psr_timestamp",
        "CPE Accuracy": "cpe_timestamp",
    }

    for column in module_columns.values():
        working_df[column] = pd.to_datetime(working_df[column], errors="coerce")

    rows = []
    for confidence in CONFIDENCE_ORDER:
        confidence_df = working_df[working_df["confidence"] == confidence]
        row = {"Confidence": confidence}

        for display_name, pred_col in module_columns.items():
            valid_predictions = confidence_df[pred_col].notna()
            if valid_predictions.any():
                correct = (
                    confidence_df.loc[valid_predictions, pred_col].dt.date
                    == confidence_df.loc[valid_predictions, "label"].dt.date
                ).sum()
                accuracy = correct / valid_predictions.sum()
            else:
                accuracy = 0
            row[display_name] = accuracy

        rows.append(row)

    result = pd.DataFrame(rows).set_index("Confidence")
    return result.map(lambda x: f"{x * 100:.2f}%")


def run_confidence_analysis(
    label_dir: Path,
    results_dir: Path,
    reports_dir: Path,
    label_suffix: str,
    results_suffix: str,
) -> None:
    """Prints confidence distribution and module accuracy analysis tables."""
    print("\n📊 Starting confidence analysis...")

    df = load_confidence_analysis_data(label_dir, results_dir, label_suffix, results_suffix)
    if df.empty:
        print("No NSTS confidence data found.")
        return

    reports_dir.mkdir(parents=True, exist_ok=True)

    distribution_table = calculate_confidence_distribution_by_domain(df)
    distribution_path = reports_dir / "confidence_distribution.csv"
    distribution_report = distribution_table.T
    distribution_report.index.name = "Domain"
    distribution_report.to_csv(distribution_path)
    print(f"Saved report: {distribution_path}")

    accuracy_table = calculate_accuracy_by_confidence(df)
    accuracy_path = reports_dir / "confidence_accuracy.csv"
    accuracy_table.index.name = "Confidence"
    accuracy_table.to_csv(accuracy_path)
    print(f"Saved report: {accuracy_path}")

    print("\n✅ Confidence analysis complete.")
