"""Tests for application-layer error contracts."""

import aa_crawler.application as application
from aa_crawler.application import (
    ApplicationError,
    SourceBoundaryError,
    UnsupportedSourceError,
)
from aa_crawler.composition import ParserCompositionError
from aa_crawler.configuration import ConfigurationError
from aa_crawler.crawler import CrawlerError
from aa_crawler.html import HtmlError
from aa_crawler.parser import ParserError
from aa_crawler.robots import RobotsError
from aa_crawler.sources import SourceRegistryError


def test_public_api_contains_only_approved_application_symbols() -> None:
    assert application.__all__ == [
        "ApplicationError",
        "ApplicationRuntime",
        "ArticleCrawlService",
        "SourceBoundaryError",
        "UnsupportedSourceError",
        "create_application_runtime",
    ]


def test_application_errors_follow_crawler_hierarchy() -> None:
    assert issubclass(ApplicationError, CrawlerError)
    assert issubclass(UnsupportedSourceError, ApplicationError)
    assert issubclass(SourceBoundaryError, ApplicationError)


def test_application_errors_have_distinct_types() -> None:
    unsupported = UnsupportedSourceError()
    boundary = SourceBoundaryError()

    assert type(unsupported) is UnsupportedSourceError
    assert type(boundary) is SourceBoundaryError
    assert not isinstance(unsupported, SourceBoundaryError)
    assert not isinstance(boundary, UnsupportedSourceError)


def test_unsupported_source_error_has_safe_deterministic_message() -> None:
    error = UnsupportedSourceError()

    assert str(error) == "No enabled source supports the requested URL"
    assert error.args == ("No enabled source supports the requested URL",)
    assert not hasattr(error, "url")
    assert not hasattr(error, "metadata")


def test_source_boundary_error_has_safe_deterministic_message() -> None:
    error = SourceBoundaryError()

    assert str(error) == "Acquired document crossed the selected source boundary"
    assert error.args == ("Acquired document crossed the selected source boundary",)
    assert not hasattr(error, "url")
    assert not hasattr(error, "source")
    assert not hasattr(error, "metadata")


def test_existing_subsystem_errors_are_not_reparented() -> None:
    existing_error_types = (
        HtmlError,
        ParserError,
        RobotsError,
        ParserCompositionError,
        SourceRegistryError,
        ConfigurationError,
    )

    assert all(
        not issubclass(error_type, ApplicationError)
        for error_type in existing_error_types
    )


def test_application_package_does_not_expose_runtime_collaborators() -> None:
    private_runtime_names = (
        "HtmlFetcher",
        "HttpClient",
        "ParserComposer",
        "RobotsPolicy",
        "SourceRegistry",
    )

    assert all(not hasattr(application, name) for name in private_runtime_names)
