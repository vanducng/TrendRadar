"""
Parameter Validation Tools

Provides unified parameter validation functionality.
"""

from datetime import datetime
from typing import List, Optional
import os
import yaml

from .errors import InvalidParameterError
from .date_parser import DateParser


def get_supported_platforms() -> List[str]:
    """
    Dynamically get supported platform list from config.yaml

    Returns:
        Platform ID list

    Note:
        - Returns empty list on read failure, allowing all platforms (fallback strategy)
        - Platform list comes from platforms configuration in config/config.yaml
    """
    try:
        # Get config.yaml path (relative to current file)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "..", "..", "config", "config.yaml")
        config_path = os.path.normpath(config_path)

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            platforms = config.get('platforms', [])
            return [p['id'] for p in platforms if 'id' in p]
    except Exception as e:
        # Fallback: return empty list, allow all platforms
        print(f"Warning: Unable to load platform configuration ({config_path}): {e}")
        return []


def validate_platforms(platforms: Optional[List[str]]) -> List[str]:
    """
    Validate platform list

    Args:
        platforms: Platform ID list, None means use all platforms from config.yaml

    Returns:
        Validated platform list

    Raises:
        InvalidParameterError: Platform not supported

    Note:
        - When platforms=None, returns platform list from config.yaml
        - Validates whether platform ID exists in config.yaml platforms configuration
        - When config loading fails, allows all platforms (fallback strategy)
    """
    supported_platforms = get_supported_platforms()

    if platforms is None:
        # Return platform list from config file (user's default configuration)
        return supported_platforms if supported_platforms else []

    if not isinstance(platforms, list):
        raise InvalidParameterError("platforms parameter must be a list type")

    if not platforms:
        # When empty list, return platform list from config file
        return supported_platforms if supported_platforms else []

    # If config loading failed (supported_platforms is empty), allow all platforms
    if not supported_platforms:
        print("Warning: Platform configuration not loaded, skipping platform validation")
        return platforms

    # Validate each platform exists in configuration
    invalid_platforms = [p for p in platforms if p not in supported_platforms]
    if invalid_platforms:
        raise InvalidParameterError(
            f"Unsupported platforms: {', '.join(invalid_platforms)}",
            suggestion=f"Supported platforms (from config.yaml): {', '.join(supported_platforms)}"
        )

    return platforms


def validate_limit(limit: Optional[int], default: int = 20, max_limit: int = 1000) -> int:
    """
    Validate limit parameter

    Args:
        limit: Limit value
        default: Default value
        max_limit: Maximum limit

    Returns:
        Validated limit value

    Raises:
        InvalidParameterError: Parameter invalid
    """
    if limit is None:
        return default

    if not isinstance(limit, int):
        raise InvalidParameterError("limit parameter must be an integer type")

    if limit <= 0:
        raise InvalidParameterError("limit must be greater than 0")

    if limit > max_limit:
        raise InvalidParameterError(
            f"limit cannot exceed {max_limit}",
            suggestion=f"Please use pagination or reduce limit value"
        )

    return limit


