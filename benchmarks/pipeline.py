import sys
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from _1_download_text import download_text_content
from _2_download_html import download_html_content
from _3_generate_labels import run_label_generation
from _4_run_benchmarks import run_benchmark_process
from _5_evaluate_results import run_evaluation
from _6_evaluate_symbolic_partner_ablation import run_symbolic_partner_ablation
from _7_evaluate_confidence_analysis import run_confidence_analysis
from _8_generate_figures import run_figure_generation

# --- Core Paths ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

URL_DIR = DATA_DIR / "url"
RAW_DIR = DATA_DIR / "raw"
HTML_DIR = RAW_DIR / "temp"
LABEL_DIR = DATA_DIR / "labels"
RESULTS_DIR = DATA_DIR / "results"
REPORTS_DIR = DATA_DIR / "reports"
ABLATION_DIR = RESULTS_DIR / "symbolic_partner_ablation"

# --- Algorithm & File Constants ---
ALGORITHMS = ["article_date_extractor", "htmldate", "mcmetadata", "llm", "nsts", "nsts_no_igd"]
SYMBOLIC_PARTNER_ALGORITHMS = [
    "article_date_extractor_psr_udg",
    "htmldate_psr_udg",
    "mcmetadata_psr_udg",
]
REPORT_FILENAMES = [
    "baseline_comparison.csv",
    "internal_ablation.csv",
    "symbolic_partner_ablation.csv",
    "confidence_distribution.csv",
    "confidence_accuracy.csv",
]
FIGURE_FILENAMES = [
    "figures/confidence_accuracy.png",
]
RAW_SUFFIX = ".json"
LABEL_SUFFIX = "_labels.json"
CLEANED_SUFFIX = "_cleaned.json"
RESULTS_SUFFIX = "_results.json"


def get_sources() -> list[str]:
    return sorted(path.stem for path in URL_DIR.glob(f"*{RAW_SUFFIX}"))


def existing_reports() -> list[Path]:
    report_paths = [
        REPORTS_DIR / filename
        for filename in REPORT_FILENAMES + FIGURE_FILENAMES
        if (REPORTS_DIR / filename).exists()
    ]
    return report_paths


def source_downstream_files(source: str) -> list[Path]:
    files = []

    label_file = LABEL_DIR / f"{source}{LABEL_SUFFIX}"
    if label_file.exists():
        files.append(label_file)

    if RESULTS_DIR.exists():
        files.extend(path for path in RESULTS_DIR.glob(f"*/{source}{RESULTS_SUFFIX}") if path.exists())

    if ABLATION_DIR.exists():
        files.extend(path for path in ABLATION_DIR.glob(f"*/{source}{RESULTS_SUFFIX}") if path.exists())

    return sorted(set(files))


def source_ablation_files(source: str) -> list[Path]:
    if not ABLATION_DIR.exists():
        return []
    return sorted(path for path in ABLATION_DIR.glob(f"*/{source}{RESULTS_SUFFIX}") if path.exists())


def missing_raw_sources(sources: list[str]) -> list[str]:
    return [source for source in sources if not (RAW_DIR / f"{source}{RAW_SUFFIX}").exists()]


def missing_label_sources(sources: list[str]) -> list[str]:
    return [source for source in sources if not (LABEL_DIR / f"{source}{LABEL_SUFFIX}").exists()]


def missing_result_sources(sources: list[str]) -> dict[str, list[str]]:
    missing = {}
    for source in sources:
        missing_algorithms = [
            algorithm
            for algorithm in ALGORITHMS
            if not (RESULTS_DIR / algorithm / f"{source}{RESULTS_SUFFIX}").exists()
        ]
        if missing_algorithms:
            missing[source] = missing_algorithms
    return missing


def missing_ablation_sources(sources: list[str]) -> dict[str, list[str]]:
    missing = {}
    for source in sources:
        missing_algorithms = [
            algorithm
            for algorithm in SYMBOLIC_PARTNER_ALGORITHMS
            if not (ABLATION_DIR / algorithm / f"{source}{RESULTS_SUFFIX}").exists()
        ]
        if missing_algorithms:
            missing[source] = missing_algorithms
    return missing


