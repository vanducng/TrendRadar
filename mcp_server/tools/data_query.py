"""
Data Query Tools

Implements P0 core data query tools.
"""

from typing import Dict, List, Optional

from ..services.data_service import DataService
from ..utils.validators import (
    validate_platforms,
    validate_limit,
    validate_keyword,
    validate_date_range,
    validate_top_n,
    validate_mode,
    validate_date_query
)
from ..utils.errors import MCPError


class DataQueryTools:
    """Data query tools class"""

    def __init__(self, project_root: str = None):
        """
        Initialize data query tools

        Args:
            project_root: Project root directory
        """
        self.data_service = DataService(project_root)

    def get_latest_news(
        self,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_url: bool = False
    ) -> Dict:
        """
        Get the latest batch of crawled news data

        Args:
            platforms: Platform ID list, e.g. ['zhihu', 'weibo']
            limit: Return limit, default 20
            include_url: Whether to include URL links, default False (save tokens)

        Returns:
            News list dictionary

        Example:
            >>> tools = DataQueryTools()
            >>> result = tools.get_latest_news(platforms=['zhihu'], limit=10)
            >>> print(result['total'])
            10
        """
        try:
            # Parameter validation
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # Get data
            news_list = self.data_service.get_latest_news(
                platforms=platforms,
                limit=limit,
                include_url=include_url
            )

            return {
                "news": news_list,
                "total": len(news_list),
                "platforms": platforms,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def search_news_by_keyword(
        self,
        keyword: str,
        date_range: Optional[Dict] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Search historical news by keyword

        Args:
            keyword: Search keyword (required)
            date_range: Date range, format: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            platforms: Platform filter list
            limit: Return limit (optional, default returns all)

        Returns:
            Search result dictionary

        Example (assuming today is 2025-11-17):
            >>> tools = DataQueryTools()
            >>> result = tools.search_news_by_keyword(
            ...     keyword="AI",
            ...     date_range={"start": "2025-11-08", "end": "2025-11-17"},
            ...     limit=50
            ... )
            >>> print(result['total'])
        """
        try:
            # Parameter validation
            keyword = validate_keyword(keyword)
            date_range_tuple = validate_date_range(date_range)
            platforms = validate_platforms(platforms)

            if limit is not None:
                limit = validate_limit(limit, default=100)

            # Search data
            search_result = self.data_service.search_news_by_keyword(
                keyword=keyword,
                date_range=date_range_tuple,
                platforms=platforms,
                limit=limit
            )

            return {
                **search_result,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def get_trending_topics(
        self,
        top_n: Optional[int] = None,
        mode: Optional[str] = None
    ) -> Dict:
        """
        Get frequency statistics for personally monitored keywords

        Note: This tool is based on the personalized watch word list in config/frequency_words.txt
        for statistics, rather than automatically extracting trending topics from news. This is a
        customizable watch word list that users can add or remove keywords according to their interests.

        Args:
            top_n: Return TOP N watched keywords, default 10
            mode: Mode - daily (daily cumulative), current (latest batch), incremental (incremental)

        Returns:
            Watch word frequency statistics dictionary, containing the number of times each watched keyword appears in news

        Example:
            >>> tools = DataQueryTools()
            >>> result = tools.get_trending_topics(top_n=5, mode="current")
            >>> print(len(result['topics']))
            5
            >>> # Returns frequency statistics for keywords you set in frequency_words.txt
        """
        try:
            # Parameter validation
            top_n = validate_top_n(top_n, default=10)
            valid_modes = ["daily", "current", "incremental"]
            mode = validate_mode(mode, valid_modes, default="current")

            # Get trending topics
            trending_result = self.data_service.get_trending_topics(
                top_n=top_n,
                mode=mode
            )

            return {
                **trending_result,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

    def get_news_by_date(
        self,
        date_query: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None,
        include_url: bool = False
    ) -> Dict:
        """
        Query news by date, supports natural language dates

        Args:
            date_query: Date query string (optional, default "today"), supports:
                - Relative dates: today, yesterday, 2 days ago, yesterday, 3 days ago
                - Weekdays: last Monday, this Wednesday, last monday, this friday
                - Absolute dates: 2025-10-10, Oct 10, October 10, 2025
            platforms: Platform ID list, e.g. ['zhihu', 'weibo']
            limit: Return limit, default 50
            include_url: Whether to include URL links, default False (save tokens)

        Returns:
            News list dictionary

        Example:
            >>> tools = DataQueryTools()
            >>> # Query today by default if date not specified
            >>> result = tools.get_news_by_date(platforms=['zhihu'], limit=20)
            >>> # Specify date
            >>> result = tools.get_news_by_date(
            ...     date_query="yesterday",
            ...     platforms=['zhihu'],
            ...     limit=20
            ... )
            >>> print(result['total'])
            20
        """
        try:
            # Parameter validation - default to today
            if date_query is None:
                date_query = "今天"
            target_date = validate_date_query(date_query)
            platforms = validate_platforms(platforms)
            limit = validate_limit(limit, default=50)

            # Get data
            news_list = self.data_service.get_news_by_date(
                target_date=target_date,
                platforms=platforms,
                limit=limit,
                include_url=include_url
            )

            return {
                "news": news_list,
                "total": len(news_list),
                "date": target_date.strftime("%Y-%m-%d"),
                "date_query": date_query,
                "platforms": platforms,
                "success": True
            }

        except MCPError as e:
            return {
                "success": False,
                "error": e.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }

