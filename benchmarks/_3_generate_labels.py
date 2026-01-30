import json
import ijson
import re
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from typing import Dict, Optional, Callable

def label_apple(html: str) -> Optional[str]:
    """Extracts timestamp from www.apple.com based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')
    span = soup.find("span", class_="category-eyebrow__date")
    if span:
        timestamp_str = span.get_text(strip=True)
        dt = datetime.strptime(timestamp_str, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    return None

def label_au(html: str) -> Optional[str]:
    """Extracts the latest timestamp from a Ask Ubuntu page."""
    soup = BeautifulSoup(html, 'html.parser')
    time_tags = soup.find_all('span', class_=['relativetime', 'relativetime-clean'])
    timestamps = []
    for tag in time_tags:
        if tag.has_attr('title'):
            timestamp_str = tag['title']
            dt_object = datetime.strptime(timestamp_str[:10], '%Y-%m-%d')
            timestamps.append(dt_object)        
    if timestamps:
        return max(timestamps).strftime('%Y-%m-%d') 
    return None

def label_cafnr(html: str) -> Optional[str]:
    """Extracts timestamp from cafnr.missouri.edu based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')
    p = soup.find_all("p", class_="cafnr-article__date")
    if len(p) == 1:
        timestamp_str = p[0].get_text(strip=True)
        timestamp_str = re.sub(r'\b([A-Za-z]{3})\.', r'\1', timestamp_str)
        timestamp_str = timestamp_str.replace("Sept", "Sep")
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(timestamp_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None

def label_coas(html: str) -> Optional[str]:
    """Extracts timestamp from coas.missouri.edu based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')
    div = soup.find("div", class_="field--name-node-post-date")
    if div:
        timestamp_str = div.get_text(strip=True)
        timestamp_str = re.sub(r'(\d{2}:\d{2})\s*[apAP][mM]', r'\1', timestamp_str)
        dt = datetime.strptime(timestamp_str, "%A, %B %d, %Y - %H:%M")
        return dt.strftime("%Y-%m-%d")
    return None

def label_google(html: str) -> Optional[str]:
    """Extracts the latest timestamp from support.google.com based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')
    divs = soup.find_all('div', class_="scTailwindThreadPost_headerPostdateroot")
    timestamps = []
    for div in divs:
        timestamp_str = div.get_text(strip=True)
        dt_object = datetime.strptime(timestamp_str, '%b %d, %Y')
        timestamps.append(dt_object)        
    if timestamps:
        return max(timestamps).strftime('%Y-%m-%d') 
    return None

def label_healthline(html: str) -> Optional[str]:
    """Extracts timestamp from www.healthline.com based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')

    section = soup.find("section", class_="css-4baf7j")
    if section:
        divs = section.find_all("div", recursive=False)
        if len(divs) >= 2:
            target_div = divs[1]
            spans = target_div.find_all("span")
            for span in reversed(spans):
                text = span.get_text(strip=True)
                text = text.replace("Updated on ", "").replace("on ", "")
                try:
                    dt = datetime.strptime(text, "%B %d, %Y")
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None

def label_hollywood(html: str) -> Optional[str]:
    """Extracts timestamp from www.hollywoodreporter.edu based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')
    time = soup.find("time", class_="lrv-u-color-black")
    if time:
        timestamp_str = time.get_text(strip=True)
        timestamp_str = timestamp_str.replace("am", "AM").replace("pm", "PM")
        formats = [
            "%B %d, %Y %I:%M%p",  # Format 1: August 2, 2024 8:10AM
            "%B %d, %Y"           # Format 2: November 14, 2022
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None

def label_so(html: str) -> Optional[str]:
    """Extracts the latest timestamp from a Stack Overflow page."""
    soup = BeautifulSoup(html, 'html.parser')
    time_tags = soup.find_all('span', class_=['relativetime', 'relativetime-clean'])
    timestamps = []
    for tag in time_tags:
        if tag.has_attr('title'):
            timestamp_str = tag['title']
            dt_object = datetime.strptime(timestamp_str[:10], '%Y-%m-%d')
            timestamps.append(dt_object)        
    if timestamps:
        return max(timestamps).strftime('%Y-%m-%d') 
    return None

def label_toh(html: str) -> Optional[str]:
    """Extracts timestamp from www.tasteofhome.com based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')
    p_tag = soup.find("p", class_="post-updated-date")
    if p_tag:
        span = p_tag.find("span")
        if span:
            span.decompose()
        timestamp_str = p_tag.get_text(strip=True)
        timestamp_str = re.sub(r'\b([A-Za-z]{3})\.', r'\1', timestamp_str)
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(timestamp_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None

def label_treasury(html: str) -> Optional[str]:
    """Extracts timestamp from home.treasury.gov based on HTML class."""
    soup = BeautifulSoup(html, 'html.parser')
    date_div = soup.find("div", class_="field--name-field-news-publication-date")
    if date_div:
        time_tag = date_div.find("time")
        if time_tag and time_tag.get('datetime'):
            return time_tag.get('datetime').split('T')[0]
            
    return None

def label_voa(html: str) -> Optional[str]:
    """Extracts timestamp from voanews.com based on HTML classes."""
    soup = BeautifulSoup(html, 'html.parser')
    date_spans = soup.find_all("span", class_="date")
    timestamp_str = None
    if len(date_spans) == 2:
        for date_span in date_spans:
            if date_span.find("span", class_="badge badge--updated"):
                time_tag = date_span.find("time", attrs={"datetime": True})
                if time_tag:
                    timestamp_str = time_tag.get_text(strip=True)
                    break
    elif len(date_spans) == 1:
        time_tag = date_spans[0].find("time", attrs={"pubdate": "pubdate", "datetime": True})
        if time_tag:
            timestamp_str = time_tag.get_text(strip=True)

    if timestamp_str:
        timestamp_str = timestamp_str.replace("Last Updated: ", "")
        timestamp_str = re.sub(r'\b0:(\d{2})\s*(AM|PM)', r'12:\1 \2', timestamp_str, flags=re.IGNORECASE)
        dt = datetime.strptime(timestamp_str, "%B %d, %Y %I:%M %p")
        return dt.strftime("%Y-%m-%d")
    
    return None

LABEL_DISPATCHER: Dict[str, Callable[[str], Optional[str]]] = {
    "apple": label_apple,
    "au": label_au,
    "cafnr": label_cafnr,
    "coas": label_coas,
    "google": label_google,
    "healthline": label_healthline,
    "hollywood": label_hollywood,
    "so": label_so,
    "toh": label_toh,
    "treasury": label_treasury,
    "voa": label_voa,
}

def run_label_generation(input_dir: Path, output_dir: Path, file_suffix: str):
    """
    Finds HTML files, groups them by source, and runs the labeling process
    using streaming to prevent Out of Memory (OOM) errors.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for raw_file in input_dir.glob('*.json'):
        source = raw_file.stem
        label_file = output_dir / f"{source}{file_suffix}"
        
        if label_file.exists():
            print(f"✅ Label file already exists for source: {source}")
            continue

        label_fn = LABEL_DISPATCHER.get(source)
        if not label_fn:
            print(f"⏩ Skipping {source} (No label function defined)")
            continue
        
        results = []
        with open(raw_file, 'rb') as f:
            items = ijson.items(f, 'item')
            
            desc = f"Processing {source}"
            for item in tqdm(items, desc=desc, unit="item"):
                if timestamp := label_fn(item.get("html", "")):
                    results.append({
                        "url": item["url"],
                        "timestamp": timestamp,
                    })

        # Save results
        if results:
            print(f"💾 Saving {len(results)} labels to {label_file}")
            with open(label_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4)
        else:
            print(f"🤷 No labels found for source: {source}")