def build_deletion_plan(sources: list[str]) -> tuple[list[Path], list[str]]:
    raw_missing = missing_raw_sources(sources)
    labels_missing = missing_label_sources(sources)
    results_missing = missing_result_sources(sources)
    ablations_missing = missing_ablation_sources(sources)

    deletion_paths = []
    reasons = []

    for source in raw_missing:
        stale_files = source_downstream_files(source)
        deletion_paths.extend(stale_files)
        if stale_files:
            reasons.append(f"Raw data for '{source}' is missing; downstream files would be stale.")

    for source in results_missing:
        stale_files = source_ablation_files(source)
        deletion_paths.extend(stale_files)
        if stale_files:
            reasons.append(f"Benchmark results for '{source}' are incomplete; derived ablation files would be stale.")

    pipeline_will_generate = bool(raw_missing or labels_missing or results_missing or ablations_missing)
    if pipeline_will_generate:
        report_files = existing_reports()
        deletion_paths.extend(report_files)
        if report_files:
            reasons.append("Reports will be regenerated from current benchmark artifacts.")

    return sorted(set(deletion_paths)), reasons


def build_source_regeneration_plan(source: str) -> tuple[list[Path], list[str]]:
    if source not in get_sources():
        raise ValueError(f"Unknown source '{source}'. Expected one of: {', '.join(get_sources())}")

    deletion_paths = source_downstream_files(source) + existing_reports()
    reasons = [
        f"Preflight simulation: if raw data for '{source}' were regenerated, these downstream files would become stale.",
        "This is a dry run; no files will be changed.",
    ]
    return sorted(set(deletion_paths)), reasons


def print_deletion_plan(paths: list[Path], reasons: list[str]) -> None:
    if reasons:
        print("\nReasons:")
        for reason in reasons:
            print(f"- {reason}")

    if paths:
        print("\nFiles planned for deletion:")
        for path in paths:
            print(f"- {path}")
    else:
        print("\nNo deletions are needed.")


def confirm_deletions(paths: list[Path], reasons: list[str]) -> None:
    if not paths:
        return

    print("\n⚠️  The pipeline must delete stale downstream files before running.")
    print_deletion_plan(paths, reasons)
    user_input = input("\nProceed with deletion and pipeline run? (y/N): ").strip().lower()
    if user_input != "y":
        print("Operation cancelled. No files were deleted.")
        sys.exit(0)


def delete_files(paths: list[Path]) -> None:
    for path in paths:
        if path.exists() and path.is_file():
            path.unlink()
            print(f"Deleted stale file: {path}")


def run_full_pipeline() -> None:
    """Runs or resumes the complete dependency-aware pipeline."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/8] Downloading missing text content...")
    download_text_content(URL_DIR, RAW_DIR, RAW_SUFFIX)

    print("\n[2/8] Downloading missing HTML content...")
    download_html_content(RAW_DIR, HTML_DIR)

    print("\n[3/8] Generating missing labels...")
    run_label_generation(RAW_DIR, LABEL_DIR, LABEL_SUFFIX)

    print("\n[4/8] Running missing benchmarks...")
    run_benchmark_process(ALGORITHMS, RAW_DIR, RESULTS_DIR, RESULTS_SUFFIX, CLEANED_SUFFIX)

    print("\n[5/8] Saving evaluation reports...")
    run_evaluation(LABEL_DIR, RESULTS_DIR, REPORTS_DIR, ALGORITHMS, LABEL_SUFFIX, RESULTS_SUFFIX)

    print("\n[6/8] Saving symbolic partner ablation report...")
    run_symbolic_partner_ablation(LABEL_DIR, RESULTS_DIR, REPORTS_DIR, LABEL_SUFFIX, RESULTS_SUFFIX)

    print("\n[7/8] Saving confidence analysis reports...")
    run_confidence_analysis(LABEL_DIR, RESULTS_DIR, REPORTS_DIR, LABEL_SUFFIX, RESULTS_SUFFIX)

    print("\n[8/8] Generating report figures...")
    run_figure_generation(REPORTS_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dependency-aware benchmark pipeline manager")
    parser.add_argument(
        "--preflight-source",
        help="Show the downstream deletion plan for one source without changing files.",
    )
    args = parser.parse_args()

    print("==========================================")
    print("🔄 PIPELINE MANAGER")
    print("==========================================")

    if args.preflight_source:
        paths, reasons = build_source_regeneration_plan(args.preflight_source)
        print_deletion_plan(paths, reasons)
        print("\nDry run complete. No files were changed.")
        return

    sources = get_sources()
    deletion_paths, reasons = build_deletion_plan(sources)
    confirm_deletions(deletion_paths, reasons)
    delete_files(deletion_paths)
    run_full_pipeline()

    print("\n==========================================")
    print("✅ COMPLETED SUCCESSFULLY")
    print("==========================================")


if __name__ == "__main__":
    main()