def validate_date(date_str: str) -> datetime:
    """
    Validate date format

    Args:
        date_str: Date string (YYYY-MM-DD)

    Returns:
        datetime object

    Raises:
        InvalidParameterError: Invalid date format
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise InvalidParameterError(
            f"Invalid date format: {date_str}",
            suggestion="Please use YYYY-MM-DD format, e.g.: 2025-10-11"
        )


def validate_date_range(date_range: Optional[dict]) -> Optional[tuple]:
    """
    Validate date range

    Args:
        date_range: Date range dictionary {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

    Returns:
        (start_date, end_date) tuple, or None

    Raises:
        InvalidParameterError: Invalid date range
    """
    if date_range is None:
        return None

    if not isinstance(date_range, dict):
        raise InvalidParameterError("date_range must be a dictionary type")

    start_str = date_range.get("start")
    end_str = date_range.get("end")

    if not start_str or not end_str:
        raise InvalidParameterError(
            "date_range must contain start and end fields",
            suggestion='Example: {"start": "2025-10-01", "end": "2025-10-11"}'
        )

    start_date = validate_date(start_str)
    end_date = validate_date(end_str)

    if start_date > end_date:
        raise InvalidParameterError(
            "Start date cannot be later than end date",
            suggestion=f"start: {start_str}, end: {end_str}"
        )

    # Check if date is in the future
    today = datetime.now().date()
    if start_date.date() > today or end_date.date() > today:
        # Get available date range hint
        try:
            from ..services.data_service import DataService
            data_service = DataService()
            earliest, latest = data_service.get_available_date_range()

            if earliest and latest:
                available_range = f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}"
            else:
                available_range = "No available data"
        except Exception:
            available_range = "Unknown (please check output directory)"

        future_dates = []
        if start_date.date() > today:
            future_dates.append(start_str)
        if end_date.date() > today and end_str != start_str:
            future_dates.append(end_str)

        raise InvalidParameterError(
            f"Future dates not allowed: {', '.join(future_dates)} (current date: {today.strftime('%Y-%m-%d')})",
            suggestion=f"Available data range: {available_range}"
        )

    return (start_date, end_date)


def validate_keyword(keyword: str) -> str:
    """
    Validate keyword

    Args:
        keyword: Search keyword

    Returns:
        Processed keyword

    Raises:
        InvalidParameterError: Invalid keyword
    """
    if not keyword:
        raise InvalidParameterError("keyword cannot be empty")

    if not isinstance(keyword, str):
        raise InvalidParameterError("keyword must be a string type")

    keyword = keyword.strip()

    if not keyword:
        raise InvalidParameterError("keyword cannot be whitespace only")

    if len(keyword) > 100:
        raise InvalidParameterError(
            "keyword length cannot exceed 100 characters",
            suggestion="Please use a more concise keyword"
        )

    return keyword


def validate_top_n(top_n: Optional[int], default: int = 10) -> int:
    """
    Validate TOP N parameter

    Args:
        top_n: TOP N count
        default: Default value

    Returns:
        Validated value

    Raises:
        InvalidParameterError: Parameter invalid
    """
    return validate_limit(top_n, default=default, max_limit=100)


def validate_mode(mode: Optional[str], valid_modes: List[str], default: str) -> str:
    """
    Validate mode parameter

    Args:
        mode: Mode string
        valid_modes: Valid mode list
        default: Default mode

    Returns:
        Validated mode

    Raises:
        InvalidParameterError: Invalid mode
    """
    if mode is None:
        return default

    if not isinstance(mode, str):
        raise InvalidParameterError("mode must be a string type")

    if mode not in valid_modes:
        raise InvalidParameterError(
            f"Invalid mode: {mode}",
            suggestion=f"Supported modes: {', '.join(valid_modes)}"
        )

    return mode


def validate_config_section(section: Optional[str]) -> str:
    """
    Validate config section parameter

    Args:
        section: Config section name

    Returns:
        Validated config section

    Raises:
        InvalidParameterError: Invalid config section
    """
    valid_sections = ["all", "crawler", "push", "keywords", "weights"]
    return validate_mode(section, valid_sections, "all")


def validate_date_query(
    date_query: str,
    allow_future: bool = False,
    max_days_ago: int = 365
) -> datetime:
    """
    Validate and parse date query string

    Args:
        date_query: Date query string
        allow_future: Whether to allow future dates
        max_days_ago: Maximum days allowed for query

    Returns:
        Parsed datetime object

    Raises:
        InvalidParameterError: Invalid date query

    Examples:
        >>> validate_date_query("yesterday")
        datetime(2025, 10, 10)
        >>> validate_date_query("2025-10-10")
        datetime(2025, 10, 10)
    """
    if not date_query:
        raise InvalidParameterError(
            "Date query string cannot be empty",
            suggestion="Please provide a date query, e.g.: today, yesterday, 2025-10-10"
        )

    # Use DateParser to parse date
    parsed_date = DateParser.parse_date_query(date_query)

    # Validate date is not in the future
    if not allow_future:
        DateParser.validate_date_not_future(parsed_date)

    # Validate date is not too old
    DateParser.validate_date_not_too_old(parsed_date, max_days=max_days_ago)

    return parsed_date
