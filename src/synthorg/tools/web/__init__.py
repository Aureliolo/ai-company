"""Built-in web tools for HTTP requests, search, and HTML parsing."""

from synthorg.tools.web.base_web_tool import BaseWebTool
from synthorg.tools.web.config import WebToolsConfig
from synthorg.tools.web.html_parser import HtmlParserTool
from synthorg.tools.web.http_request import HttpRequestTool
from synthorg.tools.web.web_search import SearchResult, WebSearchProvider, WebSearchTool

__all__ = [
    "BaseWebTool",
    "HtmlParserTool",
    "HttpRequestTool",
    "SearchResult",
    "WebSearchProvider",
    "WebSearchTool",
    "WebToolsConfig",
]
