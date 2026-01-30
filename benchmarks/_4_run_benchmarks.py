import json
import ijson
from pathlib import Path
from typing import Any, Dict, List, Optional
import articleDateExtractor
from htmldate import find_date
from mcmetadata import extract
from openai import OpenAI
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

from nsts import NSTS
from nsts.metadata_extractor import extract_metadata

_SIMPLE_LLM_SYSTEM_PROMPT = (
    "You estimate the validity timestamp of a webpage: "
    "the point in time to which the webpage's current assertions belong. "
    "Return only JSON with one key named timestamp. "
    "Use YYYY-MM-DD when possible, or YYYY-MM or YYYY if only a partial date is available. "
    "If no reliable timestamp is available, return an empty string."
)


_SIMPLE_LLM_USER_TEMPLATE = (
    "Find the best timestamp for this webpage.\n\n"
    "URL:\n{url}\n\n"
    "Metadata:\n{metadata}\n\n"
    "Text:\n{text}"
)

def estimate_timestamp_with_simple_llm(url: str, metadata: str, text: str, llm_model: str = "gpt-4o-mini") -> str:
    """Estimates a webpage timestamp with a simple LLM prompt for benchmark comparison."""
    client = OpenAI()

    try:
        response = client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": _SIMPLE_LLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _SIMPLE_LLM_USER_TEMPLATE.format(
                        url=url or "",
                        metadata=metadata or "",
                        text=text or ""
                    )
                }
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        timestamp = parsed.get("timestamp", "")
        return timestamp if isinstance(timestamp, str) else ""
    except Exception as e:
        print(f"Error processing {url} with llm: {e}")
        return ""

def run_single_algorithm(algorithm_name: str, html_content: str, url: str) -> Optional[str]:
    """Executes a single date extraction algorithm on the given HTML content."""
    timestamp = ""
    try:
        if algorithm_name == "article_date_extractor":
            extracted_date = articleDateExtractor.extractArticlePublishedDate(url, html_content)
            if extracted_date:
                timestamp = extracted_date.strftime("%Y-%m-%d")
        elif algorithm_name == "htmldate":
            timestamp = find_date(html_content or url)
        elif algorithm_name == "mcmetadata":
            metadata = extract(url=url, html_text=html_content)
            pub_date = metadata.get("publication_date")
            if pub_date:
                timestamp = pub_date.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error processing {url} with {algorithm_name}: {e}")
    return timestamp

def run_benchmark_stream(algorithm_name: str, input_file: Path, result_file: Path):
    """
    Streams the input JSON file to reduce memory usage for baseline algorithms.
    Reads one item -> Processes it -> Appends result to memory list -> Writes final file.
    """
    results = []
    
    print(f"Streaming processing for {algorithm_name} on {input_file.name}...")
    
    # Open file in binary mode for ijson
    with open(input_file, 'rb') as f:
        # ijson.items yields objects one by one without loading the whole file
        # Assumes the JSON structure is a list of objects
        for item in tqdm(ijson.items(f, 'item'), desc=f"Running {algorithm_name}"):
            url = item.get("url")
            html = item.get("html")
            
            timestamp = run_single_algorithm(algorithm_name, html, url)
            results.append({"url": url, "timestamp": timestamp})

    print(f"Saving results to {result_file}...")
    with open(result_file, 'w', encoding='utf-8') as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

def run_llm_benchmark_stream(input_file: Path, result_file: Path):
    """
    Streams raw benchmark data and runs the simple LLM baseline.
    Uses URL, metadata extracted from HTML, and text for each item.
    """
    results = []

    print(f"Streaming processing for llm on {input_file.name}...")

    with open(input_file, 'rb') as f:
        for item in tqdm(ijson.items(f, 'item'), desc="Running llm"):
            url = item.get("url") or ""
            html = item.get("html") or ""
            text = item.get("text") or ""
            metadata = extract_metadata(html if html else url)

            timestamp = estimate_timestamp_with_simple_llm(url, metadata, text)
            results.append({"url": url, "timestamp": timestamp})

    print(f"Saving results to {result_file}...")
    with open(result_file, 'w', encoding='utf-8') as file:
        json.dump(results, file, indent=4, ensure_ascii=False)

