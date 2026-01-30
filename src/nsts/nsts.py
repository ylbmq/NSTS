from typing import Optional, Dict, Any

from .cascaded_pattern_extractor import estimate_timestamp_with_regex
from .prioritized_semantic_reasoner import estimate_timestamp_with_llm
from .iterative_greedy_denoising import remove_frequent_text_blocks
from .metadata_extractor import extract_metadata
from .web_scraper import fetch_website

class NSTS:
    """
    A class to determine validity timestamps from web pages using a combination
    of regex-based extraction, LLM-based analysis, and content cleaning.
    """
    def __init__(
            self,
            extraction_method: str = "nsts",
            llm_model: str = "gpt-4o-mini",
            min_len: int = 30,
            min_repeatance_ratio: float = 0.01,
            min_docs: int = 30
        ):
        """
        Initializes the NSTS instance.

        Args:
            extraction_method (str): The method for extraction. Can be 'nsts', 
                                    'psr', or 'cpe'. Defaults to 'nsts'.
            llm_model (str): The name of the LLM model to use for timestamp extraction.
                             Defaults to "gpt-4o-mini".
            min_len (int): Minimum length of a text pattern to be considered for removal
                           by the frequent pattern remover. Defaults to 30.
            min_repeatance_ratio (float): Minimum ratio of documents a pattern must appear in
                                          to be considered frequent for removal. Defaults to 0.01.
            min_docs (int): Minimum number of documents containing a pattern before
                            it can be removed. Must be a positive integer. Defaults to 30.
        """
        allowed_methods = {"nsts", "psr", "cpe"}
        if extraction_method not in allowed_methods:
            raise ValueError(f"extraction_method must be one of {allowed_methods}")
        
        self.extraction_method = extraction_method
        self.llm_model = llm_model
        self.min_len = min_len
        self.min_repeatance_ratio = min_repeatance_ratio
        self.min_docs = min_docs

    def remove_boilerplate(self, data: Any) -> Any:
        """Removes frequent text blocks from the data."""
        cleaned_data = remove_frequent_text_blocks(data, self.min_len, self.min_repeatance_ratio, self.min_docs)
        return cleaned_data

    def get_timestamps(
        self, 
        url: str, 
        text: Optional[str] = None, 
        html: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate validity timestamps from a URL or provided content.

        Args:
            url: The target URL.
            text: Optional pre-fetched text content.
            html: Optional pre-fetched HTML content.

        Returns:
            A dictionary containing the final timestamp, method-specific timestamps, and confidence state.
        """
        if not text:
            webpage = fetch_website(url)[0]
            text = webpage["text"]

        source = html if html else url
        metadata = extract_metadata(source)

        # Initialize fields
        timestamp, cpe_timestamp, psr_timestamp, system_confidence = "", "", "", ""

        # --- Extraction Logic ---
        if self.extraction_method == "psr":
            psr_timestamp, system_confidence = estimate_timestamp_with_llm(url, metadata, text, self.llm_model)
            timestamp = psr_timestamp
        
        elif self.extraction_method == "cpe":
            cpe_timestamp = estimate_timestamp_with_regex(url, metadata, text)
            timestamp = cpe_timestamp
        
        elif self.extraction_method == "nsts":
            cpe_timestamp = estimate_timestamp_with_regex(url, metadata, text)
            psr_timestamp, system_confidence = estimate_timestamp_with_llm(url, metadata, text, self.llm_model)
            
            if psr_timestamp not in (None, "", "none") and (not cpe_timestamp or system_confidence == "high"):
                timestamp = psr_timestamp
            else:
                timestamp = cpe_timestamp

        result_item = {
            "url": url,
            "timestamp": timestamp,
            "cpe_timestamp": cpe_timestamp,
            "psr_timestamp": psr_timestamp,
            "system_confidence": system_confidence
        }
        
        return result_item