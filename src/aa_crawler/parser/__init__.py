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
from aa_crawler.parser.generic_json_article import GenericJsonArticleParser
from aa_crawler.parser.microdata_article import MicrodataArticleParser

__all__ = [
    "ArticleParserError",
    "BaseParser",
    "GenericJsonArticleParser",
    "JsonLdArticleParser",
    "MicrodataArticleParser",
    "ParserContractError",
    "ParserError",
    "ParserExecutionError",
]
