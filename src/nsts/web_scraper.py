from apify_client import ApifyClient
import time
import os

def fetch_website(url_input):
    """
    Crawls a given URL using the Apify Website Content Crawler actor and retrieves 
    the resulting dataset.

    Requires the APIFY_API_TOKEN environment variable to be set.

    Args:
        url_input: The starting URL to crawl.

    Returns:
        list[dict]: A list of dictionaries for each crawled item. Each dictionary contains:
            - 'url': The URL of the page.
            - 'html': The raw HTML content (or None if unavailable).
            - 'text': The extracted text content (or None if unavailable).

    Raises:
        Exception: If the Apify actor run fails or returns an unexpected status.
        KeyError: If the APIFY_API_TOKEN environment variable is not set.
    """
    apify_api_token = os.environ.get("APIFY_API_TOKEN")
    if not apify_api_token:
        raise KeyError("APIFY_API_TOKEN environment variable is not set.")
    
    # --- 1. NORMALIZE INPUT ---
    start_urls = []
    
    # If a single item (dict or string) was passed, wrap it in a list first
    if not isinstance(url_input, list):
        url_input = [url_input]

    for item in url_input:
        if isinstance(item, str):
            # Handle plain string URLs
            start_urls.append({"url": item, "method": "GET"})
        elif isinstance(item, dict) and "url" in item:
            # Handle dicts (works for both raw JSON and pre-formatted)
            start_urls.append({"url": item["url"], "method": "GET"})

    # --- 2. CONFIGURE RUN ---
    run_input = {
        "aggressivePrune": False,
        "clickElementsCssSelector": "[aria-expanded=\"false\"]",
        "clientSideMinChangePercentage": 15,
        "crawlerType": "playwright:adaptive",
        "debugLog": False,
        "debugMode": False,
        "expandIframes": True,
        "htmlTransformer": "none",
        "ignoreCanonicalUrl": False,
        "keepUrlFragments": False,
        "maxCrawlDepth": 0,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": []
        },
        "readableTextCharThreshold": 100,
        "removeCookieWarnings": True,
        "removeElementsCssSelector": "nav, footer, script, style, noscript, svg,\n[role=\"alert\"],\n[role=\"banner\"],\n[role=\"dialog\"],\n[role=\"alertdialog\"],\n[role=\"region\"][aria-label*=\"skip\" i],\n[aria-modal=\"true\"]",
        "renderingTypeDetectionPercentage": 10,
        "saveFiles": False,
        "saveHtml": True,
        "saveHtmlAsFile": False,
        "saveMarkdown": False,
        "saveScreenshots": False,
        "startUrls": start_urls,
        "useSitemaps": False,
        "includeUrlGlobs": [],
        "excludeUrlGlobs": [],
        "maxCrawlPages": 9999999,
        "initialConcurrency": 1,
        "maxConcurrency": 1,
        "initialCookies": [],
        "maxSessionRotations": 10,
        "maxRequestRetries": 5,
        "requestTimeoutSecs": 60,
        "minFileDownloadSpeedKBps": 128,
        "dynamicContentWaitSecs": 10,
        "waitForSelector": "",
        "maxScrollHeightPixels": 5000,
        "maxResults": 9999999
    }

    # --- 3. EXECUTE RUN ---
    client = ApifyClient(apify_api_token)
    run = client.actor("apify/website-content-crawler").start(run_input=run_input)
    id = run["id"]
    print("💾 Check your data here: https://console.apify.com/storage/datasets/" + id)

    while True:
        run = client.run(id).get()
        print(run["status"])

        if run["status"] == "SUCCEEDED":
            data = client.dataset(run["defaultDatasetId"]).list_items().items
            return [
                {
                    "url": item.get("url"),
                    "html": item.get("html"),
                    "text": item.get("text")
                }
                for item in data
            ]
        elif run["status"] == "RUNNING" or run["status"] == "READY":
            time.sleep(60)
        else:
            raise Exception(f"Run with ID {id} has an unexpected status: {run['status']}")