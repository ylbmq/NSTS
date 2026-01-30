# NSTS

NSTS determines the **validity timestamp** of a webpage: the date that best represents its current primary content. It combines a symbolic date extractor (CPE), an OpenAI semantic reasoner (PSR), and confidence-based selection between their candidates.

## Installation

```bash
python -m pip install NSTS
```

Python 3.10 or newer is required. Runtime dependencies install automatically. Import the `NSTS` class from the lowercase `nsts` package.

## Determine a timestamp from a URL

Set `OPENAI_API_KEY` and `APIFY_API_TOKEN` in the environment of your Python process, then run:

```python
from nsts import NSTS

nsts = NSTS()
result = nsts.get_timestamps(url="https://www.example.com/article")
print(result)
```

With only a URL, NSTS fetches the page text through Apify, fetches HTML metadata over HTTP, and uses OpenAI for semantic reasoning. Live service calls use your accounts and may incur their normal charges.

## Use text and HTML you already have

If you already have the URL and page text, pass both to `get_timestamps`:

```python
from nsts import NSTS

url = "https://example.com/article"
text = " Published on 2020-05-17. "

nsts = NSTS()
result = nsts.get_timestamps(url=url, text=text)
print(result)
```

Supplying nonempty text avoids Apify crawling, so `APIFY_API_TOKEN` is not needed. NSTS still fetches HTML metadata from the URL, and the default mode still requires `OPENAI_API_KEY`.

If you also have the HTML, supply it to avoid fetching page content entirely:

```python
from nsts import NSTS

url = "https://example.com/article"
text = " Published on 2020-05-17. "
html = '<html><head><title>Example</title></head><body>Published on 2020-05-17.</body></html>'

nsts = NSTS()
result = nsts.get_timestamps(url=url, text=text, html=html)
print(result)
```

The default mode still calls OpenAI even when text and HTML are supplied. Omitted or empty text triggers Apify fetching; omitted or empty HTML triggers HTTP metadata fetching.

## Choose a mode and LLM model

| `extraction_method` | Behavior | Credentials |
| --- | --- | --- |
| `"nsts"` (default) | Combines symbolic and semantic candidates using confidence. | OpenAI; Apify if fetching text. |
| `"psr"` | Uses semantic reasoning. | OpenAI; Apify if fetching text. |
| `"cpe"` | Uses deterministic date patterns. | Apify only if fetching text. |

Specify the mode and model when constructing NSTS:

```python
from nsts import NSTS

nsts = NSTS(
    extraction_method="nsts",
    llm_model="gpt-4o-mini",
)
```

`gpt-4o-mini` is the default. To use another model, set `llm_model` to a model your OpenAI account supports for Chat Completions with function tools. The model setting applies to `nsts` and `psr`; `cpe` does not use an LLM.

## Read the result

Every determination example above assigns the returned dictionary to `result`. To access the selected timestamp:

```python
print(result["timestamp"])
```

The dictionary also includes the candidates and confidence:

| Field | Meaning |
| --- | --- |
| `url` | Input webpage URL. |
| `timestamp` | Selected validity timestamp, possibly a partial date or empty string. |
| `cpe_timestamp` | Symbolic candidate when CPE ran. |
| `psr_timestamp` | Semantic candidate when PSR ran. |
| `system_confidence` | PSR confidence, including `high`, `low`, `conflicted`, or `none`; may be empty if PSR did not run or failed. |

These are estimates. A date mentioned in content can differ from the page's validity date; semantic modes help distinguish those cases.

## Corpus-Level Use

IGD is a corpus-level denoising step. Use it when processing multiple pages from the same source or domain, then determine a timestamp for each cleaned item. Call `remove_boilerplate` once on the corpus; `get_timestamps` does not automatically perform corpus denoising.

The following example illustrates the workflow with two records. Replace them with your corpus. The default neural mode requires `OPENAI_API_KEY`; supplied nonempty text and HTML avoid page fetching.

```python
from nsts import NSTS

nsts = NSTS(
    min_len=30,
    min_repeatance_ratio=0.01,
    min_docs=30,
)

corpus_data = [
    {"url": "...", "text": "Header... Unique 1... Footer...", "html": "<html>...</html>"},
    {"url": "...", "text": "Header... Unique 2... Footer...", "html": "<html>...</html>"},
]

cleaned_corpus = nsts.remove_boilerplate(corpus_data)

for item in cleaned_corpus:
    result = nsts.get_timestamps(
        url=item["url"],
        text=item["text"],
        html=item["html"],
    )
    print(f"{item['url']}: {result['timestamp']}")
```

The following settings control corpus denoising:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `min_len` | `30` | Minimum text-pattern length in characters considered for removal. Increase it to focus on longer repeated blocks. |
| `min_repeatance_ratio` | `0.01` | Fraction of corpus documents in which a pattern must occur, subject to the `min_docs` minimum. Increase it to require broader repetition in larger corpora. |
| `min_docs` | `30` | Minimum number of documents containing a pattern before removal. Set a smaller positive integer for a smaller corpus. |

The document threshold is `max(min_docs, int(len(corpus_data) * min_repeatance_ratio))`. With the default `min_docs=30`, a pattern must occur in at least 30 documents, so the two-item illustration above does not remove repeated patterns. With 10,000 documents and the default ratio, the threshold is 100 documents. For a smaller corpus, set `min_docs=2` to allow removal of patterns shared by at least two documents. The ratio can still require a higher document count; lowering the ratio alone does not lower `min_docs`. The above example illustrates the workflow; removal also requires a shared pattern that meets `min_len`.

Supply dictionaries with `url` and string `text` fields and, optionally, `html`. The returned list contains cleaned text with the original URL and supplied HTML; additional custom fields are not retained. Keep your original records separately if you need those fields.

## Research and examples

The [repository](https://github.com/ylbmq/NSTS) contains runnable examples, benchmark datasets/results, reproduction instructions, and the paper's [citation](https://github.com/ylbmq/NSTS#citation). Benchmark tools and data are not installed with this library. See [issues](https://github.com/ylbmq/NSTS/issues) for problem reports.

Released under the [MIT license](https://github.com/ylbmq/NSTS/blob/main/LICENSE).
