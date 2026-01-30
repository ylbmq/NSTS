import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
from _5_evaluate_results import safe_parse_date

ABLATION_DIR_NAME = "symbolic_partner_ablation"

SYMBOLIC_PARTNERS = {
    "article_date_extractor": {
        "output_name": "article_date_extractor_psr_udg",
        "display_name": "ArticleDateExtractor + PSR + UDG",
    },
    "htmldate": {
        "output_name": "htmldate_psr_udg",
        "display_name": "Htmldate + PSR + UDG",
    },
    "mcmetadata": {
        "output_name": "mcmetadata_psr_udg",
        "display_name": "McMetadata + PSR + UDG",
    },
}

NSTS_DISPLAY_NAME = "NSTS (CPE + PSR + UDG)"


def apply_udg_selection(
    psr_timestamp: Optional[str],
    system_confidence: Optional[str],
    symbolic_timestamp: Optional[str],
) -> str:
    """Applies the same PSR-vs-symbolic selection rule used by NSTS."""
    psr_timestamp = psr_timestamp or ""
    symbolic_timestamp = symbolic_timestamp or ""
    confidence = (system_confidence or "").strip().lower()

    if psr_timestamp not in ("", "none") and (
        not symbolic_timestamp or confidence in ["high", "medium"]
    ):
        return psr_timestamp
    return symbolic_timestamp


def load_results_by_url(result_file: Path) -> Dict[str, dict]:
    if not result_file.exists():
        return {}

    with open(result_file, "r", encoding="utf-8") as f:
        return {item["url"]: item for item in json.load(f)}


