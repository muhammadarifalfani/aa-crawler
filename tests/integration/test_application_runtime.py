"""Cross-package verification of application runtime composition."""

from __future__ import annotations

import logging
from importlib import metadata
from typing import TYPE_CHECKING

import pytest

import aa_crawler.application.runtime as runtime_module
from aa_crawler import bootstrap_application
from aa_crawler.application import (
    ApplicationRuntime,
    ArticleCrawlService,
    create_application_runtime,
)
from aa_crawler.composition import ParserComposer
from aa_crawler.configuration import ApplicationSettings
from aa_crawler.html import HtmlFetcher
from aa_crawler.http import HttpClient, RetryPolicy, TimeoutPolicy
from aa_crawler.identity import RequestIdentity
from aa_crawler.robots import RobotsPolicy
from aa_crawler.sources import DEFAULT_SOURCE_PROFILES, SourceRegistry

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from pytest import MonkeyPatch

    from aa_crawler.crawler import CrawlerRequest, CrawlerResponse


@pytest.fixture(autouse=True)
def restore_aa_crawler_logger() -> Iterator[None]:
    """Keep real bootstrap logging isolated from the process test state."""
    logger = logging.getLogger("aa_crawler")
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    yield
    for handler in logger.handlers:
        if handler not in original_handlers:
            handler.close()
    logger.handlers = original_handlers
    logger.setLevel(original_level)
    logger.propagate = original_propagate


class NetworkGuardHttpClient(HttpClient):
    """Use the real client lifecycle while rejecting every send attempt."""

    def __init__(
        self,
        *,
        timeout_policy: TimeoutPolicy,
        retry_policy: RetryPolicy,
    ) -> None:
        super().__init__(
            timeout_policy=timeout_policy,
            retry_policy=retry_policy,
        )
        self.close_count = 0
        self.send_count = 0

    def send(self, request: CrawlerRequest) -> CrawlerResponse:
        self.send_count += 1
        raise AssertionError(
            f"runtime construction attempted network access: {request}"
        )

    def close(self) -> None:
        self.close_count += 1
        super().close()


