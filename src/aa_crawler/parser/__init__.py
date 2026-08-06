"""Public synchronous parser framework API."""

from aa_crawler.parser.base import BaseParser
from aa_crawler.parser.errors import (
    ArticleParserError,
    ParserContractError,
    ParserError,
    ParserExecutionError,
)

# isort: split
from aa_crawler.parser.article import JsonLdArticleParser

__all__ = [
    "ArticleParserError",
    "BaseParser",
    "JsonLdArticleParser",
    "ParserContractError",
    "ParserError",
    "ParserExecutionError",
]