def write_json(path: Path, data: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def generate_symbolic_partner_results(results_dir: Path, results_suffix: str) -> Dict[str, str]:
    """
    Generates derived PSR + UDG + symbolic-partner outputs from existing result files.

    Returns:
        A mapping from generated algorithm folder names to display names.
    """
    nsts_dir = results_dir / "nsts"
    ablation_root = results_dir / ABLATION_DIR_NAME
    generated_algorithms = {}

    if not nsts_dir.exists():
        print(f"⚠️ NSTS results not found at {nsts_dir}. Skipping symbolic partner ablation.")
        return generated_algorithms

    for nsts_file in sorted(nsts_dir.glob(f"*{results_suffix}")):
        source = nsts_file.name.removesuffix(results_suffix)
        nsts_by_url = load_results_by_url(nsts_file)

        for partner_name, config in SYMBOLIC_PARTNERS.items():
            partner_file = results_dir / partner_name / f"{source}{results_suffix}"
            partner_by_url = load_results_by_url(partner_file)

            if not partner_by_url:
                print(f"⚠️ Missing {partner_name} results for {source}. Skipping this source.")
                continue

            derived_results = []
            for url, nsts_item in nsts_by_url.items():
                symbolic_item = partner_by_url.get(url, {})
                symbolic_timestamp = symbolic_item.get("timestamp", "")
                psr_timestamp = nsts_item.get("psr_timestamp", "")
                system_confidence = nsts_item.get("system_confidence", "")

                derived_results.append({
                    "url": url,
                    "timestamp": apply_udg_selection(
                        psr_timestamp=psr_timestamp,
                        system_confidence=system_confidence,
                        symbolic_timestamp=symbolic_timestamp,
                    ),
                    "symbolic_timestamp": symbolic_timestamp,
                    "psr_timestamp": psr_timestamp,
                    "system_confidence": system_confidence,
                    "symbolic_partner": partner_name,
                })

            output_name = config["output_name"]
            output_file = ablation_root / output_name / f"{source}{results_suffix}"
            write_json(output_file, derived_results)
            generated_algorithms[output_name] = config["display_name"]

    return generated_algorithms


def load_labels(label_dir: Path, label_suffix: str) -> pd.DataFrame:
    records = []

    for label_file in label_dir.glob(f"*{label_suffix}"):
        source = label_file.name.removesuffix(label_suffix)
        with open(label_file, "r", encoding="utf-8") as f:
            label_data = json.load(f)

        for item in label_data:
            label = safe_parse_date(item.get("timestamp"))
            if pd.notna(label):
                records.append({
                    "url": item["url"],
                    "source": source,
                    "label": label,
                })

    return pd.DataFrame(records)


def load_predictions(
    results_dir: Path,
    algorithm_sources: Dict[str, Path],
    results_suffix: str,
) -> Dict[str, Dict[str, pd.Timestamp]]:
    predictions = {}

    for algorithm_name, algorithm_dir in algorithm_sources.items():
        pred_map = {}
        for result_file in algorithm_dir.glob(f"*{results_suffix}"):
            with open(result_file, "r", encoding="utf-8") as f:
                result_data = json.load(f)
            pred_map.update({
                item["url"]: safe_parse_date(item.get("timestamp"))
                for item in result_data
            })
        predictions[algorithm_name] = pred_map

    return predictions


def calculate_ablation_accuracy(
    labels_df: pd.DataFrame,
    algorithm_display_names: Dict[str, str],
    predictions: Dict[str, Dict[str, pd.Timestamp]],
) -> pd.DataFrame:
    df = labels_df.copy()
    df["label"] = pd.to_datetime(df["label"], errors="coerce")

    summary_data = []
    sources = sorted(df["source"].unique())

    for algorithm_name, display_name in algorithm_display_names.items():
        pred_col = f"{algorithm_name}_pred"
        correct_col = f"{algorithm_name}_correct"
        df[pred_col] = df["url"].map(predictions.get(algorithm_name, {}))
        df[pred_col] = pd.to_datetime(df[pred_col], errors="coerce")
        df[correct_col] = df[pred_col].dt.date == df["label"].dt.date

        for source in sources:
            source_df = df[df["source"] == source]
            correct = source_df[correct_col].sum()
            total = source_df[pred_col].notna().sum()
            accuracy = correct / total if total > 0 else 0
            summary_data.append({
                "Source": source,
                "Algorithm": display_name,
                "Accuracy": accuracy,
            })

        overall_correct = df[correct_col].sum()
        overall_total = df[pred_col].notna().sum()
        overall_accuracy = overall_correct / overall_total if overall_total > 0 else 0
        summary_data.append({
            "Source": "Overall",
            "Algorithm": display_name,
            "Accuracy": overall_accuracy,
        })

    summary_df = pd.DataFrame(summary_data)
    avg_df = (
        summary_df[~summary_df["Source"].isin(["Overall", "Average"])]
        .groupby("Algorithm")["Accuracy"]
        .mean()
        .reset_index()
    )
    avg_df["Source"] = "Average"

    final_summary = pd.concat([summary_df, avg_df], ignore_index=True)
    pivot = final_summary.pivot_table(
        index="Algorithm",
        columns="Source",
        values="Accuracy",
        fill_value=0,
        sort=False,
    )

    source_cols = sorted([col for col in pivot.columns if col not in ["Overall", "Average"]])
    pivot = pivot[source_cols + ["Overall", "Average"]]
    row_order = list(algorithm_display_names.values())
    pivot = pivot.reindex(row_order)

    return pivot.map(lambda x: f"{x * 100:.2f}%")


def run_symbolic_partner_ablation(
    label_dir: Path,
    results_dir: Path,
    reports_dir: Path,
    label_suffix: str,
    results_suffix: str,
) -> None:
    """Generates and evaluates the symbolic partner ablation table."""
    print("\n📊 Starting symbolic partner ablation...")

    generated_algorithms = generate_symbolic_partner_results(results_dir, results_suffix)
    if not generated_algorithms:
        print("No symbolic partner ablation results were generated.")
        return

    labels_df = load_labels(label_dir, label_suffix)
    if labels_df.empty:
        print("No labels found for symbolic partner ablation.")
        return

    algorithm_display_names = {
        **generated_algorithms,
        "nsts": NSTS_DISPLAY_NAME,
    }

    algorithm_sources = {
        name: results_dir / ABLATION_DIR_NAME / name
        for name in generated_algorithms
    }
    algorithm_sources["nsts"] = results_dir / "nsts"

    predictions = load_predictions(results_dir, algorithm_sources, results_suffix)
    accuracy_report = calculate_ablation_accuracy(
        labels_df=labels_df,
        algorithm_display_names=algorithm_display_names,
        predictions=predictions,
    )

    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / "symbolic_partner_ablation.csv"
    output_report = accuracy_report.T
    output_report.index.name = "Domain"
    output_report.to_csv(output_path)
    print(f"Saved report: {output_path}")
    print("\n✅ Symbolic partner ablation complete.")
