"""Deadline resolution — converts natural-language deadline phrases to datetimes."""

import calendar
import re
from datetime import datetime, timedelta


def resolve_deadline(text: str, base_date: datetime) -> datetime:
    """Convert a deadline phrase to an absolute datetime.

    Supported patterns:
        - "within N days/weeks/months/years"
        - "by DD Month YYYY" or "by Month DD, YYYY" (Pattern A)
        - "by Month YYYY" or "by QN YYYY" (Pattern B)
        - "by end of [Month/Quarter]" (Pattern C)
        - "by <Month> <Day>" (assumes current/next year)
        - Fallback: 90 days from base_date if unparseable

    Args:
        text: The natural-language deadline phrase.
        base_date: The reference date (usually the circular's ingestion date).

    Returns:
        An absolute datetime representing the resolved deadline.
    """
    text = text.strip().lower()

    # --- Pattern 1: "within N <unit>" ---
    within_match = re.search(
        r"within\s+(\d+)\s+(day|week|month|year)s?", text, re.IGNORECASE
    )
    if within_match:
        amount = int(within_match.group(1))
        unit = within_match.group(2).lower()
        if unit == "day":
            return base_date + timedelta(days=amount)
        elif unit == "week":
            return base_date + timedelta(weeks=amount)
        elif unit == "month":
            return base_date + timedelta(days=amount * 30)
        elif unit == "year":
            return base_date + timedelta(days=amount * 365)

    # --- Month name mapping ---
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "jun": 6, "jul": 7, "aug": 8, "sep": 9,
        "oct": 10, "nov": 11, "dec": 12,
    }
    months_regex_str = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"

    # --- Pattern A1: "by DD Month YYYY" (e.g. "by 31 March 2025") ---
    match_a1 = re.search(
        rf"by\s+(\d{{1,2}})\s+{months_regex_str}\s+(\d{{4}})",
        text,
        re.IGNORECASE
    )
    if match_a1:
        day = int(match_a1.group(1))
        month_str = match_a1.group(2).lower()
        year = int(match_a1.group(3))
        month = month_names.get(month_str)
        if month:
            return datetime(year, month, day, tzinfo=base_date.tzinfo)

    # --- Pattern A2: "by Month DD, YYYY" (e.g. "by March 31, 2025") ---
    match_a2 = re.search(
        rf"by\s+{months_regex_str}\s+(\d{{1,2}}),?\s+(\d{{4}})",
        text,
        re.IGNORECASE
    )
    if match_a2:
        month_str = match_a2.group(1).lower()
        day = int(match_a2.group(2))
        year = int(match_a2.group(3))
        month = month_names.get(month_str)
        if month:
            return datetime(year, month, day, tzinfo=base_date.tzinfo)

    # --- Pattern B1: "by Month YYYY" (e.g. "by March 2025") ---
    match_b1 = re.search(
        rf"by\s+{months_regex_str}\s+(\d{{4}})",
        text,
        re.IGNORECASE
    )
    if match_b1:
        month_str = match_b1.group(1).lower()
        year = int(match_b1.group(2))
        month = month_names.get(month_str)
        if month:
            last_day = calendar.monthrange(year, month)[1]
            return datetime(year, month, last_day, tzinfo=base_date.tzinfo)

    # --- Pattern B2: "by QN YYYY" (e.g. "by Q1 2025") ---
    match_b2 = re.search(r"by\s+q([1-4])\s+(\d{4})", text, re.IGNORECASE)
    if match_b2:
        quarter = int(match_b2.group(1))
        year = int(match_b2.group(2))
        month = quarter * 3
        last_day = calendar.monthrange(year, month)[1]
        return datetime(year, month, last_day, tzinfo=base_date.tzinfo)

    # --- Pattern C1: "by end of [Month]" (e.g. "by end of March") ---
    match_c1 = re.search(
        rf"by\s+end\s+of\s+{months_regex_str}",
        text,
        re.IGNORECASE
    )
    if match_c1:
        month_str = match_c1.group(1).lower()
        year = base_date.year
        month = month_names.get(month_str)
        if month:
            last_day = calendar.monthrange(year, month)[1]
            return datetime(year, month, last_day, tzinfo=base_date.tzinfo)

    # --- Pattern C2: "by end of QN" (e.g. "by end of Q1") ---
    match_c2 = re.search(r"by\s+end\s+of\s+q([1-4])", text, re.IGNORECASE)
    if match_c2:
        quarter = int(match_c2.group(1))
        year = base_date.year
        month = quarter * 3
        last_day = calendar.monthrange(year, month)[1]
        return datetime(year, month, last_day, tzinfo=base_date.tzinfo)

    # --- Pattern D: "by <Month> <Day>" (no year — assume current/next year) ---
    by_md_match = re.search(rf"by\s+{months_regex_str}\s+(\d{{1,2}})", text, re.IGNORECASE)
    if by_md_match:
        month_str = by_md_match.group(1).lower()
        day = int(by_md_match.group(2))
        month = month_names.get(month_str)
        if month:
            candidate = datetime(
                base_date.year, month, day, tzinfo=base_date.tzinfo
            )
            if candidate < base_date:
                candidate = datetime(
                    base_date.year + 1, month, day, tzinfo=base_date.tzinfo
                )
            return candidate

    # --- Fallback: 90 days from base_date ---
    return base_date + timedelta(days=90)


if __name__ == "__main__":
    test_base = datetime(2025, 1, 1)
    
    cases = [
        "within 30 days",
        "by March 31, 2025",
        "by March 2025",
        "by end of Q1",
        "gibberish",
    ]
    
    print("Testing date resolver:")
    for c in cases:
        res = resolve_deadline(c, test_base)
        print(f"'{c}' -> {res.strftime('%Y-%m-%d')}")
