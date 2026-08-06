import pytest

from aa_crawler.crawler import ParsingError
from aa_crawler.parser import (
    ArticleParserError,
    ParserContractError,
    ParserError,
    ParserExecutionError,
)


@pytest.mark.parametrize(
    "error_type",
    [ParserError, ParserContractError, ParserExecutionError, ArticleParserError],
)
def test_parser_errors_inherit_parsing_error(error_type: type[ParserError]) -> None:
    error = error_type("safe parser failure")

    assert isinstance(error, ParsingError)
    assert str(error) == "safe parser failure"


def test_specific_errors_inherit_parser_error() -> None:
    assert issubclass(ArticleParserError, ParserError)
    assert issubclass(ParserContractError, ParserError)
    assert issubclass(ParserExecutionError, ParserError)