def run_NSTS(runner: NSTS, input_file: Path, result_file: Path, cleaned_file: Path, use_boilerplate_removal: bool = True):
    mode_label = "Standard (with IGD)" if use_boilerplate_removal else "No-IGD (Original Text)"
    print(f"Running NSTS [{mode_label}] on {input_file.name}...")

    processed_light_data = []

    if use_boilerplate_removal:
        # --- STANDARD MODE: Check Cache or Run Boilerplate Removal ---
        if cleaned_file.exists():
            print(f"Step 1 & 2: Found cleaned file ({cleaned_file.name}). Loading directly...")
            with open(cleaned_file, 'r', encoding='utf-8') as f:
                processed_light_data = json.load(f)
        else:
            # --- PASS 1: Load Metadata (URL + Text) Only ---
            print("Step 1/3: Loading text and URLs (skipping HTML)...")
            light_data = []
            with open(input_file, 'rb') as f:
                for item in ijson.items(f, 'item'):
                    light_data.append({
                        "url": item.get("url"), 
                        "text": item.get("text")
                    })

            # --- PASS 2: Boilerplate Removal ---
            print("Step 2/3: Removing boilerplate from text...")
            processed_light_data = runner.remove_boilerplate(light_data)
            
            # Save intermediate cleaned data
            print(f"Saving cleaned intermediate data to {cleaned_file.name}...")
            with open(cleaned_file, 'w', encoding='utf-8') as f:
                json.dump(processed_light_data, f, indent=4, ensure_ascii=False)
    else:
        # --- NO-IGD MODE: Load Original Text Directly ---
        print("Step 1 & 2: Skipping boilerplate removal. Loading original text...")
        with open(input_file, 'rb') as f:
            for item in ijson.items(f, 'item'):
                processed_light_data.append({
                    "url": item.get("url"), 
                    "text": item.get("text") # Using original text directly
                })

    # --- PASS 3: Stream HTML and Process Item-by-Item ---
    print(f"Step 3/3: Streaming HTML and extracting timestamps ({mode_label})...")
    final_results = []
    
    with open(input_file, 'rb') as f:
        # Create a stream generator for the original file again to get HTML
        file_stream = ijson.items(f, 'item')
        
        # Zip the processed text data with the streaming raw HTML
        total_items = len(processed_light_data)
        
        for i, raw_item in tqdm(enumerate(file_stream), total=total_items, desc="NSTS Extraction"):
            processed_item = processed_light_data[i]
            
            # Sanity check
            if raw_item.get("url") != processed_item.get("url"):
                print(f"Warning: Mismatch at index {i}. Stream out of sync.")
                continue

            single_result = runner.get_timestamps(
                url=processed_item.get("url"),
                text=processed_item.get("text"),
                html=raw_item.get("html")
            )

            final_results.append(single_result)
            
    print(f"Saving NSTS results to {result_file}...")
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=4, ensure_ascii=False)

def run_benchmark_process(algorithms: List[str], input_dir: Path, output_dir: Path, file_suffix: str, intermediate_file_suffix: str):
    """Main function to run the benchmarking pipeline."""
    print("🚀 Starting benchmarking process...")

    for algo in algorithms:
        (output_dir / algo).mkdir(parents=True, exist_ok=True)
    
    # Initialize the runner once
    nsts_runner = NSTS()

    for raw_file in input_dir.glob('*.json'):
        source = raw_file.stem
        
        for algo in algorithms:
            output_folder = output_dir / algo
            result_file = output_folder / f"{source}{file_suffix}"
            cleaned_file = output_folder /  f"{source}{intermediate_file_suffix}"

            if result_file.exists():
                print(f"Results for '{algo}' on '{source}' found. Skipping.")
                continue

            if algo in ["article_date_extractor", "htmldate", "mcmetadata"]:
                run_benchmark_stream(algo, raw_file, result_file)

            elif algo == "llm":
                run_llm_benchmark_stream(raw_file, result_file)
            
            elif algo in ["nsts", "nsts_no_igd"] and nsts_runner:
                run_NSTS(
                    runner=nsts_runner, 
                    input_file=raw_file, 
                    result_file=result_file, 
                    cleaned_file=cleaned_file,
                    use_boilerplate_removal=algo == "nsts"
                )

    print("✅ Benchmarking complete.")
