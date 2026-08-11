"""Tests for application runtime composition and resource ownership."""

from __future__ import annotations

from importlib import metadata
from typing import TYPE_CHECKING, cast

import pytest

import aa_crawler.application.runtime as runtime_module
from aa_crawler.application import (
    ApplicationRuntime,
    ArticleCrawlService,
    create_application_runtime,
)
from aa_crawler.composition import ParserComposer
from aa_crawler.http import RetryPolicy, TimeoutPolicy
from aa_crawler.identity import RequestIdentity
from aa_crawler.sources import SourceRegistry

if TYPE_CHECKING:
    from types import TracebackType

    from pytest import MonkeyPatch

    from aa_crawler.html import HtmlFetcher


class RecordingHttpClient:
    """Record explicit policies and synchronous lifecycle calls."""

    def __init__(
        self,
        *,
        timeout_policy: TimeoutPolicy,
        retry_policy: RetryPolicy,
    ) -> None:
        self.timeout_policy = timeout_policy
        self.retry_policy = retry_policy
        self.enter_count = 0
        self.close_count = 0

    @property
    def is_open(self) -> bool:
        return self.enter_count == 1 and self.close_count == 0

    def __enter__(self) -> RecordingHttpClient:
        self.enter_count += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.close_count += 1


class RecordingRobotsPolicy:
    """Expose the identity contract while recording the client dependency."""

    def __init__(
        self,
        *,
        http_client: RecordingHttpClient,
        identity: RequestIdentity,
    ) -> None:
        self.http_client = http_client
        self.identity = identity


class RecordingHtmlFetcher:
    """Record the complete acquisition dependency graph."""

    def __init__(
        self,
        *,
        http_client: RecordingHttpClient,
        robots_policy: RecordingRobotsPolicy,
        identity: RequestIdentity,
    ) -> None:
        self.http_client = http_client
        self.robots_policy = robots_policy
        self.identity = identity


