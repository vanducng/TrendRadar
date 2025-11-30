"""
TrendRadar MCP Server - FastMCP 2.0 Implementation

Provides production-grade MCP tool server using FastMCP 2.0.
Supports both stdio and HTTP transport modes.
"""

import json
from typing import List, Optional, Dict

from fastmcp import FastMCP

from .tools.data_query import DataQueryTools
from .tools.analytics import AnalyticsTools
from .tools.search_tools import SearchTools
from .tools.config_mgmt import ConfigManagementTools
from .tools.system import SystemManagementTools
from .utils.date_parser import DateParser
from .utils.errors import MCPError


# Create FastMCP 2.0 application
mcp = FastMCP('trendradar-news')

# Global tool instances (initialized on first request)
_tools_instances = {}


def _get_tools(project_root: Optional[str] = None):
    """Get or create tool instances (singleton pattern)"""
    if not _tools_instances:
        _tools_instances['data'] = DataQueryTools(project_root)
        _tools_instances['analytics'] = AnalyticsTools(project_root)
        _tools_instances['search'] = SearchTools(project_root)
        _tools_instances['config'] = ConfigManagementTools(project_root)
        _tools_instances['system'] = SystemManagementTools(project_root)
    return _tools_instances


# ==================== Date Parsing Tools (Recommended Priority) ====================

@mcp.tool
async def resolve_date_range(
    expression: str
) -> str:
    """
    [Recommended Priority] Parse natural language date expressions into standard date ranges

    **Why is this tool needed?**
    Users often use natural language like "this week", "last 7 days" to express dates,
    but AI models calculating dates themselves may lead to inconsistent results. This tool
    uses precise server-side current time calculations to ensure all AI models get
    consistent date ranges.

    **Recommended Usage Flow:**
    1. User says "analyze AI sentiment this week"
    2. AI calls resolve_date_range("this week") -> get precise date range
    3. AI calls analyze_sentiment(topic="ai", date_range=date_range from previous step)

    Args:
        expression: Natural language date expression, supports:
            - Single day: "today", "yesterday"
            - Week: "this week", "last week"
            - Month: "this month", "last month"
            - Last N days: "last 7 days", "last 30 days"
            - Dynamic: "last 5 days", "last 10 days" (any number of days)

    Returns:
        JSON formatted date range, can be directly used for other tools' date_range parameter:
        {
            "success": true,
            "expression": "this week",
            "date_range": {
                "start": "2025-11-18",
                "end": "2025-11-26"
            },
            "current_date": "2025-11-26",
            "description": "This week (Monday to Sunday, 11-18 to 11-26)"
        }

    Examples:
        User: "Analyze AI sentiment this week"
        AI call steps:
        1. resolve_date_range("this week")
           -> {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}, ...}
        2. analyze_sentiment(topic="ai", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        User: "Show Tesla news from last 7 days"
        AI call steps:
        1. resolve_date_range("last 7 days")
           -> {"date_range": {"start": "2025-11-20", "end": "2025-11-26"}, ...}
        2. search_news(query="Tesla", date_range={"start": "2025-11-20", "end": "2025-11-26"})
    """
    try:
        result = DateParser.resolve_date_range_expression(expression)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except MCPError as e:
        return json.dumps({
            "success": False,
            "error": e.to_dict()
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        }, ensure_ascii=False, indent=2)


# ==================== Data Query Tools ====================

