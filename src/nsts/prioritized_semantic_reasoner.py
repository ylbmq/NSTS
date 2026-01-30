import re
import json
from openai import OpenAI

_TIMESTAMP_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "get_timestamp",
            "description": "Analyzes webpage data to determine its timestamp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "labeled_dates_list": {
                        "type": "array",
                        "description": (
                            "A list of all explicit timestamps found in the text, "
                            "including the primary article, answers, and comments. This is a complete collection. "
                            "An explicit timestamp is in text identified by its label (e.g., 'published', 'updated', 'modified', 'edited', 'asked','answered') "
                            "or position (e.g., under a title, at the top or end of a comment). "
                            "To distinguish a relevant answer from an irrelevant 'related story', check content length; "
                            "ignore timestamps from short, title-only snippets. "
                            "Excludes narrative dates from sentence prose. Format as YYYY-MM-DD or partial."
                        ),
                        "items": {
                            "type": "string"
                        }
                    },
                    "timestamp": {
                        "type": "string",
                        "description": "The estimated timestamp of the MAIN article in 'YYYY-MM-DD' format. \
                        If only part of the timestamp is available, return the available portion (e.g., 'YYYY'). \
                        Return an empty string if no reliable timestamp is found."
                    },
                    "confidence_level": {
                        "type": "string",
                        "description": (
                            "Confidence in the chosen timestamp: 'high', 'low', or 'none'. "
                            "Use 'none' only if no reliable estimate can be made."
                        )
                    },
                    "source": {
                        "type": "string",
                        "description": "The single source used for estimating the timestamp. Possible values are: 'URL', 'text', 'metadata', or 'none'. \
                        If no time-related information is found, return 'none'."
                    }
                },
                "required": ["time", "confidence_level", "source"],
                "additionalProperties": False
            }
        }
    }
]

_SYSTEM_CONTENT = (
    "You are an expert timestamp detection agent. "
    "Your task is to analyze webpage data and identify the most accurate publication or modification date. "
    "Follow the rules and steps below with extreme precision.\n\n"

    "## Core Definitions\n\n"

    "Your most important task is to distinguish between an **\"Explicit Timestamp\"** and a **\"Narrative Date\"**.\n\n"
    "* **Explicit Timestamp (✅ Include in `explicit_dates_list`)**\n"
    "    * This is the publication or update date in **TEXT**, not in metadata or URL. "
    "This includes the timestamp for the **main article, as well as for individual answers or comments**.\n"
    "    * It can be identified in two ways:\n"
    "        1.  **By Label:** It has a preceding or succeeding keyword like "
    "**\"Published\"**, **\"Posted on\"**, **\"Updated\"**, **\"Last modified\"**, **\"edited\"**, **\"asked\"**, **\"answered\"**.\n"
    "            * *Example:* `Published on March 15, 2023` -> Add `2023-03-15`.\n"
    "        2.  **By Position:** It appears in a common timestamp location, even without a label. This includes:\n"
    "            * Directly under the article's main title.\n"
    "            * At the very top or end of a forum post, answer, or comment body.\n"
    "            * *Example:* A date like `March 15, 2023` appearing alone on a line "
    "between the headline and the first paragraph is an Explicit Timestamp.\n\n"
    "* **Narrative Date (❌ Exclude from `explicit_dates_list`)**\n"
    "    * A date mentioned as part of a regular sentence to describe a historical fact, an event, "
    "or other information within the content.\n"
    "    * It is embedded within the article's prose and is **not** the publication date of the article.\n"
    "    * *Example:* `The company was founded in 1998.` or `The study in March 2023 found...` -> "
    "**DO NOT** add these dates to the list.\n\n"

    "## Distinguishing Answers from Related Stories\n\n"
    "A list of related articles can look like a list of answers. Use content length to tell them apart:\n"
    "* **✅ Relevant Answer/Comment**: Has a substantial body of text (one or more paragraphs). "
    "Its timestamp **should** be included in `labeled_dates_list`.\n"
    "* **❌ Irrelevant Related Story**: Is usually just a title and a very short one-sentence snippet. "
    "Its timestamp **must be ignored** and excluded from the list.\n\n"

    "## Confidence Rubric\n"
    "Assign `confidence_level` exactly as follows:\n"
    "* `high`: The selected timestamp comes from exactly one clear user-facing Explicit Timestamp in the text, "
    "such as a publication, update, modification, asked, answered, or edited timestamp for the main content; "
    "or no clear explicit text timestamp is available, and the selected timestamp comes from metadata "
    "or from a full date in the URL.\n"
    "* `low`: The selected timestamp comes from a partial date, an ambiguous signal, multiple competing text timestamps, "
    "or a narrative date used only as a last resort.\n"
    "* `none`: No reliable timestamp can be found.\n"
    "Do not assign `high` to narrative dates, copyright years, sidebar dates, related-story dates, "
    "or unrelated event dates.\n\n"

    "---\n\n"

    "## Step-by-Step Instructions\n\n"
    
    "**Step 1: Populate `explicit_dates_list`**\n"
    "1.  Carefully read the main content TEXT, including any **answers or comments**.\n"
    "2.  Identify **only Explicit Timestamps** using the two methods (Label or Position) defined above.\n"
    "3.  Add every Explicit Timestamp found to the `explicit_dates_list`. Strip any time-of-day information.\n"
    "4.  **Crucially**, ignore all Narrative Dates. "
    "Also ignore dates from metadata, URLs, sidebars, or \"related articles\" sections at this stage.\n\n"
    "**Step 2: Determine Final Timestamp, Source, and Confidence**\n"
    "Follow this logic flow:\n\n"

    "* **If `explicit_dates_list` is NOT empty:**\n"
    "    1.  **timestamp**: Choose the most relevant date from the list (often the first or most prominent one).\n"
    "    2.  **source**: `text`.\n"
    "    3.  **confidence_level**:\n"
    "        * `high`: If there is exactly one Explicit Timestamp for the main article.\n"
    "        * `low`: If there are multiple timestamps (e.g., from comments or answers) "
    "making the primary article's date ambiguous.\n\n"

    "* **If `explicit_dates_list` IS empty:**\n"
    "    1.  Search for the best available date clue in this order of priority: **Metadata -> URL -> Text**.\n"
    "    2.  **timestamp**: The date you found.\n"
    "    3.  **source**: Where you found it (`metadata`, `URL`, or `text`).\n"
    "    4.  **confidence_level**:\n"
    "        * `high`: From explicit metadata fields like `published_time` and `dateModified` or a full date in the URL (e.g., `/2023/10/26/`).\n"
    "        * `low`: From a partial date (e.g., `/2023/archive/`) or from a Narrative Date in the text used as a last resort.\n\n"
    "* **If no date clues are found anywhere:**\n"
    "    * Set `timestamp` to `\"\"`, `confidence_level` to `none`, and `source` to `none`.\n\n"

    "Finally, use the 'get_timestamp' function to output:\n"
    "- 'timestamp': the estimated timestamp ('YYYY-MM-DD' or partial like 'YYYY-MM' or 'YYYY')\n"
    "- 'confidence_level': 'high', 'low', or 'none'\n"
    "- 'source': 'URL', 'text', 'metadata', or 'none'\n"
    "- 'labeled_dates_list': list of labeled dates "
)

