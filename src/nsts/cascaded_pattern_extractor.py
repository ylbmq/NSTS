import re
from datetime import datetime

def _generate_year_regex_inner(max_year):
    """
    Generates the inner regex pattern for years, supporting 19xx and 20xx up to max_year.
    """
    year_parts = [r'19[0-9]{2}'] 
    
    dynamic_20xx_sub_parts = []
    
    # For 2000-2009 (e.g., 200[0-9])
    if max_year >= 2009:
        dynamic_20xx_sub_parts.append('0[0-9]')
    elif max_year >= 2000: # If max_year is e.g. 2005
        dynamic_20xx_sub_parts.append(f'0[0-{max_year % 10}]')
    
    # For 2010-2019 (e.g., 201[0-9])
    if max_year >= 2019:
        dynamic_20xx_sub_parts.append('1[0-9]')
    elif max_year >= 2010: # If max_year is e.g. 2015
        dynamic_20xx_sub_parts.append(f'1[0-{max_year % 10}]')

    # For the current decade (2020s and beyond), up to max_year
    if max_year >= 2020:
        current_decade_tens_digit = str((max_year % 100) // 10) # e.g., '2' for 2025
        last_digit_of_max_year = max_year % 10
        dynamic_20xx_sub_parts.append(rf'{current_decade_tens_digit}[0-{last_digit_of_max_year}]')
    
    # Combine the 20xx parts into a single group if any exist
    if dynamic_20xx_sub_parts:
        year_parts.append(r'20(?:' + '|'.join(dynamic_20xx_sub_parts) + r')')

    return '|'.join(year_parts) # Return without outer (?:...)

def _generate_two_digit_year_regex_inner(max_year):
    """
    Generates the inner regex pattern for two-digit years, supporting 00-current_two_digit_year.
    """
    two_digit_year_parts = []
    # For 2000-2009 (e.g., 0[0-9])
    if max_year >= 2009:
        two_digit_year_parts.append('0[0-9]')
    elif max_year >= 2000:
        two_digit_year_parts.append(f'0[0-{max_year % 10}]')

    # For 2010-2019 (e.g., 1[0-9])
    if max_year >= 2019:
        two_digit_year_parts.append('1[0-9]')
    elif max_year >= 2010:
        two_digit_year_parts.append(f'1[0-{max_year % 10}]')

    # For the current decade (2020s and beyond), up to max_year
    if max_year >= 2020:
        current_decade_tens_digit = str((max_year % 100) // 10) # e.g., '2' for 2025
        last_digit_of_max_year = max_year % 10
        if current_decade_tens_digit == '0':
            # This case ideally won't be reached if handling 2000s separately, but for completeness
            two_digit_year_parts.append(rf'0[0-{last_digit_of_max_year}]')
        else:
            two_digit_year_parts.append(rf'{current_decade_tens_digit}[0-{last_digit_of_max_year}]')

    return '|'.join(two_digit_year_parts)

# Now, use current_year as the max year for the dynamic generation
# This will be '19[0-9]{2}|20(?:0[0-9]|1[0-9]|2[0-5])' when current_year is 2025
current_year = datetime.now().year
_DYNAMIC_YEAR_CONTENT = _generate_year_regex_inner(current_year)
_TWO_DIGIT_DYNAMIC_YEAR_CONTENT = _generate_two_digit_year_regex_inner(current_year)

_DATE_EXPRESSION_TEMPLATE  = r'\D((?:{dynamic_year_content})(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|1[0-2])(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|[12][0-9]|3[01])|' \
                            r'(?:{dynamic_year_content})(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|[12][0-9]|3[01])(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|1[0-2])|' \
                            r'(?:0?[1-9]|[12][0-9]|3[01])(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|1[0-2])(?:[^a-zA-Z0-9]{{0,2}})(?:{dynamic_year_content})|' \
                            r'(?:0?[1-9]|1[0-2])(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|[12][0-9]|3[01])(?:[^a-zA-Z0-9]{{0,2}})(?:{dynamic_year_content})|' \
                            r'(?:{dynamic_year_content})(?:[^a-zA-Z0-9]{{0,2}})' \
                            r'(?:Jan(?:uary)?\.?|Feb(?:ruary)?\.?|Mar(?:ch)?\.?|Apr(?:il)?\.?|May\.?|Jun(?:e)?\.?|Jul(?:y)?\.?|Aug(?:ust)?\.?|Sep(?:tember)?\.?|Oct(?:ober)?\.?|Nov(?:ember)?\.?|Dec(?:ember)?\.?)' \
                            r'(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|[12][0-9]|3[01])|' \
                            r'(?:{dynamic_year_content})(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|[12][0-9]|3[01])' \
                            r'(?:[^a-zA-Z0-9]{{0,2}})(?:Jan(?:uary)?\.?|Feb(?:ruary)?\.?|Mar(?:ch)?\.?|Apr(?:il)?\.?|May\.?|Jun(?:e)?\.?|Jul(?:y)?\.?|Aug(?:ust)?\.?|Sep(?:tember)?\.?|Oct(?:ober)?\.?|Nov(?:ember)?\.?|Dec(?:ember)?\.?)|' \
                            r'(?:Jan(?:uary)?\.?|Feb(?:ruary)?\.?|Mar(?:ch)?\.?|Apr(?:il)?\.?|May\.?|Jun(?:e)?\.?|Jul(?:y)?\.?|Aug(?:ust)?\.?|Sep(?:tember)?\.?|Oct(?:ober)?\.?|Nov(?:ember)?\.?|Dec(?:ember)?\.?)' \
                            r'(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|[12][0-9]|3[01])(?:[^a-zA-Z0-9]{{0,2}})(?:{dynamic_year_content})|' \
                            r'(?:0?[1-9]|[12][0-9]|3[01])(?:[^a-zA-Z0-9]{{0,2}})' \
                            r'(?:Jan(?:uary)?\.?|Feb(?:ruary)?\.?|Mar(?:ch)?\.?|Apr(?:il)?\.?|May\.?|Jun(?:e)?\.?|Jul(?:y)?\.?|Aug(?:ust)?\.?|Sep(?:tember)?\.?|Oct(?:ober)?\.?|Nov(?:ember)?\.?|Dec(?:ember)?\.?)' \
                            r'(?:[^a-zA-Z0-9]{{0,2}})(?:{dynamic_year_content}))(?:\D|$)'
_DATE_PATTERN = re.compile(_DATE_EXPRESSION_TEMPLATE.format(dynamic_year_content=_DYNAMIC_YEAR_CONTENT))

_DATE_EXPRESSION_2  = r'((?:' + _TWO_DIGIT_DYNAMIC_YEAR_CONTENT + r')(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01]))'
_DATE_PATTERN_2 = re.compile(_DATE_EXPRESSION_2)

_MONTH_EXPRESSION_TEMPLATE  = r'\D((?:{dynamic_year_content})(?:[^a-zA-Z0-9]{{0,2}})(?:0?[1-9]|1[0-2])|' \
                            r'(?:0?[1-9]|1[0-2])(?:[^a-zA-Z0-9]{{0,2}})(?:{dynamic_year_content})|' \
                            r'(?:{dynamic_year_content})(?:[^a-zA-Z0-9]{{0,2}})' \
                            r'(?:Jan(?:uary)?\.?|Feb(?:ruary)?\.?|Mar(?:ch)?\.?|Apr(?:il)?\.?|May\.?|Jun(?:e)?\.?|Jul(?:y)?\.?|Aug(?:ust)?\.?|Sep(?:tember)?\.?|Oct(?:ober)?\.?|Nov(?:ember)?\.?|Dec(?:ember)?\.?)|' \
                            r'(?:Jan(?:uary)?\.?|Feb(?:ruary)?\.?|Mar(?:ch)?\.?|Apr(?:il)?\.?|May\.?|Jun(?:e)?\.?|Jul(?:y)?\.?|Aug(?:ust)?\.?|Sep(?:tember)?\.?|Oct(?:ober)?\.?|Nov(?:ember)?\.?|Dec(?:ember)?\.?)' \
                            r'(?:[^a-zA-Z0-9]{{0,2}})(?:{dynamic_year_content}))(?:\D|$)'
_MONTH_PATTERN = re.compile(_MONTH_EXPRESSION_TEMPLATE.format(dynamic_year_content=_DYNAMIC_YEAR_CONTENT))

_YEAR_EXPRESSION_TEMPLATE  = r'\D((?:{dynamic_year_content}))(?:\D|$)'
_YEAR_PATTERN = re.compile(_YEAR_EXPRESSION_TEMPLATE.format(dynamic_year_content=_DYNAMIC_YEAR_CONTENT))

_SEPARATORS  = [" ", ",", "/", ".", "_", "|", "\\", "-", "~", ", "]
_DATE_FORMATS  = [
    "%y%m%d",
    "%Y%m%d", "%Y%b%d", "%Y%b.%d", "%Y%B%d",
    "%Y%d%m", "%Y%d%b", "%Y%d%b.", "%Y%d%B",
    "%m%d%Y", "%b%d%Y", "%b.%d%Y", "%B%d%Y",
    "%d%m%Y", "%d%b%Y", "%d%b.%Y", "%d%B%Y"
]
for sep1 in _SEPARATORS:
    for sep2 in _SEPARATORS:
        _DATE_FORMATS.extend([
            f"%Y{sep1}%m{sep2}%d", f"%Y{sep1}%b{sep2}%d", f"%Y{sep1}%b.{sep2}%d", f"%Y{sep1}%B{sep2}%d",
            f"%Y{sep1}%d{sep2}%m", f"%Y{sep1}%d{sep2}%b", f"%Y{sep1}%d{sep2}%b.", f"%Y{sep1}%d{sep2}%B",
            f"%m{sep1}%d{sep2}%Y", f"%b{sep1}%d{sep2}%Y", f"%b.{sep1}%d{sep2}%Y", f"%B{sep1}%d{sep2}%Y",
            f"%d{sep1}%m{sep2}%Y", f"%d{sep1}%b{sep2}%Y", f"%d{sep1}%b.{sep2}%Y", f"%d{sep1}%B{sep2}%Y"
        ])

_MONTH_FORMATS  = [
    "%Y%m", "%Y%b", "%Y%b.", "%Y%B",
    "%m%Y", "%b%Y", "%b.%Y", "%B%Y"
]
for sep in _SEPARATORS:
    _MONTH_FORMATS.extend([
        f"%Y{sep}%m", f"%Y{sep}%b", f"%Y{sep}%b.", f"%Y{sep}%B",
        f"%m{sep}%Y", f"%b{sep}%Y", f"%b.{sep}%Y", f"%B{sep}%Y"
    ])

_YEAR_FORMATS  = ["%Y"]

def _find_match(pattern, text):
    """
    Finds all non-overlapping matches of a regex pattern in text, returning the captured group.
    """
    matches = []
    for i in range(len(text)):
        match = re.match(pattern, text[i:])
        if match:
            matches.append(match.group(1))
    
    return matches

def _sort_times(time_strs, formats):
    """
    Parses a list of time strings using given formats, filters by year (<= current year + 1),
    and returns the latest valid datetime object and the original matching strings.
    """
    times = []
    match_strs = []
    for time_str in time_strs:
        for format in formats:
            try:
                time = datetime.strptime(time_str, format)
                if time.year < 2026:
                    times.append(time)
                    match_strs.append(time_str)
                    break
            except ValueError:
                continue

    # Sort the valid dates
    sorted_times = sorted(times, reverse=True)
    if sorted_times:
        largest_time = sorted_times[0]
    else:
        largest_time = None

    return largest_time, match_strs

def _get_largest_date(string, information_type):
    """
    Extracts the largest (most recent) date from a string based on patterns,
    considering full dates, then month-year, then year.
    Returns the date in 'YYYY-MM-DD', 'YYYY-MM', or 'YYYY' format, or None.
    """
    #date-month-year
    if information_type == "metadata" or information_type == "url":
        date_strs = _find_match(_DATE_PATTERN, string) + _find_match(_DATE_PATTERN_2, string)
    elif information_type == "text":
        date_strs = _DATE_PATTERN.findall(string)
    largest_date, match_strs = _sort_times(date_strs, _DATE_FORMATS)
    for match_str in match_strs:
        string = re.sub(re.escape(match_str), '****', string)

    #month-year
    if information_type == "metadata" or information_type == "url":
        month_strs = _find_match(_MONTH_PATTERN, string)
    elif information_type == "text":
        month_strs = _MONTH_PATTERN.findall(string)
    largest_month, match_strs = _sort_times(month_strs, _MONTH_FORMATS)
    for match_str in match_strs:
        string = re.sub(re.escape(match_str), '****', string)

    #year
    year_strs = _YEAR_PATTERN.findall(string)
    largest_year, match_strs = _sort_times(year_strs, _YEAR_FORMATS)

    all_time = [dt for dt in [largest_date, largest_month, largest_year] if dt is not None]
    if all_time:
        largest_time = max(all_time)
        
        # Check which list the largest date is from
        if largest_time == largest_date:
            return largest_time.strftime("%Y-%m-%d")
        elif largest_time == largest_month:
            return largest_time.strftime("%Y-%m")
        elif largest_time == largest_year:
            return largest_time.strftime("%Y")
    else:
        return None

def estimate_timestamp_with_regex(url, metadata, text):
    """
    Extracts the most recent timestamp from a URL, its metadata, and its text content
    using regular expressions.

    Args:
        url (str): The URL of the webpage.
        metadata (str): The metadata of the webpage (e.g., <head> section HTML).
        text (str): The main text content of the webpage.

    Returns:
        str: The latest extracted timestamp in 'YYYY-MM-DD', 'YYYY-MM', or 'YYYY' format,
             or an empty string if no timestamp is found.
    """
    url_largest_date = _get_largest_date(url, "url")
    metadata_largest_date = _get_largest_date(metadata, "metadata")
    text_largest_date = _get_largest_date(text, "text")

    all_date = [dt for dt in [url_largest_date, metadata_largest_date, text_largest_date] if dt is not None]
    if all_date:
        largest_date = max(all_date)
        return largest_date
    else:
        return ""