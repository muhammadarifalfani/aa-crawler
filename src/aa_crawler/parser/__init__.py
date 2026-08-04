"""Public synchronous parser framework API."""

from aa_crawler.parser.base import BaseParser
from aa_crawler.parser.errors import (
    ParserContractError,
    ParserError,
    ParserExecutionError,
)

__all__ = [
    "BaseParser",
    "ParserContractError",
    "ParserError",
    "ParserExecutionError",
]