class CompositionRecorder:
    """Install and record every constructor in the approved runtime graph."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.versions: list[str] = []
        self.identities: list[RequestIdentity] = []
        self.timeout_policies: list[TimeoutPolicy] = []
        self.retry_policies: list[RetryPolicy] = []
        self.registries: list[SourceRegistry] = []
        self.composers: list[ParserComposer] = []
        self.clients: list[RecordingHttpClient] = []
        self.robots_policies: list[RecordingRobotsPolicy] = []
        self.fetchers: list[RecordingHtmlFetcher] = []
        self.services: list[ArticleCrawlService] = []

    def resolve_version(self, distribution_name: str) -> str:
        self.events.append("version")
        self.versions.append(distribution_name)
        return "9.8.7"

    def create_identity(self, *, product_version: str) -> RequestIdentity:
        self.events.append("identity")
        identity = RequestIdentity(product_version=product_version)
        self.identities.append(identity)
        return identity

    def create_timeout_policy(self) -> TimeoutPolicy:
        self.events.append("timeout")
        policy = TimeoutPolicy()
        self.timeout_policies.append(policy)
        return policy

    def create_retry_policy(self) -> RetryPolicy:
        self.events.append("retry")
        policy = RetryPolicy()
        self.retry_policies.append(policy)
        return policy

    def create_registry(self, profiles: object) -> SourceRegistry:
        self.events.append("registry")
        assert profiles is runtime_module.DEFAULT_SOURCE_PROFILES
        registry = SourceRegistry(runtime_module.DEFAULT_SOURCE_PROFILES)
        self.registries.append(registry)
        return registry

    def create_composer(self) -> ParserComposer:
        self.events.append("composer")
        composer = ParserComposer()
        self.composers.append(composer)
        return composer

    def create_client(
        self,
        *,
        timeout_policy: TimeoutPolicy,
        retry_policy: RetryPolicy,
    ) -> RecordingHttpClient:
        self.events.append("client")
        client = RecordingHttpClient(
            timeout_policy=timeout_policy,
            retry_policy=retry_policy,
        )
        self.clients.append(client)
        return client

    def create_robots_policy(
        self,
        *,
        http_client: RecordingHttpClient,
        identity: RequestIdentity,
    ) -> RecordingRobotsPolicy:
        self.events.append("robots")
        policy = RecordingRobotsPolicy(
            http_client=http_client,
            identity=identity,
        )
        self.robots_policies.append(policy)
        return policy

    def create_fetcher(
        self,
        *,
        http_client: RecordingHttpClient,
        robots_policy: RecordingRobotsPolicy,
        identity: RequestIdentity,
    ) -> RecordingHtmlFetcher:
        self.events.append("fetcher")
        fetcher = RecordingHtmlFetcher(
            http_client=http_client,
            robots_policy=robots_policy,
            identity=identity,
        )
        self.fetchers.append(fetcher)
        return fetcher

    def create_service(
        self,
        *,
        source_registry: SourceRegistry,
        html_fetcher: RecordingHtmlFetcher,
        parser_composer: ParserComposer,
    ) -> ArticleCrawlService:
        self.events.append("service")
        service = ArticleCrawlService(
            source_registry=source_registry,
            html_fetcher=cast("HtmlFetcher", html_fetcher),
            parser_composer=parser_composer,
        )
        self.services.append(service)
        return service

    def install(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setattr(runtime_module.metadata, "version", self.resolve_version)
        monkeypatch.setattr(runtime_module, "RequestIdentity", self.create_identity)
        monkeypatch.setattr(
            runtime_module,
            "TimeoutPolicy",
            self.create_timeout_policy,
        )
        monkeypatch.setattr(runtime_module, "RetryPolicy", self.create_retry_policy)
        monkeypatch.setattr(runtime_module, "SourceRegistry", self.create_registry)
        monkeypatch.setattr(runtime_module, "ParserComposer", self.create_composer)
        monkeypatch.setattr(runtime_module, "HttpClient", self.create_client)
        monkeypatch.setattr(runtime_module, "RobotsPolicy", self.create_robots_policy)
        monkeypatch.setattr(runtime_module, "HtmlFetcher", self.create_fetcher)
        monkeypatch.setattr(
            runtime_module,
            "ArticleCrawlService",
            self.create_service,
        )


def _install_acquisition_doubles(
    monkeypatch: MonkeyPatch,
) -> tuple[
    list[RecordingHttpClient],
    list[RecordingRobotsPolicy],
    list[RecordingHtmlFetcher],
]:
    clients: list[RecordingHttpClient] = []
    robots_policies: list[RecordingRobotsPolicy] = []
    fetchers: list[RecordingHtmlFetcher] = []

    def create_client(
        *,
        timeout_policy: TimeoutPolicy,
        retry_policy: RetryPolicy,
    ) -> RecordingHttpClient:
        client = RecordingHttpClient(
            timeout_policy=timeout_policy,
            retry_policy=retry_policy,
        )
        clients.append(client)
        return client

    def create_robots_policy(
        *,
        http_client: RecordingHttpClient,
        identity: RequestIdentity,
    ) -> RecordingRobotsPolicy:
        policy = RecordingRobotsPolicy(
            http_client=http_client,
            identity=identity,
        )
        robots_policies.append(policy)
        return policy

    def create_fetcher(
        *,
        http_client: RecordingHttpClient,
        robots_policy: RecordingRobotsPolicy,
        identity: RequestIdentity,
    ) -> RecordingHtmlFetcher:
        fetcher = RecordingHtmlFetcher(
            http_client=http_client,
            robots_policy=robots_policy,
            identity=identity,
        )
        fetchers.append(fetcher)
        return fetcher

    monkeypatch.setattr(runtime_module, "HttpClient", create_client)
    monkeypatch.setattr(runtime_module, "RobotsPolicy", create_robots_policy)
    monkeypatch.setattr(runtime_module, "HtmlFetcher", create_fetcher)
    return clients, robots_policies, fetchers


def test_public_application_api_is_exact() -> None:
    from aa_crawler import application

    assert application.__all__ == [
        "ApplicationError",
        "ApplicationRuntime",
        "ArticleCrawlService",
        "SourceBoundaryError",
        "UnsupportedSourceError",
        "create_application_runtime",
    ]
    assert application.ApplicationRuntime is ApplicationRuntime
    assert application.create_application_runtime is create_application_runtime


def test_runtime_is_frozen_and_exposes_only_application_service(
    monkeypatch: MonkeyPatch,
) -> None:
    clients, _, _ = _install_acquisition_doubles(monkeypatch)
    runtime = create_application_runtime()

    assert isinstance(runtime.article_crawl_service, ArticleCrawlService)
    assert not hasattr(runtime, "http_client")
    assert not hasattr(runtime, "identity")
    assert not hasattr(runtime, "robots_policy")
    assert not hasattr(runtime, "html_fetcher")
    assert not hasattr(runtime, "source_registry")
    assert not hasattr(runtime, "parser_composer")
    assert type(runtime).__setattr__ is not object.__setattr__

    runtime.close()
    assert clients[0].close_count == 1


def test_factory_composes_explicit_graph_in_required_order(
    monkeypatch: MonkeyPatch,
) -> None:
    recorder = CompositionRecorder()
    recorder.install(monkeypatch)

    runtime = create_application_runtime()

    assert recorder.events == [
        "version",
        "identity",
        "timeout",
        "retry",
        "registry",
        "composer",
        "client",
        "robots",
        "fetcher",
        "service",
    ]
    assert recorder.versions == ["aa-crawler"]
    assert recorder.identities[0].product_version == "9.8.7"
    assert recorder.robots_policies[0].identity is recorder.identities[0]
    assert recorder.fetchers[0].identity is recorder.identities[0]
    assert recorder.fetchers[0].robots_policy is recorder.robots_policies[0]
    assert recorder.clients[0].timeout_policy is recorder.timeout_policies[0]
    assert recorder.clients[0].retry_policy is recorder.retry_policies[0]
    assert recorder.robots_policies[0].http_client is recorder.clients[0]
    assert recorder.fetchers[0].http_client is recorder.clients[0]
    assert recorder.services[0].source_registry is recorder.registries[0]
    assert recorder.services[0].parser_composer is recorder.composers[0]
    assert recorder.services[0].html_fetcher is cast(
        "HtmlFetcher",
        recorder.fetchers[0],
    )
    assert runtime.article_crawl_service is recorder.services[0]

    runtime.close()


def test_metadata_failure_occurs_before_http_client_creation(
    monkeypatch: MonkeyPatch,
) -> None:
    clients, _, _ = _install_acquisition_doubles(monkeypatch)
    error = metadata.PackageNotFoundError("aa-crawler")

    def fail_version(distribution_name: str) -> str:
        assert distribution_name == "aa-crawler"
        raise error

    monkeypatch.setattr(runtime_module.metadata, "version", fail_version)

    with pytest.raises(metadata.PackageNotFoundError) as caught:
        create_application_runtime()

    assert caught.value is error
    assert clients == []


def test_context_manager_and_explicit_close_are_idempotent(
    monkeypatch: MonkeyPatch,
) -> None:
    clients, _, _ = _install_acquisition_doubles(monkeypatch)

    with create_application_runtime() as runtime:
        assert runtime.__enter__() is runtime
        assert clients[0].is_open
        runtime.close()
        runtime.close()
        assert clients[0].close_count == 1

    assert clients[0].close_count == 1


def test_downstream_construction_failure_closes_client_and_propagates(
    monkeypatch: MonkeyPatch,
) -> None:
    clients, _, _ = _install_acquisition_doubles(monkeypatch)
    error = RuntimeError("injected robots construction failure")

    def fail_robots_policy(
        *,
        http_client: RecordingHttpClient,
        identity: RequestIdentity,
    ) -> RecordingRobotsPolicy:
        assert http_client is clients[0]
        assert isinstance(identity, RequestIdentity)
        raise error

    monkeypatch.setattr(runtime_module, "RobotsPolicy", fail_robots_policy)

    with pytest.raises(RuntimeError) as caught:
        create_application_runtime()

    assert caught.value is error
    assert clients[0].close_count == 1


def test_multiple_runtimes_are_independent_and_have_no_global_state(
    monkeypatch: MonkeyPatch,
) -> None:
    clients, robots_policies, fetchers = _install_acquisition_doubles(monkeypatch)

    first = create_application_runtime()
    first.close()
    second = create_application_runtime()

    assert first is not second
    assert first.article_crawl_service is not second.article_crawl_service
    assert clients[0] is not clients[1]
    assert robots_policies[0] is not robots_policies[1]
    assert robots_policies[0].identity is not robots_policies[1].identity
    assert fetchers[0] is not fetchers[1]
    assert first.article_crawl_service.source_registry is not (
        second.article_crawl_service.source_registry
    )
    assert first.article_crawl_service.parser_composer is not (
        second.article_crawl_service.parser_composer
    )
    assert clients[0].close_count == 1
    assert clients[1].is_open

    second.close()
    assert clients[1].close_count == 1


def test_runtime_factory_does_not_depend_on_bootstrap() -> None:
    assert not hasattr(runtime_module, "bootstrap_application")
