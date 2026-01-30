import json
from pathlib import Path
from typing import List, Tuple, Dict
from typing import Optional
import pandas as pd
from dateutil import parser
import logging

BASELINE_REPORT_ALGORITHMS = [
    "article_date_extractor",
    "htmldate",
    "mcmetadata",
    "llm",
    "nsts",
]

INTERNAL_ABLATION_ALGORITHMS = [
    "PSR_Only (Neural)",
    "CPE_Only (Symbolic)",
    "nsts_no_igd",
    "nsts",
]

def safe_parse_date(date_str: Optional[str]) -> Optional[pd.Timestamp]:
    """
    Safely parses a date string into a pandas Timestamp object.

    Args:
        date_str: The string representation of the date.

    Returns:
        A pandas Timestamp object or None if parsing fails.
    """
    if not date_str:
        return None
    try:
        return parser.parse(date_str)
    except (ValueError, TypeError):
        logging.warning(f"Could not parse date string: {date_str}")
        return None

def load_data_for_evaluation(
    label_dir: Path,
    results_dir: Path,
    algorithms: List[str],
    label_suffix: str,
    results_suffix: str
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Loads label and result data, discovers LLM-only algorithms, and returns a comprehensive DataFrame.
    """
    records = []
    derived_predictions_by_algo: Dict[str, Dict] = {} 
    derived_algo_names: List[str] = []
    confidence_data_by_algo: Dict[str, Dict] = {}

    # First, gather all label data. Keep label rows rather than collapsing by URL,
    # because duplicated URLs in the benchmark should preserve the benchmark count.
    label_records = []
    for label_file in label_dir.glob(f"*{label_suffix}"):
        source = label_file.name.removesuffix(label_suffix)
        with open(label_file, 'r', encoding='utf-8') as f:
            label_data = json.load(f)
        for item in label_data:
            label_records.append({
                "url": item["url"],
                "source": source,
                "label": safe_parse_date(item.get("timestamp")),
            })

    # Gather results and discover LLM algorithms
    algo_results: Dict[str, Dict] = {}
    for source in {item["source"] for item in label_records if item.get("source")}:
        for algo in algorithms:
            result_file = results_dir / algo / f"{source}{results_suffix}"
            if not result_file.exists():
                continue

            with open(result_file, 'r', encoding='utf-8') as f:
                result_data = json.load(f)

            if algo not in algo_results:
                algo_results[algo] = {}
            algo_results[algo].update({
                item['url']: safe_parse_date(item.get('timestamp')) for item in result_data
            })

            if algo == 'nsts':
                if algo not in confidence_data_by_algo:
                    confidence_data_by_algo[algo] = {}
                
                clean_conf_map = {}
                for item in result_data:
                    if 'system_confidence' in item:
                        conf_val = item.get('system_confidence')
                        if isinstance(conf_val, str):
                            conf_val = conf_val.strip().lower()
                            # Treat empty strings as None so they are filtered out later
                            if not conf_val:
                                conf_val = None
                        clean_conf_map[item['url']] = conf_val
                
                confidence_data_by_algo[algo].update(clean_conf_map)

                # --- LLM-Only Extraction ---
                current_llm_preds = {item['url']: safe_parse_date(item.get('psr_timestamp')) for item in result_data if item.get('psr_timestamp')}
                if current_llm_preds:
                    new_llm_algo_name = f"PSR_Only (Neural)"
                    if new_llm_algo_name not in derived_predictions_by_algo:
                        derived_predictions_by_algo[new_llm_algo_name] = {}
                        derived_algo_names.append(new_llm_algo_name)
                    derived_predictions_by_algo[new_llm_algo_name].update(current_llm_preds)

                # --- Regex-Only Extraction ---
                current_regex_preds = {item['url']: safe_parse_date(item.get('cpe_timestamp')) for item in result_data if item.get('cpe_timestamp')}
                if current_regex_preds:
                    new_regex_algo_name = f"CPE_Only (Symbolic)"
                    if new_regex_algo_name not in derived_predictions_by_algo:
                        derived_predictions_by_algo[new_regex_algo_name] = {}
                        derived_algo_names.append(new_regex_algo_name)
                    derived_predictions_by_algo[new_regex_algo_name].update(current_regex_preds)

    # Create the base DataFrame
    for item in label_records:
        if pd.notna(item["label"]):
            records.append(item)
    df = pd.DataFrame(records)

    # Add prediction columns for all discovered algorithms
    all_algorithms = algorithms + derived_algo_names
    all_predictions = {**algo_results, **derived_predictions_by_algo}

    for algo in all_algorithms:
        pred_map = all_predictions.get(algo, {})
        df[f"{algo}_pred"] = df['url'].map(pred_map)

        if algo in confidence_data_by_algo:
            conf_map = confidence_data_by_algo.get(algo, {})
            df[f"{algo}_confidence"] = df['url'].map(conf_map)

    return df, all_algorithms


def calculate_accuracy(df: pd.DataFrame, algorithms: List[str]) -> pd.DataFrame:
    """Calculates accuracy for a given list of algorithms and pivots results."""
    df['label'] = pd.to_datetime(df['label'], errors='coerce')

    for algo in algorithms:
        pred_col = f"{algo}_pred"
        df[pred_col] = pd.to_datetime(df[pred_col], errors='coerce')
        df[f"{algo}_correct"] = (df[pred_col].dt.date == df['label'].dt.date)

    summary_data = []
    sources = df['source'].unique()
    for source in sources:
        source_df = df[df['source'] == source]
        for algo in algorithms:
            correct = source_df[f"{algo}_correct"].sum()
            total = source_df[f"{algo}_pred"].notna().sum()
            accuracy = correct / total if total > 0 else 0
            summary_data.append({"Source": source, "Algorithm": algo, "Accuracy": accuracy})
    
    for algo in algorithms:
        overall_correct = df[f"{algo}_correct"].sum()
        overall_total = df[f"{algo}_pred"].notna().sum()
        overall_accuracy = overall_correct / overall_total if overall_total > 0 else 0
        summary_data.append({"Source": "Overall", "Algorithm": algo, "Accuracy": overall_accuracy})

    summary_df = pd.DataFrame(summary_data)
    avg_df = summary_df[~summary_df['Source'].isin(['Overall', 'Average'])].groupby('Algorithm')['Accuracy'].mean().reset_index()
    avg_df['Source'] = 'Average'
    
    final_summary = pd.concat([summary_df, avg_df], ignore_index=True)
    pivot = final_summary.pivot_table(index='Algorithm', columns='Source', values='Accuracy', fill_value=0)
    
    source_cols = sorted([col for col in pivot.columns if col not in ['Overall', 'Average']])
    ordered_cols = source_cols + ['Overall', 'Average']
    pivot = pivot[ordered_cols]
    
    return pivot.map(lambda x: f"{x * 100:.2f}%")

def save_report(report: pd.DataFrame, reports_dir: Path, filename: str) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / filename
    output_report = report.T
    output_report.index.name = "Domain"
    output_report.to_csv(output_path)
    print(f"Saved report: {output_path}")

def save_selected_rows(
    accuracy_report: pd.DataFrame,
    row_names: List[str],
    reports_dir: Path,
    filename: str
) -> None:
    existing_rows = [row for row in row_names if row in accuracy_report.index]
    report = accuracy_report.loc[existing_rows]
    save_report(report, reports_dir, filename)

def calculate_confidence_distribution(df: pd.DataFrame, target_algo: str) -> pd.DataFrame:
    conf_col = f"{target_algo}_confidence"
    
    if conf_col not in df.columns:
        print(f"⚠️ Column '{conf_col}' not found. Cannot calculate confidence distribution.")
        return pd.DataFrame()

    # Filter df where we actually have confidence values
    df_conf = df[df[conf_col].notna()].copy()
    
    if df_conf.empty:
        print(f"⚠️ No confidence values found for {target_algo}.")
        return pd.DataFrame()

    # Normalize confidence values to lowercase for consistent sorting/grouping
    df_conf[conf_col] = df_conf[conf_col].astype(str).str.lower()

    # 1. Calculate distribution per Source
    # crosstab gives counts, normalize='columns' gives proportions (0-1)
    dist_per_source = pd.crosstab(
        index=df_conf[conf_col], 
        columns=df_conf['source'], 
        normalize='columns'
    )
    
    # Rename source columns to include count: "Source (N)"
    source_counts = df_conf['source'].value_counts()
    dist_per_source.columns = [f"{col} ({source_counts.get(col, 0)})" for col in dist_per_source.columns]

    # 2. Calculate Overall distribution (weighted by instance count)
    dist_overall = df_conf[conf_col].value_counts(normalize=True)
    dist_overall.name = f"Overall ({len(df_conf)})"

    # 3. Calculate Average distribution (macro-average across sources)
    # We take the mean across the per-source columns
    dist_average = dist_per_source.mean(axis=1)
    dist_average.name = "Average"

    # 4. Combine all parts
    final_dist = pd.concat([dist_per_source, dist_overall, dist_average], axis=1)

    # 5. Enforce Logical Sort Order (High -> Medium -> Low)
    # Define preferred order. Any labels not in this list will appear at the end.
    sort_order = ['high', 'medium', 'low', 'conflicted', 'none']
    final_dist = final_dist.reindex(index=sort_order)
    
    # Drop rows that might be all NaN (if a category didn't exist in data)
    final_dist = final_dist.dropna(how='all')

    # 6. Format as percentage strings and fill NaNs with 0
    final_dist = final_dist.fillna(0).map(lambda x: f"{x * 100:.2f}%")
    
    return final_dist

def run_evaluation(
    label_dir: Path,
    results_dir: Path,
    reports_dir: Path,
    algorithms: List[str],
    label_suffix: str,
    results_suffix: str
):
    """Main function to run the evaluation and reporting pipeline."""
    print("📊 Starting evaluation...")
    
    # Load all data and discover which algorithms are LLM-based
    eval_df, all_algorithms = load_data_for_evaluation(label_dir, results_dir, algorithms, label_suffix, results_suffix)

    if eval_df.empty:
        print("No data found for evaluation.")
        return

    accuracy_report = calculate_accuracy(eval_df, all_algorithms)
    save_selected_rows(
        accuracy_report,
        BASELINE_REPORT_ALGORITHMS,
        reports_dir,
        "baseline_comparison.csv"
    )
    save_selected_rows(
        accuracy_report,
        INTERNAL_ABLATION_ALGORITHMS,
        reports_dir,
        "internal_ablation.csv"
    )

    print("\n✅ Evaluation complete.")