_USER_TEMPLATE = (
    "Please analyze the following webpage data for its timestamp.\n\n"
    "**URL:** {url}\n"
    "**Text:** {text}\n"
    "**Metadata:** {metadata}\n\n"
    "---\n\n"
    "**Instructions:**\n\n"
    "**1. Understand \"Explicit Timestamp\" vs. \"Narrative Date\":**\n"
    "   - **Explicit Timestamp (✅ Correct):** The publication/update date in TEXT. "
    "Identify it by a **label** (e.g., \"published\", \"modified\", \"updated\", \"asked\", \"edited\", \"answered\") "
    "OR by its **prominent position** (e.g., right under the title).\n"
    "   - **Narrative Date (❌ Incorrect):** A date inside a sentence describing an event "
    "(e.g., `In 2025, the law was passed.`).\n\n"
    "**2. Create the `explicit_dates_list`:**\n"
    "   - Scan the provided **Text** only.\n"
    "   - Find all **Explicit Timestamps** (using either label or position) and add them to the `explicit_dates_list`.\n"
    "   - This list **MUST** contain all timestamps for the main article, the question, "
    "**every answer, and every comment**. Collect them all.\n"
    "   - **DO NOT** include any **Narrative Dates**.\n\n"
    "**3. Determine the Final Timestamp:**\n"
    "   - **If `explicit_dates_list` is not empty,** use the best date from it. Set `source` to `text`.\n"
    "   - **If `explicit_dates_list` is empty,** search for a date in the `metadata`, then the `URL`. "
    "Use narrative text dates only as a last resort. Set the `source` accordingly.\n"
    "   - Assign `confidence_level` exactly according to the Confidence Rubric.\n\n"
    
    "Finally, use the 'get_timestamp' function to output:\n"
    "- 'timestamp': the estimated timestamp ('YYYY-MM-DD' or partial like 'YYYY-MM' or 'YYYY')\n"
    "- 'confidence_level': 'high', 'low', or 'none'\n"
    "- 'source': 'URL', 'text', 'metadata', or 'none'\n"
    "- 'labeled_dates_list': list of labeled dates "
)

def estimate_timestamp_with_llm(url: str, metadata: str, text: str, llm_model: str) -> tuple[str, str]:
    """
    Estimates the last modified time of a webpage using an LLM by analyzing the URL,
    text, and metadata.

    Args:
        url (str): The URL of the webpage.
        metadata (str): The metadata (e.g., HTML <head> content) of the webpage.
        text (str): The main text content of the webpage.
        llm_model (str): The name of the LLM model to use (e.g., "gpt-4o-mini").

    Returns:
        tuple[str, str]: A tuple containing:
            - The estimated timestamp in 'YYYY-MM-DD' (or 'YYYY-MM', 'YYYY') format,
              or an empty string if no reliable timestamp is found.
            - The confidence level ('high', 'low', 'conflicted', or 'none').
    """
    client = OpenAI()

    for attempt in range(2):
        try:
            ans = client.chat.completions.create(
                model=llm_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_CONTENT},
                    {"role": "user", "content": _USER_TEMPLATE.format(
                        url=url,
                        text=text,
                        metadata=metadata
                    )}
                ],
                tools = _TIMESTAMP_TOOL
            )
            arguments = ans.choices[0].message.tool_calls[0].function.arguments
            parsed_arguments = json.loads(arguments)

            # If the labeled_dates_list contains more than one unique, cleaned date, override the original confidence to 'conflicted'
            processed_dates = {
                re.sub(r'[^0-9-]', '', date.strip()) 
                for date in parsed_arguments.get("labeled_dates_list", [])
            }
            confidence = 'conflicted' if len(processed_dates) > 1 else parsed_arguments.get("confidence_level")

            return parsed_arguments["timestamp"], confidence
        except Exception as e:
            if attempt == 0:  # first failure → retry
                continue
            print(f"An error occurred in get_llm_time for URL '{url}': {e}")
            return "", ""