@mcp.tool
async def get_latest_news(
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Get the latest batch of crawled news data for quick understanding of current hot topics

    Args:
        platforms: Platform ID list, e.g. ['zhihu', 'weibo', 'douyin']
                   - When not specified: uses all platforms from config.yaml
                   - Supported platforms come from platforms configuration in config/config.yaml
                   - Each platform has a corresponding name field for AI recognition
        limit: Return count limit, default 50, max 1000
               Note: Actual return count may be less than requested, depending on available news
        include_url: Whether to include URL links, default False (saves tokens)

    Returns:
        JSON formatted news list

    **Important: Data Display Recommendations**
    This tool returns the complete news list (usually 50 items) to you. Note:
    - **Tool returns**: Complete 50 items of data
    - **Recommended display**: Show all data to user, unless user explicitly requests summary
    - **User expectation**: User may need complete data, be careful with summarization

    **When to summarize**:
    - User explicitly says "give me a summary" or "just the highlights"
    - When data exceeds 100 items, show partial first and ask if user wants to see all

    **Note**: If user asks "why only partial display", they need complete data
    """
    tools = _get_tools()
    result = tools['data'].get_latest_news(platforms=platforms, limit=limit, include_url=include_url)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_trending_topics(
    top_n: int = 10,
    mode: str = 'current'
) -> str:
    """
    Get frequency statistics for personal watchlist keywords in news (based on config/frequency_words.txt)

    Note: This tool does not automatically extract hot topics from news, but rather counts
    the frequency of your personal watchlist keywords (in config/frequency_words.txt) appearing
    in news. You can customize this watchlist.

    Args:
        top_n: Return TOP N keywords, default 10
        mode: Mode selection
            - daily: Daily cumulative data statistics
            - current: Latest batch data statistics (default)

    Returns:
        JSON formatted watchlist keyword frequency statistics
    """
    tools = _get_tools()
    result = tools['data'].get_trending_topics(top_n=top_n, mode=mode)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_news_by_date(
    date_query: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Get news data for specified date, for historical data analysis and comparison

    Args:
        date_query: Date query, optional formats:
            - Natural language: "today", "yesterday", "3 days ago"
            - Standard date: "2024-01-15", "2024/01/15"
            - Default: "today" (saves tokens)
        platforms: Platform ID list, e.g. ['zhihu', 'weibo', 'douyin']
                   - When not specified: uses all platforms from config.yaml
                   - Supported platforms come from platforms configuration in config/config.yaml
                   - Each platform has a corresponding name field for AI recognition
        limit: Return count limit, default 50, max 1000
               Note: Actual return count may be less, depending on news count for specified date
        include_url: Whether to include URL links, default False (saves tokens)

    Returns:
        JSON formatted news list, including title, platform, rank, etc.

    **Important: Data Display Recommendations**
    This tool returns the complete news list (usually 50 items) to you. Note:
    - **Tool returns**: Complete 50 items of data
    - **Recommended display**: Show all data to user, unless user explicitly requests summary
    - **User expectation**: User may need complete data, be careful with summarization

    **When to summarize**:
    - User explicitly says "give me a summary" or "just the highlights"
    - When data exceeds 100 items, show partial first and ask if user wants to see all

    **Note**: If user asks "why only partial display", they need complete data
    """
    tools = _get_tools()
    result = tools['data'].get_news_by_date(
        date_query=date_query,
        platforms=platforms,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)



# ==================== Advanced Data Analytics Tools ====================

@mcp.tool
async def analyze_topic_trend(
    topic: str,
    analysis_type: str = "trend",
    date_range: Optional[Dict[str, str]] = None,
    granularity: str = "day",
    threshold: float = 3.0,
    time_window: int = 24,
    lookahead_hours: int = 6,
    confidence_threshold: float = 0.7
) -> str:
    """
    Unified topic trend analysis tool - integrates multiple trend analysis modes

    **Important: Date Range Handling**
    When user uses "this week", "last 7 days" etc., first call resolve_date_range to get precise date:
    1. Call resolve_date_range("this week") -> Get {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    2. Pass the returned date_range to this tool

    Args:
        topic: Topic keyword (required)
        analysis_type: Analysis type, options:
            - "trend": Popularity trend analysis (track topic popularity changes)
            - "lifecycle": Lifecycle analysis (complete cycle from emergence to disappearance)
            - "viral": Abnormal popularity detection (identify suddenly viral topics)
            - "predict": Topic prediction (predict potential future hot topics)
        date_range: Date range (trend and lifecycle modes), optional
                    - **Format**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **How to get**: Call resolve_date_range tool to parse natural language dates
                    - **Default**: Analyzes last 7 days when not specified
        granularity: Time granularity (trend mode), default "day" (only supports day as underlying data is daily aggregated)
        threshold: Popularity surge multiplier threshold (viral mode), default 3.0
        time_window: Detection time window in hours (viral mode), default 24
        lookahead_hours: Hours to predict ahead (predict mode), default 6
        confidence_threshold: Confidence threshold (predict mode), default 0.7

    Returns:
        JSON formatted trend analysis results

    Examples:
        User: "Analyze AI trend this week"
        Recommended call flow:
        1. resolve_date_range("this week") -> {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}}
        2. analyze_topic_trend(topic="AI", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        User: "Check Tesla popularity over last 30 days"
        Recommended call flow:
        1. resolve_date_range("last 30 days") -> {"date_range": {"start": "2025-10-28", "end": "2025-11-26"}}
        2. analyze_topic_trend(topic="Tesla", analysis_type="lifecycle", date_range=...)
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_topic_trend_unified(
        topic=topic,
        analysis_type=analysis_type,
        date_range=date_range,
        granularity=granularity,
        threshold=threshold,
        time_window=time_window,
        lookahead_hours=lookahead_hours,
        confidence_threshold=confidence_threshold
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_data_insights(
    insight_type: str = "platform_compare",
    topic: Optional[str] = None,
    date_range: Optional[Dict[str, str]] = None,
    min_frequency: int = 3,
    top_n: int = 20
) -> str:
    """
    Unified data insight analysis tool - integrates multiple data analysis modes

    Args:
        insight_type: Insight type, options:
            - "platform_compare": Platform comparison analysis (compare attention to topics across platforms)
            - "platform_activity": Platform activity statistics (statistics on publication frequency and active times)
            - "keyword_cooccur": Keyword co-occurrence analysis (analyze patterns of keywords appearing together)
        topic: Topic keyword (optional, applicable to platform_compare mode)
        date_range: **[Object type]** Date range (optional)
                    - **Format**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **Example**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **Important**: Must be object format, cannot pass integer
        min_frequency: Minimum co-occurrence frequency (keyword_cooccur mode), default 3
        top_n: Return TOP N results (keyword_cooccur mode), default 20

    Returns:
        JSON formatted data insight analysis results

    Examples:
        - analyze_data_insights(insight_type="platform_compare", topic="artificial intelligence")
        - analyze_data_insights(insight_type="platform_activity", date_range={"start": "2025-01-01", "end": "2025-01-07"})
        - analyze_data_insights(insight_type="keyword_cooccur", min_frequency=5, top_n=15)
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_data_insights_unified(
        insight_type=insight_type,
        topic=topic,
        date_range=date_range,
        min_frequency=min_frequency,
        top_n=top_n
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_sentiment(
    topic: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    date_range: Optional[Dict[str, str]] = None,
    limit: int = 50,
    sort_by_weight: bool = True,
    include_url: bool = False
) -> str:
    """
    Analyze sentiment tendency and popularity trends of news

    **Important: Date Range Handling**
    When user uses "this week", "last 7 days" etc., first call resolve_date_range to get precise date:
    1. Call resolve_date_range("this week") -> Get {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    2. Pass the returned date_range to this tool

    Args:
        topic: Topic keyword (optional)
        platforms: Platform ID list, e.g. ['zhihu', 'weibo', 'douyin']
                   - When not specified: uses all platforms from config.yaml
                   - Supported platforms come from platforms configuration in config/config.yaml
                   - Each platform has a corresponding name field for AI recognition
        date_range: Date range (optional)
                    - **Format**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **How to get**: Call resolve_date_range tool to parse natural language dates
                    - **Default**: Queries today's data when not specified
        limit: Return news count, default 50, max 100
               Note: This tool deduplicates news titles (same title across platforms kept only once),
               so actual return count may be less than requested limit
        sort_by_weight: Whether to sort by popularity weight, default True
        include_url: Whether to include URL links, default False (saves tokens)

    Returns:
        JSON formatted analysis results, including sentiment distribution, popularity trends and related news

    Examples:
        User: "Analyze AI sentiment this week"
        Recommended call flow:
        1. resolve_date_range("this week") -> {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}}
        2. analyze_sentiment(topic="AI", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        User: "Analyze Tesla news sentiment over last 7 days"
        Recommended call flow:
        1. resolve_date_range("last 7 days") -> {"date_range": {"start": "2025-11-20", "end": "2025-11-26"}}
        2. analyze_sentiment(topic="Tesla", date_range={"start": "2025-11-20", "end": "2025-11-26"})

    **Important: Data Display Strategy**
    - This tool returns complete analysis results and news list
    - **Default display method**: Show complete analysis results (including all news)
    - Only filter when user explicitly requests "summary" or "highlights"
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_sentiment(
        topic=topic,
        platforms=platforms,
        date_range=date_range,
        limit=limit,
        sort_by_weight=sort_by_weight,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def find_similar_news(
    reference_title: str,
    threshold: float = 0.6,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Find other news similar to specified news title

    Args:
        reference_title: News title (complete or partial)
        threshold: Similarity threshold, between 0-1, default 0.6
                   Note: Higher threshold means stricter matching, fewer results
        limit: Return count limit, default 50, max 100
               Note: Actual return count depends on similarity matching results, may be less than requested
        include_url: Whether to include URL links, default False (saves tokens)

    Returns:
        JSON formatted similar news list, including similarity scores

    **Important: Data Display Strategy**
    - This tool returns complete similar news list
    - **Default display method**: Show all returned news (including similarity scores)
    - Only filter when user explicitly requests "summary" or "highlights"
    """
    tools = _get_tools()
    result = tools['analytics'].find_similar_news(
        reference_title=reference_title,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def generate_summary_report(
    report_type: str = "daily",
    date_range: Optional[Dict[str, str]] = None
) -> str:
    """
    Daily/Weekly summary generator - automatically generate hot topic summary reports

    Args:
        report_type: Report type (daily/weekly)
        date_range: **[Object type]** Custom date range (optional)
                    - **Format**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **Example**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **Important**: Must be object format, cannot pass integer

    Returns:
        JSON formatted summary report, including Markdown format content
    """
    tools = _get_tools()
    result = tools['analytics'].generate_summary_report(
        report_type=report_type,
        date_range=date_range
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Smart Search Tools ====================

@mcp.tool
async def search_news(
    query: str,
    search_mode: str = "keyword",
    date_range: Optional[Dict[str, str]] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    sort_by: str = "relevance",
    threshold: float = 0.6,
    include_url: bool = False
) -> str:
    """
    Unified search interface, supports multiple search modes

    **Important: Date Range Handling**
    When user uses "this week", "last 7 days" etc., first call resolve_date_range to get precise date:
    1. Call resolve_date_range("this week") -> Get {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    2. Pass the returned date_range to this tool

    Args:
        query: Search keyword or content fragment
        search_mode: Search mode, options:
            - "keyword": Exact keyword matching (default, suitable for searching specific topics)
            - "fuzzy": Fuzzy content matching (suitable for content fragments, filters results below threshold)
            - "entity": Entity name search (suitable for searching people/places/organizations)
        date_range: Date range (optional)
                    - **Format**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **How to get**: Call resolve_date_range tool to parse natural language dates
                    - **Default**: Queries today's news when not specified
        platforms: Platform ID list, e.g. ['zhihu', 'weibo', 'douyin']
                   - When not specified: uses all platforms from config.yaml
                   - Supported platforms come from platforms configuration in config/config.yaml
                   - Each platform has a corresponding name field for AI recognition
        limit: Return count limit, default 50, max 1000
               Note: Actual return count depends on search matches (especially in fuzzy mode which filters low similarity results)
        sort_by: Sort method, options:
            - "relevance": Sort by relevance (default)
            - "weight": Sort by news weight
            - "date": Sort by date
        threshold: Similarity threshold (only effective in fuzzy mode), between 0-1, default 0.6
                   Note: Higher threshold means stricter matching, fewer results
        include_url: Whether to include URL links, default False (saves tokens)

    Returns:
        JSON formatted search results, including title, platform, rank, etc.

    Examples:
        User: "Search AI news this week"
        Recommended call flow:
        1. resolve_date_range("this week") -> {"date_range": {"start": "2025-11-18", "end": "2025-11-26"}}
        2. search_news(query="AI", date_range={"start": "2025-11-18", "end": "2025-11-26"})

        User: "Tesla news last 7 days"
        Recommended call flow:
        1. resolve_date_range("last 7 days") -> {"date_range": {"start": "2025-11-20", "end": "2025-11-26"}}
        2. search_news(query="Tesla", date_range={"start": "2025-11-20", "end": "2025-11-26"})

        User: "AI news today" (default today, no need to resolve)
        -> search_news(query="AI")

    **Important: Data Display Strategy**
    - This tool returns complete search results list
    - **Default display method**: Show all returned news, no summarization or filtering needed
    - Only filter when user explicitly requests "summary" or "highlights"
    """
    tools = _get_tools()
    result = tools['search'].search_news_unified(
        query=query,
        search_mode=search_mode,
        date_range=date_range,
        platforms=platforms,
        limit=limit,
        sort_by=sort_by,
        threshold=threshold,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def search_related_news_history(
    reference_text: str,
    time_preset: str = "yesterday",
    threshold: float = 0.4,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    Search related news in historical data based on seed news

    Args:
        reference_text: Reference news title (complete or partial)
        time_preset: Time range preset, options:
            - "yesterday": Yesterday
            - "last_week": Last week (7 days)
            - "last_month": Last month (30 days)
            - "custom": Custom date range (requires start_date and end_date)
        threshold: Relevance threshold, between 0-1, default 0.4
                   Note: Comprehensive similarity calculation (70% keyword overlap + 30% text similarity)
                   Higher threshold means stricter matching, fewer results
        limit: Return count limit, default 50, max 100
               Note: Actual return count depends on relevance matching results, may be less than requested
        include_url: Whether to include URL links, default False (saves tokens)

    Returns:
        JSON formatted related news list, including relevance scores and time distribution

    **Important: Data Display Strategy**
    - This tool returns complete related news list
    - **Default display method**: Show all returned news (including relevance scores)
    - Only filter when user explicitly requests "summary" or "highlights"
    """
    tools = _get_tools()
    result = tools['search'].search_related_news_history(
        reference_text=reference_text,
        time_preset=time_preset,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Configuration & System Management Tools ====================

@mcp.tool
async def get_current_config(
    section: str = "all"
) -> str:
    """
    Get current system configuration

    Args:
        section: Config section, options:
            - "all": All configurations (default)
            - "crawler": Crawler configuration
            - "push": Push notification configuration
            - "keywords": Keywords configuration
            - "weights": Weights configuration

    Returns:
        JSON formatted configuration information
    """
    tools = _get_tools()
    result = tools['config'].get_current_config(section=section)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_system_status() -> str:
    """
    Get system running status and health check information

    Returns system version, data statistics, cache status, etc.

    Returns:
        JSON formatted system status information
    """
    tools = _get_tools()
    result = tools['system'].get_system_status()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def trigger_crawl(
    platforms: Optional[List[str]] = None,
    save_to_local: bool = False,
    include_url: bool = False
) -> str:
    """
    Manually trigger a crawl task (optional persistence)

    Args:
        platforms: Specify platform ID list, e.g. ['zhihu', 'weibo', 'douyin']
                   - When not specified: uses all platforms from config.yaml
                   - Supported platforms come from platforms configuration in config/config.yaml
                   - Each platform has a corresponding name field for AI recognition
                   - Note: Failed platforms will be listed in the failed_platforms field of return result
        save_to_local: Whether to save to local output directory, default False
        include_url: Whether to include URL links, default False (saves tokens)

    Returns:
        JSON formatted task status information, including:
        - platforms: List of successfully crawled platforms
        - failed_platforms: List of failed platforms (if any)
        - total_news: Total news count crawled
        - data: News data

    Examples:
        - Temporary crawl: trigger_crawl(platforms=['zhihu'])
        - Crawl and save: trigger_crawl(platforms=['weibo'], save_to_local=True)
        - Use default platforms: trigger_crawl()  # Crawl all platforms configured in config.yaml
    """
    tools = _get_tools()
    result = tools['system'].trigger_crawl(platforms=platforms, save_to_local=save_to_local, include_url=include_url)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== Entry Point ====================

def run_server(
    project_root: Optional[str] = None,
    transport: str = 'stdio',
    host: str = '0.0.0.0',
    port: int = 3333
):
    """
    Start MCP server

    Args:
        project_root: Project root directory path
        transport: Transport mode, 'stdio' or 'http'
        host: Listen address for HTTP mode, default 0.0.0.0
        port: Listen port for HTTP mode, default 3333
    """
    # Initialize tool instances
    _get_tools(project_root)

    # Print startup information
    print()
    print("=" * 60)
    print("  TrendRadar MCP Server - FastMCP 2.0")
    print("=" * 60)
    print(f"  Transport mode: {transport.upper()}")

    if transport == 'stdio':
        print("  Protocol: MCP over stdio (standard input/output)")
        print("  Description: Communicates with MCP client via standard I/O")
    elif transport == 'http':
        print(f"  Protocol: MCP over HTTP (production environment)")
        print(f"  Server listening: {host}:{port}")

    if project_root:
        print(f"  Project directory: {project_root}")
    else:
        print("  Project directory: Current directory")

    print()
    print("  Registered tools:")
    print("    === Date Parsing Tools (Recommended Priority) ===")
    print("    0. resolve_date_range       - Parse natural language dates to standard format")
    print()
    print("    === Basic Data Query (P0 Core) ===")
    print("    1. get_latest_news        - Get latest news")
    print("    2. get_news_by_date       - Query news by date (supports natural language)")
    print("    3. get_trending_topics    - Get trending topics")
    print()
    print("    === Smart Search Tools ===")
    print("    4. search_news                  - Unified news search (keyword/fuzzy/entity)")
    print("    5. search_related_news_history  - Historical related news search")
    print()
    print("    === Advanced Data Analytics ===")
    print("    6. analyze_topic_trend      - Unified topic trend analysis (popularity/lifecycle/viral/predict)")
    print("    7. analyze_data_insights    - Unified data insight analysis (platform compare/activity/keyword co-occurrence)")
    print("    8. analyze_sentiment        - Sentiment analysis")
    print("    9. find_similar_news        - Find similar news")
    print("    10. generate_summary_report - Daily/weekly summary generation")
    print()
    print("    === Configuration & System Management ===")
    print("    11. get_current_config      - Get current system configuration")
    print("    12. get_system_status       - Get system running status")
    print("    13. trigger_crawl           - Manually trigger crawl task")
    print("=" * 60)
    print()

    # Run server based on transport mode
    if transport == 'stdio':
        mcp.run(transport='stdio')
    elif transport == 'http':
        # HTTP mode (production recommended)
        mcp.run(
            transport='http',
            host=host,
            port=port,
            path='/mcp'  # HTTP endpoint path
        )
    else:
        raise ValueError(f"Unsupported transport mode: {transport}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='TrendRadar MCP Server - News Hot Topic Aggregation MCP Tool Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
For detailed configuration tutorial, see: README-Cherry-Studio.md
        """
    )
    parser.add_argument(
        '--transport',
        choices=['stdio', 'http'],
        default='stdio',
        help='Transport mode: stdio (default) or http (production environment)'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Listen address for HTTP mode, default 0.0.0.0'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=3333,
        help='Listen port for HTTP mode, default 3333'
    )
    parser.add_argument(
        '--project-root',
        help='Project root directory path'
    )

    args = parser.parse_args()

    run_server(
        project_root=args.project_root,
        transport=args.transport,
        host=args.host,
        port=args.port
    )
