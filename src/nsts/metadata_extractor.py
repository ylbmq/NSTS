from urllib3.util.retry import Retry
import requests
from requests.adapters import HTTPAdapter
import requests
from bs4 import BeautifulSoup
import re

def _request_http(url: str, timeout: int = 10, retries: int = 2, backoff_factor: float = 0.3) -> requests.Response:
    """Makes an HTTP GET request to the specified URL with retry logic."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504],  # retry on these status codes
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session.get(url, timeout=timeout)

def extract_metadata(source: str) -> str:
    """
    Fetches or uses HTML content to extract metadata from the <head> section.
    This includes the <title> tag and all <meta> tags.

    The function automatically detects if the source is a URL (starts with http/https)
    or a raw HTML string.

    Args:
        source (str): The URL of the webpage or the raw HTML content string.

    Returns:
        str: A string containing the extracted HTML metadata (title and meta tags),
             each on a new line, or an empty string if fetching/parsing fails or
             no <head> section is found.
    """
    html_content = None
    if re.match(r'^https?://', source):
        try:
            # Send an HTTP GET request to get the full HTML content
            response = _request_http(source)
            if response.status_code == 200:
                html_content = response.content
            else:
                print(f"Failed to fetch page for {source}, status code: {response.status_code}")
                return ""
        except requests.RequestException as e:
            print(f"Error fetching page for URL {source}: {e}")
            return ""
    else:
        # If it's not a URL, treat it as a raw HTML string
        html_content = source
    
    if not html_content:
        return ""

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        head = soup.head
        
        if head:
            metadata = ""
            # Extract the <title> tag
            title_tag = head.find("title")
            if title_tag:
                metadata += f"<title>{title_tag.get_text(strip=True)}</title>\n"

            # Extract metadata from meta tags
            meta_tags = head.find_all('meta')
            for meta in meta_tags:
                # Create the tag string
                attributes = ' '.join([f'{attr}="{value}"' for attr, value in meta.attrs.items()])
                tag_string = f"<meta {attributes}>"
                metadata += tag_string + "\n"

            return metadata
        else:
            print("No <head> section found in the provided source.")
    except Exception as e:
        print(f"An error occurred during HTML parsing: {e}")
    
    return ""