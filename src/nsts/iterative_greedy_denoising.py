from collections import defaultdict
from tqdm import tqdm

def remove_frequent_text_blocks(
    data: list[dict], 
    min_len: int, 
    min_repeatance_ratio: float,
    min_docs: int
) -> list[dict]:
    """
    Identifies and removes frequent, repeated text patterns from a list of documents.
    
    This function is now a pure function; it takes data as a list of dicts
    and returns the cleaned data, without handling any file I/O.
    
    Args:
        data (list[dict]): A list of dictionaries, where each item has a 'text' key.
        min_len (int): Minimum length of a pattern to be considered for removal.
        min_repeatance_ratio (float): Minimum ratio of documents a pattern must appear in
                                      to be considered frequent. This is converted to an
                                      absolute count, with a floor of min_docs.
        min_docs (int): Positive minimum document count for removal, supplied by the caller.

    Returns:
        list[dict]: The list of documents with frequent patterns removed.
    """
    if not data:
        return []
    
    min_repeatance = len(data) * min_repeatance_ratio
    min_repeatance = max(min_docs, int(min_repeatance))

    # Pre-calculate character spans for lines in each document to avoid re-calculating
    doc_line_char_spans = [] 
    doc_num_lines = [] 

    for item in tqdm(data, desc="Pre-calculating line spans"):
        raw_lines = item["text"].split("\n")
        
        line_spans = []
        current_char_idx = 0
        for raw_line in raw_lines:
            line_len_including_whitespace = len(raw_line)
            line_spans.append((current_char_idx, current_char_idx + line_len_including_whitespace))
            current_char_idx += line_len_including_whitespace + 1 # +1 for the actual newline character
        
        filtered_line_spans = []
        for i, (start_idx, end_idx) in enumerate(line_spans):
            line_content_from_raw = item["text"][start_idx:end_idx]
            if line_content_from_raw.strip(): 
                filtered_line_spans.append((start_idx, end_idx))
        
        doc_line_char_spans.append(filtered_line_spans)
        doc_num_lines.append(len(filtered_line_spans)) 

    # Step 1: Count initial chunks
    hash_to_line_locations = defaultdict(list)
    
    for doc_idx, item in enumerate(tqdm(data, desc="Indexing initial chunks")):
        current_doc_spans = doc_line_char_spans[doc_idx]
        num_valid_lines = doc_num_lines[doc_idx]
        seen_hashes_in_doc = set() 

        for i in range(num_valid_lines):
            for j in range(i, num_valid_lines):
                start_char = current_doc_spans[i][0]
                end_char = current_doc_spans[j][1] 
                
                chunk_text_for_hash = item["text"][start_char : end_char + 1]

                if len(chunk_text_for_hash) >= min_len:
                    h = hash(chunk_text_for_hash)
                    if h not in seen_hashes_in_doc:
                        hash_to_line_locations[h].append((doc_idx, i, j))
                        seen_hashes_in_doc.add(h)
                    break 
    
    frequent_initial_hashes = {h for h, locs in hash_to_line_locations.items() if len(locs) >= min_repeatance}

    # Step 2: Iteratively grow frequent substrings (identifying ALL frequent patterns)
    current_candidates = defaultdict(list)
    
    for h in tqdm(frequent_initial_hashes, desc="Initializing candidates"):
        for loc in hash_to_line_locations[h]:
            current_candidates[h].append(loc)

    all_frequent_substrings_by_hash = defaultdict(list) 

    # Initialize all_frequent_substrings_by_hash with all initial frequent candidates
    for h, locations in current_candidates.items():
        if len(locations) >= min_repeatance:
            first_doc_idx, first_start_line, first_end_line = locations[0]
            start_char = doc_line_char_spans[first_doc_idx][first_start_line][0]
            end_char = doc_line_char_spans[first_doc_idx][first_end_line][1]
            length = (end_char - start_char + 1)
            if length >= min_len:
                for loc in locations:
                    all_frequent_substrings_by_hash[h].append(loc)

    pbar = tqdm(total=len(current_candidates), desc="Growing substrings by line")
    
    while current_candidates:
        next_candidates = defaultdict(list)
        processed_hashes_in_iteration = set()

        current_hashes_to_process = list(current_candidates.keys())

        for sub_hash in current_hashes_to_process:
            if sub_hash not in current_candidates or sub_hash in processed_hashes_in_iteration:
                continue 
            
            locations = current_candidates[sub_hash]
            pbar.update(1)

            first_doc_idx, first_start_line, first_end_line = locations[0]
            char_start_of_current_substring = doc_line_char_spans[first_doc_idx][first_start_line][0]
            char_end_of_current_substring = doc_line_char_spans[first_doc_idx][first_end_line][1]
            current_substring_raw_text_sample = data[first_doc_idx]["text"][char_start_of_current_substring : char_end_of_current_substring + 1]
            
            possible_next_line_info = defaultdict(list) 
            
            for doc_idx, start_line, end_line in locations:
                num_valid_lines_in_doc = doc_num_lines[doc_idx]
                if end_line + 1 < num_valid_lines_in_doc: 
                    next_line_char_start = doc_line_char_spans[doc_idx][end_line + 1][0]
                    next_line_char_end = doc_line_char_spans[doc_idx][end_line + 1][1]
                    raw_next_line_text = data[doc_idx]["text"][next_line_char_start : next_line_char_end + 1]
                    
                    next_line_hash = hash(raw_next_line_text)
                    possible_next_line_info[next_line_hash].append((doc_idx, start_line, end_line + 1)) 

            for next_line_hash, new_locations in possible_next_line_info.items():
                if len(new_locations) >= min_repeatance:
                    sample_doc_idx, _, sample_new_end_line = new_locations[0]
                    sample_next_line_char_start = doc_line_char_spans[sample_doc_idx][sample_new_end_line][0]
                    sample_next_line_char_end = doc_line_char_spans[sample_doc_idx][sample_new_end_line][1]
                    raw_sample_next_line_text = data[sample_doc_idx]["text"][sample_next_line_char_start : sample_next_line_char_end + 1]
                    
                    new_substring_raw_text_for_hash = current_substring_raw_text_sample + raw_sample_next_line_text
                    new_hash = hash(new_substring_raw_text_for_hash)
                    
                    new_length = len(new_substring_raw_text_for_hash)
                    if new_length >= min_len:
                        for loc in new_locations:
                            all_frequent_substrings_by_hash[new_hash].append(loc)

                    for loc in new_locations: 
                        next_candidates[new_hash].append(loc)
            
            processed_hashes_in_iteration.add(sub_hash) 
            
        current_candidates = next_candidates
    pbar.close()

    # Step 3: Select substrings to remove based on "independent" repeatance
    final_unique_substrings_to_remove = [] 
    
    # This will store the character spans of patterns that HAVE been selected for removal.
    # It will be used to determine if a shorter pattern's occurrences are "covered".
    # {doc_idx: [(start_char, end_char), ...]}
    selected_removal_spans_per_doc = defaultdict(list) 

    # First, collect all potential candidates, and sort them to prioritize longer ones.
    # We'll use the actual text as key for easier deduplication and lookup in the next step.
    potential_removal_candidates_by_text = {} # {text: list_of_char_locations}
    for sub_hash, line_locations in all_frequent_substrings_by_hash.items():
        if len(line_locations) < min_repeatance: 
            continue

        first_doc_idx, first_start_line, first_end_line = line_locations[0]
        start_char = doc_line_char_spans[first_doc_idx][first_start_line][0]
        end_char = doc_line_char_spans[first_doc_idx][first_end_line][1]
        
        substr_text_sample = data[first_doc_idx]["text"][start_char : end_char + 1]
        
        if len(substr_text_sample) >= min_len:
            # Consolidate all char locations for this unique text string
            current_text_char_locations = []
            for doc_idx_loc, start_line_loc, end_line_loc in line_locations:
                start_char_loc = doc_line_char_spans[doc_idx_loc][start_line_loc][0]
                end_char_loc = doc_line_char_spans[doc_idx_loc][end_line_loc][1]
                current_text_char_locations.append((doc_idx_loc, start_char_loc, end_char_loc))
            
            # Store or update with the full list of locations
            if substr_text_sample in potential_removal_candidates_by_text:
                # Merge locations if this hash was encountered via different growth paths
                potential_removal_candidates_by_text[substr_text_sample].extend(current_text_char_locations)
                # Deduplicate locations for the same text
                potential_removal_candidates_by_text[substr_text_sample] = list(set(potential_removal_candidates_by_text[substr_text_sample]))
            else:
                potential_removal_candidates_by_text[substr_text_sample] = current_text_char_locations
    
    # Convert to a list of (text, locations) tuples for sorting
    sorted_candidates = [(text, locs) for text, locs in potential_removal_candidates_by_text.items()]
    
    # Sort by length descending, then by occurrence count descending, then alphabetically for ties
    sorted_candidates.sort(key=lambda x: (-len(x[0]), -len(x[1]), x[0]))

    # Now, iterate through sorted candidates and apply the "independent" repeatance check
    print("\nEvaluating Substrings for Removal based on Independent Occurrences:")
    print("---------------------------------")

    for substr_text_sample, char_locations_total in tqdm(sorted_candidates, desc="Filtering substrings"):
        independent_occurrences = 0
        current_independent_locations = []

        for doc_idx, start_char, end_char in char_locations_total:
            is_covered = False
            # Check if this specific occurrence is covered by an already selected, longer pattern
            # Note: selected_removal_spans_per_doc are sorted by start_char for binary search efficiency
            
            # This check can be optimized with interval trees or a more sophisticated data structure
            # For simplicity, a linear scan for each span:
            for removed_start, removed_end in selected_removal_spans_per_doc[doc_idx]:
                # If the current substring is completely within a removed span
                if start_char >= removed_start and end_char <= removed_end:
                    is_covered = True
                    break
            
            if not is_covered:
                independent_occurrences += 1
                current_independent_locations.append((doc_idx, start_char, end_char))

        if independent_occurrences >= min_repeatance:
            # Add to the final list
            final_unique_substrings_to_remove.append((substr_text_sample, current_independent_locations))
            
            # Mark these occurrences as "covered" for subsequent, shorter patterns
            for doc_idx, start_char, end_char in current_independent_locations:
                selected_removal_spans_per_doc[doc_idx].append((start_char, end_char))
                # Keep the spans for each doc sorted to optimize future `is_covered` checks
                selected_removal_spans_per_doc[doc_idx].sort() # Re-sort after adding

    print("---------------------------------")
    print(f"Total {len(final_unique_substrings_to_remove)} unique repeated substrings will be removed.")

    # Step 4: Delete repeated substrings from texts efficiently
    cleaned_data = []
    
    # Re-build doc_substrings_to_remove_char_spans using the filtered list
    doc_substrings_to_remove_char_spans = defaultdict(list)
    for substr_text, char_locations in final_unique_substrings_to_remove: 
        for doc_idx, start_char, end_char in char_locations:
            # Note: We now use the 'current_independent_locations' from Step 3,
            # which are the *uncovered* instances that met min_repeatance.
            doc_substrings_to_remove_char_spans[doc_idx].append((start_char, end_char + 1, substr_text))

    for doc_idx, item in enumerate(tqdm(data, desc="Cleaning documents")):
        original_text = item["text"]
        substrings_for_this_doc = doc_substrings_to_remove_char_spans[doc_idx]
        
        if not substrings_for_this_doc:
            # Create a new dictionary with only the desired keys
            new_item = {
                "url": item.get("url", ""), # Use .get() for safety
                "text": original_text.strip()
            }
            if "html" in item:
                new_item["html"] = item["html"]
            cleaned_data.append(new_item)
            continue

        substrings_for_this_doc.sort() 

        cleaned_parts = []
        current_pos = 0

        for start_remove, end_remove, _ in substrings_for_this_doc:
            if start_remove >= current_pos:
                cleaned_parts.append(original_text[current_pos:start_remove])
            current_pos = max(current_pos, end_remove) 
        
        cleaned_parts.append(original_text[current_pos:])
        
        new_item = {
            "url": item.get("url", ""), # Use .get() for safety in case 'url' is missing
            "text": "".join(cleaned_parts).strip()
        }
        if "html" in item:
                new_item["html"] = item["html"]
        cleaned_data.append(new_item)

    return cleaned_data