class RuntimeGraphRecorder:
    """Record construction while returning real cross-package collaborators."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.identities: list[RequestIdentity] = []
        self.timeout_policies: list[TimeoutPolicy] = []
        self.retry_policies: list[RetryPolicy] = []
        self.clients: list[NetworkGuardHttpClient] = []
        self.robots_policies: list[RobotsPolicy] = []
        self.fetchers: list[HtmlFetcher] = []
        self.registries: list[SourceRegistry] = []
        self.composers: list[ParserComposer] = []
        self.services: list[ArticleCrawlService] = []
        self.fetcher_wiring: list[
            tuple[NetworkGuardHttpClient, RobotsPolicy, RequestIdentity]
        ] = []

    def resolve_version(self, distribution_name: str) -> str:
        self.events.append("version")
        assert distribution_name == "aa-crawler"
        return "7.6.5"

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
        assert profiles is DEFAULT_SOURCE_PROFILES
        registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
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
    ) -> NetworkGuardHttpClient:
        self.events.append("client")
        client = NetworkGuardHttpClient(
            timeout_policy=timeout_policy,
            retry_policy=retry_policy,
        )
        self.clients.append(client)
        return client

    def create_robots_policy(
        self,
        *,
        http_client: NetworkGuardHttpClient,
        identity: RequestIdentity,
    ) -> RobotsPolicy:
        self.events.append("robots")
        policy = RobotsPolicy(http_client=http_client, identity=identity)
        self.robots_policies.append(policy)
        return policy

    def create_fetcher(
        self,
        *,
        http_client: NetworkGuardHttpClient,
        robots_policy: RobotsPolicy,
        identity: RequestIdentity,
    ) -> HtmlFetcher:
        self.events.append("fetcher")
        fetcher = HtmlFetcher(
            http_client=http_client,
            robots_policy=robots_policy,
            identity=identity,
        )
        self.fetchers.append(fetcher)
        self.fetcher_wiring.append((http_client, robots_policy, identity))
        return fetcher

    def create_service(
        self,
        *,
        source_registry: SourceRegistry,
        html_fetcher: HtmlFetcher,
        parser_composer: ParserComposer,
    ) -> ArticleCrawlService:
        self.events.append("service")
        service = ArticleCrawlService(
            source_registry=source_registry,
            html_fetcher=html_fetcher,
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


def test_real_runtime_graph_uses_one_identity_and_real_collaborators(
    monkeypatch: MonkeyPatch,
) -> None:
    profile_snapshot = tuple(profile.to_dict() for profile in DEFAULT_SOURCE_PROFILES)
    recorder = RuntimeGraphRecorder()
    recorder.install(monkeypatch)

    runtime = create_application_runtime()

    assert isinstance(runtime, ApplicationRuntime)
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
    assert all(
        len(instances) == 1
        for instances in (
            recorder.identities,
            recorder.timeout_policies,
            recorder.retry_policies,
            recorder.clients,
            recorder.robots_policies,
            recorder.fetchers,
            recorder.registries,
            recorder.composers,
            recorder.services,
        )
    )
    identity = recorder.identities[0]
    client, robots_policy, fetcher_identity = recorder.fetcher_wiring[0]
    assert identity.product_version == "7.6.5"
    assert robots_policy.identity is identity
    assert fetcher_identity is identity
    assert recorder.fetchers[0].identity is identity
    assert client is recorder.clients[0]
    assert runtime.article_crawl_service is recorder.services[0]
    assert runtime.article_crawl_service.source_registry is recorder.registries[0]
    assert runtime.article_crawl_service.html_fetcher is recorder.fetchers[0]
    assert runtime.article_crawl_service.parser_composer is recorder.composers[0]
    assert recorder.clients[0].send_count == 0
    assert tuple(profile.to_dict() for profile in DEFAULT_SOURCE_PROFILES) == (
        profile_snapshot
    )

    runtime.close()


def test_context_and_explicit_close_use_the_runtime_owner(
    monkeypatch: MonkeyPatch,
) -> None:
    recorder = RuntimeGraphRecorder()
    recorder.install(monkeypatch)

    with create_application_runtime() as runtime:
        assert runtime.__enter__() is runtime
        assert recorder.clients[0].close_count == 0
        assert recorder.clients[0].send_count == 0
        runtime.close()
        runtime.close()
        assert recorder.clients[0].close_count == 1

    assert recorder.clients[0].close_count == 1


def test_failure_after_client_acquisition_closes_and_preserves_error(
    monkeypatch: MonkeyPatch,
) -> None:
    recorder = RuntimeGraphRecorder()
    recorder.install(monkeypatch)
    error = RuntimeError("injected HTML composition failure")

    def fail_fetcher(
        *,
        http_client: NetworkGuardHttpClient,
        robots_policy: RobotsPolicy,
        identity: RequestIdentity,
    ) -> HtmlFetcher:
        assert http_client is recorder.clients[0]
        assert robots_policy is recorder.robots_policies[0]
        assert identity is recorder.identities[0]
        raise error

    monkeypatch.setattr(runtime_module, "HtmlFetcher", fail_fetcher)

    with pytest.raises(RuntimeError) as caught:
        create_application_runtime()

    assert caught.value is error
    assert recorder.clients[0].close_count == 1
    assert recorder.services == []


def test_metadata_failure_precedes_resource_acquisition(
    monkeypatch: MonkeyPatch,
) -> None:
    recorder = RuntimeGraphRecorder()
    recorder.install(monkeypatch)
    error = metadata.PackageNotFoundError("aa-crawler")

    def fail_version(distribution_name: str) -> str:
        assert distribution_name == "aa-crawler"
        raise error

    monkeypatch.setattr(runtime_module.metadata, "version", fail_version)

    with pytest.raises(metadata.PackageNotFoundError) as caught:
        create_application_runtime()

    assert caught.value is error
    assert recorder.events == []
    assert recorder.clients == []


def test_multiple_runtime_cycles_are_independent_and_repeatable(
    monkeypatch: MonkeyPatch,
) -> None:
    recorder = RuntimeGraphRecorder()
    recorder.install(monkeypatch)

    first = create_application_runtime()
    first.close()
    second = create_application_runtime()

    assert first is not second
    assert recorder.services[0] is not recorder.services[1]
    assert recorder.clients[0] is not recorder.clients[1]
    assert recorder.identities[0] is not recorder.identities[1]
    assert recorder.registries[0] is not recorder.registries[1]
    assert recorder.composers[0] is not recorder.composers[1]
    assert recorder.clients[0].close_count == 1
    assert recorder.clients[1].close_count == 0
    assert recorder.clients[0].send_count == recorder.clients[1].send_count == 0

    second.close()
    assert recorder.clients[1].close_count == 1


def test_bootstrap_and_runtime_creation_remain_separate(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    recorder = RuntimeGraphRecorder()
    recorder.install(monkeypatch)

    settings = bootstrap_application(base_dir=tmp_path / "project")

    assert isinstance(settings, ApplicationSettings)
    assert settings.paths.data_dir.is_dir()
    assert settings.paths.temp_dir.is_dir()
    assert recorder.events == []
    assert recorder.clients == []

    runtime = create_application_runtime()

    assert isinstance(runtime, ApplicationRuntime)
    assert len(recorder.clients) == 1
    assert recorder.clients[0].send_count == 0
    runtime.close()
