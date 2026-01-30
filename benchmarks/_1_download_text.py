import json
from pathlib import Path

from nsts.web_scraper import fetch_website

def download_text_content(input_dir: Path, output_dir: Path, file_suffix: str) -> None:
    """
    Reads URL lists from input_dir, downloads content via Apify, 
    and saves raw data to output_dir.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    for url_file in input_dir.glob('*.json'):
        source_name = url_file.stem

        output_path = output_dir / f"{source_name}{file_suffix}"
        if output_path.exists():
            print(f"✅ Raw file already exists for source: {source_name}")
            continue

        print(f"🚀 Processing source: {source_name}")
        with open(url_file) as json_file:
            data = json.load(json_file)

        results = fetch_website(data)

        # Save results
        if results:
            print(f"💾 Saving {len(results)} to {output_path.name}")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4)
        else:
            print(f"🤷 No results returned for: {source_name}")