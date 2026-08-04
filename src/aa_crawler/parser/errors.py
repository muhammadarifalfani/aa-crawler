"""Parser framework errors."""

from aa_crawler.crawler import ParsingError


class ParserError(ParsingError):
    """Base exception for parser framework failures."""


class ParserContractError(ParserError):
    """Raised when a parser yields an invalid result."""


class ParserExecutionError(ParserError):
    """Raised when parser implementation execution fails unexpectedly."""
