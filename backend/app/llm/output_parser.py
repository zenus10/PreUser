import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output with automatic repair.

    Handles common LLM output issues:
    - JSON wrapped in markdown code blocks
    - Trailing commas
    - Single quotes instead of double quotes
    - Truncated JSON output (attempts to close open brackets/braces)
    """
    # Step 1: Extract JSON from markdown code blocks
    cleaned = _extract_json_block(text)

    # Step 2: Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Step 3: Try auto-repair
    repaired = _auto_repair(cleaned)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Step 4: Try truncation repair (LLM output may have been cut off)
    truncation_repaired = _repair_truncated_json(repaired)
    try:
        result = json.loads(truncation_repaired)
        logger.warning("JSON was truncated, recovered partial data")
        return result
    except json.JSONDecodeError:
        pass

    # Step 5: Last resort — try to find any valid JSON object in the text
    # Some LLMs wrap JSON with explanatory text before/after
    for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL):
        try:
            result = json.loads(match.group())
            logger.warning("Extracted JSON object from mixed text output")
            return result
        except json.JSONDecodeError:
            continue

    # All attempts failed — log sufficient context for debugging
    # Show area around the likely error position
    logger.error(
        f"JSON parse failed after all repairs.\n"
        f"Original text (first 1000 chars): {text[:1000]}\n"
        f"Repaired text (first 1000 chars): {repaired[:1000]}"
    )
    raise ValueError(f"Failed to parse LLM output as JSON. Text starts with: {text[:200]}")


def validate_schema(data: dict, required_fields: list[str]) -> list[str]:
    """Validate that required fields exist in the data.

    Returns list of missing field names (empty if valid).
    """
    missing = [f for f in required_fields if f not in data]
    return missing


def validate_block_ids(blocks: list[dict]) -> list[str]:
    """Validate block_id uniqueness and dependency references.

    Returns list of error messages (empty if valid).
    """
    errors = []
    ids = set()

    for block in blocks:
        bid = block.get("block_id", "")
        if bid in ids:
            errors.append(f"Duplicate block_id: {bid}")
        ids.add(bid)

    for block in blocks:
        for dep in block.get("dependencies", []):
            if dep not in ids:
                errors.append(f"Invalid dependency reference: {dep} in block {block.get('block_id')}")

    return errors


def validate_source_ranges(blocks: list[dict]) -> list[str]:
    """Check that source_range values don't overlap."""
    errors = []
    ranges = []

    for block in blocks:
        sr = block.get("source_range", [])
        if len(sr) == 2:
            ranges.append((sr[0], sr[1], block.get("block_id", "")))

    ranges.sort(key=lambda x: x[0])
    for i in range(len(ranges) - 1):
        if ranges[i][1] > ranges[i + 1][0]:
            errors.append(
                f"Overlapping source_range: {ranges[i][2]}[{ranges[i][0]}-{ranges[i][1]}] "
                f"and {ranges[i+1][2]}[{ranges[i+1][0]}-{ranges[i+1][1]}]"
            )

    return errors


def _extract_json_block(text: str) -> str:
    """Extract JSON from markdown code blocks like ```json ... ```."""
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find raw JSON object or array
    text = text.strip()
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

    return text


def _auto_repair(text: str) -> str:
    """Attempt to fix common JSON issues from LLM output."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Remove comments (single-line // style)
    text = re.sub(r"//.*?\n", "\n", text)
    # Replace literal ... or …… placeholders in values with empty string
    text = re.sub(r':\s*\.\.\.', ': ""', text)
    text = re.sub(r':\s*……', ': ""', text)
    # Fix Python-style None -> null
    text = re.sub(r'\bNone\b', 'null', text)
    # Fix Python-style True/False -> true/false
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    # Fix NaN / Infinity (not valid JSON)
    text = re.sub(r'\bNaN\b', 'null', text)
    text = re.sub(r'\bInfinity\b', '1e308', text)
    text = re.sub(r'-Infinity\b', '-1e308', text)
    # Fix single-quoted strings: 'value' -> "value"  (simple cases only)
    # Only outside of already-double-quoted strings — replace 'key': 'val' patterns
    text = re.sub(r"(?<![\"\\])'([^'\\]*)'", r'"\1"', text)
    # Fix missing value after colon (e.g., "key": , or "key": })
    text = re.sub(r':\s*,', ': "",', text)
    text = re.sub(r':\s*}', ': ""}', text)
    text = re.sub(r':\s*]', ': ""]', text)
    return text


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair truncated JSON by closing open brackets/braces.

    When LLM output is cut off mid-JSON, this tries to recover
    by truncating at the last complete element and closing all open structures.
    """
    text = text.rstrip()

    # Strategy: find each position that ends a complete JSON value
    # (closing quote, closing bracket/brace, digit, true/false/null end)
    # and try closing from there, working backwards.

    # Collect candidate truncation points: positions right after a complete value
    # We scan backwards for efficiency.
    search_start = max(0, len(text) - 2000)

    for end in range(len(text), search_start, -1):
        candidate = text[:end]

        # Track string state properly (handle escaped quotes)
        in_string = False
        i = 0
        while i < len(candidate):
            ch = candidate[i]
            if in_string:
                if ch == '\\':
                    i += 2  # skip escaped character
                    continue
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
            i += 1

        # If we're inside a string, truncate back to before the opening quote
        if in_string:
            # Find the last unmatched opening quote and cut before it
            last_quote = candidate.rfind('"')
            if last_quote > 0:
                candidate = candidate[:last_quote]
            else:
                continue

        # Clean up trailing incomplete elements
        candidate = candidate.rstrip()
        candidate = re.sub(r',\s*"[^"]*":\s*$', '', candidate)
        candidate = re.sub(r',\s*$', '', candidate)

        # Count open/close brackets (outside strings)
        open_braces = 0
        open_brackets = 0
        in_str = False
        j = 0
        while j < len(candidate):
            ch = candidate[j]
            if in_str:
                if ch == '\\':
                    j += 2
                    continue
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    open_braces += 1
                elif ch == '}':
                    open_braces -= 1
                elif ch == '[':
                    open_brackets += 1
                elif ch == ']':
                    open_brackets -= 1
            j += 1

        if open_braces < 0 or open_brackets < 0:
            continue

        # Close open structures
        closing = ']' * open_brackets + '}' * open_braces
        attempt = candidate + closing

        try:
            json.loads(attempt)
            return attempt
        except json.JSONDecodeError:
            continue

    return text
