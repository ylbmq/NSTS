import argparse
from dotenv import load_dotenv

from nsts import NSTS

load_dotenv()

def main():
    """
    A demonstration script to fetch and display the timestamp for a given URL.
    """
    parser = argparse.ArgumentParser(description="Extract the timestamp from a web page.")
    parser.add_argument(
        "url",
        nargs="?",  # Makes the URL optional
        default="https://support.google.com/chrome/thread/385622697/chrome-notifications-are-not-opening-windows-11?hl=en",
        help="The URL of the article to analyze."
    )
    args = parser.parse_args()

    print(f"🚀 Analyzing URL: {args.url}")

    # Initialize the library's main class
    nsts = NSTS()

    # Get the timestamp and other metadata
    result = nsts.get_timestamps(args.url)

    # Print the results in a clean, readable format
    print("\n--- Full Results ---")
    print(f"Final Chosen Timestamp: {result['timestamp']}")
    print("----------------------")
    print(f"  - PSR Timestamp: {result['psr_timestamp']}")
    print(f"  - CPE Timestamp: {result['cpe_timestamp']}")
    print(f"  - System Confidence: {result['system_confidence']}")
    print("----------------------")

if __name__ == "__main__":
    main()