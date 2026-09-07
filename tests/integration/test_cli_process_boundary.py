"""Process-boundary integration tests for the ADR-023 CLI entry point.

Exercises the real top-level ``aa_crawler.main()`` delegator, the real
``aa_crawler.cli`` argument boundary, real ``bootstrap_application()``,
and the real cross-package composition inside ``create_application_runtime()``
(identity, policies, source registry, parser composer, application service,
and real ``JsonLdArticleParser``). Only network acquisition itself, and a
small number of specific failure-injection leaves, are faked or guarded;
``HttpClient`` is always network-guarded so any attempted real send fails the
test immediately.

This module does not duplicate the Sprint 5 application/runtime integration
suites (source gates, parser ownership, runtime composition order, and
identity reuse are already proven there in depth). It proves the *joined*
process boundary: that the merged CLI reaches every one of those real
components through argv, and that CLI-local exit-code translation and
cleanup behave correctly for a compact, high-value matrix of cross-package
outcomes.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest

import aa_crawler.application.runtime as runtime_module
import aa_crawler.cli.app as cli_app_module
from aa_crawler import main
from aa_crawler.composition import ParserComposer
from aa_crawler.html import HtmlDocument
from aa_crawler.http import HttpClient, RetryPolicy, TimeoutPolicy
from aa_crawler.observability import get_correlation_id
from aa_crawler.sources import CNN_INDONESIA_PROFILE, SourceProfile

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from pytest import CaptureFixture, MonkeyPatch

    from aa_crawler.crawler import CrawlerRequest, CrawlerResponse
    from aa_crawler.identity import RequestIdentity
    from aa_crawler.parser import BaseParser
    from aa_crawler.robots import RobotsPolicy

_CNN_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/"
    "invented-cli-process-boundary-story"
)
_FOREIGN_URL = "https://foreign.example.test/article"


@pytest.fixture(autouse=True)
def restore_aa_crawler_logger() -> Iterator[None]:
    """Keep real bootstrap logging isolated from the process test state.

    Also snapshots ``aa_crawler.cli.app`` specifically: real bootstrap sets
    ``propagate = False`` on the ``aa_crawler`` logger (by design, to avoid
    double logging), which means pytest's ``caplog`` — attached at the root
    logger — cannot observe records once real logging is configured. Tests
    that need to prove a log line was emitted attach their own handler
    directly to the child logger instead; this fixture restores that logger
    too so no handler leaks between tests.
    """
    snapshots: list[tuple[logging.Logger, list[logging.Handler], int, bool]] = []
    for name in ("aa_crawler", "aa_crawler.cli.app"):
        logger = logging.getLogger(name)
        snapshots.append((logger, logger.handlers[:], logger.level, logger.propagate))
    yield
    for logger, original_handlers, original_level, original_propagate in snapshots:
        for handler in logger.handlers:
            if handler not in original_handlers:
                handler.close()
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate


class _ListLogHandler(logging.Handler):
    """Capture emitted records directly, bypassing root-logger propagation."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class NetworkGuardHttpClient(HttpClient):
    """Use the real client lifecycle while rejecting every send attempt."""

    def __init__(
        self,
        *,
        timeout_policy: TimeoutPolicy,
        retry_policy: RetryPolicy,
    ) -> None:
        super().__init__(timeout_policy=timeout_policy, retry_policy=retry_policy)
        self.send_count = 0
        self.close_count = 0

    def send(self, request: CrawlerRequest) -> CrawlerResponse:
        self.send_count += 1
        raise AssertionError(
            f"CLI process boundary attempted network access: {request}"
        )

    def close(self) -> None:
        self.close_count += 1
        super().close()


class FakeHtmlFetcher:
    """Return one deterministic document without acquisition or network access."""

    def __init__(self, document: HtmlDocument) -> None:
        self._document = document
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []
        self.wiring: tuple[HttpClient, RobotsPolicy, RequestIdentity] | None = None

    def fetch(
        self,
        *,
        url: str,
        metadata: Mapping[str, object] | None = None,
    ) -> HtmlDocument:
        self.calls.append((url, metadata))
        return self._document


class RecordingParserComposer:
    """Observe composition while delegating to the real ParserComposer."""

    def __init__(self) -> None:
        self._delegate = ParserComposer()
        self.profiles: list[SourceProfile] = []

    def create(self, profile: SourceProfile) -> BaseParser:
        self.profiles.append(profile)
        return self._delegate.create(profile)


class DenyingRobotsPolicy:
    """Expose the real identity contract while always denying acquisition."""

    def __init__(self, *, http_client: HttpClient, identity: RequestIdentity) -> None:
        self.http_client = http_client
        self.identity = identity
        self.denied_urls: list[str] = []

    def allowed(self, *, target_url: str) -> bool:
        self.denied_urls.append(target_url)
        return False


def _html_with_jsonld(node: dict[str, object], *, canonical_href: str) -> str:
    return (
        '<html lang="id-ID"><head>'
        f'<link rel="canonical" href="{canonical_href}">'
        '<script type="application/ld+json">'
        f"{json.dumps(node)}"
        "</script></head><body></body></html>"
    )


def _synthetic_document() -> HtmlDocument:
    node: dict[str, object] = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": _CNN_URL},
        "headline": "Invented CLI process-boundary headline",
        "datePublished": "2099-01-01T08:30:00+07:00",
    }
    return HtmlDocument(
        requested_url=_CNN_URL,
        final_url=_CNN_URL,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=_html_with_jsonld(node, canonical_href=_CNN_URL),
        encoding="utf-8",
    )


def _install_network_guard(monkeypatch: MonkeyPatch) -> list[NetworkGuardHttpClient]:
    clients: list[NetworkGuardHttpClient] = []

    def create_client(
        *,
        timeout_policy: TimeoutPolicy,
        retry_policy: RetryPolicy,
    ) -> NetworkGuardHttpClient:
        client = NetworkGuardHttpClient(
            timeout_policy=timeout_policy,
            retry_policy=retry_policy,
        )
        clients.append(client)
        return client

    monkeypatch.setattr(runtime_module, "HttpClient", create_client)
    return clients


def _install_fake_acquisition(
    monkeypatch: MonkeyPatch,
    *,
    document: HtmlDocument | None = None,
) -> tuple[FakeHtmlFetcher, list[NetworkGuardHttpClient]]:
    fetcher = FakeHtmlFetcher(document or _synthetic_document())
    clients = _install_network_guard(monkeypatch)

    def create_fetcher(
        *,
        http_client: HttpClient,
        robots_policy: RobotsPolicy,
        identity: RequestIdentity,
    ) -> FakeHtmlFetcher:
        fetcher.wiring = (http_client, robots_policy, identity)
        return fetcher

    monkeypatch.setattr(runtime_module, "HtmlFetcher", create_fetcher)
    return fetcher, clients


def _install_recording_composer(monkeypatch: MonkeyPatch) -> RecordingParserComposer:
    composer = RecordingParserComposer()
    monkeypatch.setattr(runtime_module, "ParserComposer", lambda: composer)
    return composer


# --- 1/3/4. Real top-level boundary, real runtime graph, successful crawl ---


def test_cli_process_boundary_produces_json_and_success_exit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Drive the real aa_crawler.main() delegator through a fake acquisition leaf."""
    fetcher, clients = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)
    # Real bootstrap disables root propagation for the aa_crawler logger, so
    # caplog (root-attached) cannot observe records once it runs; attach a
    # handler directly to the source logger instead.
    capture_handler = _ListLogHandler()
    app_logger = logging.getLogger("aa_crawler.cli.app")
    app_logger.addHandler(capture_handler)
    app_logger.setLevel(logging.INFO)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["source"] == "cnn_indonesia"
    assert payload["headline"] == "Invented CLI process-boundary headline"
    assert fetcher.calls == [(_CNN_URL, None)]
    # Real bootstrap_application() prepared real runtime directories under tmp_path.
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / ".tmp").is_dir()
    # Real runtime cleanup occurred, and lifecycle logs never touched stdout.
    assert clients[0].close_count == 1
    messages = [record.getMessage() for record in capture_handler.records]
    assert "crawl started" in messages
    assert "crawl completed" in messages
    assert "crawl started" not in captured.out
    assert "crawl completed" not in captured.out


def test_cli_process_boundary_json_output_contains_all_expected_fields_only(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Every field of the current article contract appears, and nothing else."""
    node: dict[str, object] = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": _CNN_URL},
        "headline": "Invented full-field headline",
        "description": "Invented full-field description.",
        "author": [{"name": "Author One"}, {"name": "Author Two"}],
        "datePublished": "2099-01-01T08:30:00+07:00",
        "dateModified": "2099-01-01T09:15:00+07:00",
        "image": {"url": "https://images.example.test/invented.jpg"},
        "articleSection": "Synthetic Section",
        "inLanguage": "id-ID",
    }
    document = HtmlDocument(
        requested_url=_CNN_URL,
        final_url=_CNN_URL,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=_html_with_jsonld(node, canonical_href=_CNN_URL),
        encoding="utf-8",
    )
    _install_fake_acquisition(monkeypatch, document=document)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert exit_code == 0
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert isinstance(payload, dict)
    assert payload == {
        "source": "cnn_indonesia",
        "source_domain": "www.cnnindonesia.com",
        "requested_url": _CNN_URL,
        "canonical_url": _CNN_URL,
        "headline": "Invented full-field headline",
        "published_at": "2099-01-01T01:30:00+00:00",
        "description": "Invented full-field description.",
        "author_names": ["Author One", "Author Two"],
        "modified_at": "2099-01-01T02:15:00+00:00",
        "section": "Synthetic Section",
        "lead_image_url": "https://images.example.test/invented.jpg",
        "language": "id-ID",
    }


# --- 6. Requested vs canonical URL distinction ------------------------------


def test_cli_process_boundary_preserves_requested_and_canonical_url_distinctly(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    requested_url = f"{_CNN_URL}?utm_source=invented-test"
    node: dict[str, object] = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": _CNN_URL},
        "headline": "Invented requested/canonical headline",
        "datePublished": "2099-01-01T08:30:00+07:00",
    }
    document = HtmlDocument(
        requested_url=requested_url,
        final_url=_CNN_URL,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=_html_with_jsonld(node, canonical_href=_CNN_URL),
        encoding="utf-8",
    )
    _install_fake_acquisition(monkeypatch, document=document)
    monkeypatch.chdir(tmp_path)

    exit_code = main([requested_url])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["requested_url"] == requested_url
    assert payload["canonical_url"] == _CNN_URL
    assert "?" in payload["requested_url"]
    assert "?" not in payload["canonical_url"]


# --- 7/8. Disabled source and unknown/non-HTTPS source behavior ------------


def test_cli_process_boundary_rejects_disabled_source_before_acquisition(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A disabled production profile must fail before the fake fetcher is used.

    Kompas was enabled in Sprint 11 (a project-owner governance decision),
    so no current production profile is disabled; this test proves the same
    real-pipeline guarantee using one synthetic disabled profile injected
    alongside the real ones, exactly as `runtime_module.HttpClient` and
    similar collaborators are already substituted elsewhere in this module.
    """
    fetcher, clients = _install_fake_acquisition(monkeypatch)
    disabled_profile = SourceProfile(
        source="disabled_example",
        domains=("disabled.example.test",),
        enabled=False,
    )
    monkeypatch.setattr(
        runtime_module,
        "DEFAULT_SOURCE_PROFILES",
        (*runtime_module.DEFAULT_SOURCE_PROFILES, disabled_profile),
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["https://disabled.example.test/invented/article"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert fetcher.calls == []
    # The runtime was still created and closed even though the crawl never ran.
    assert clients[0].close_count == 1


@pytest.mark.parametrize(
    "url",
    [
        "https://totally-unknown-host.example.test/article",
        "http://www.cnnindonesia.com/invented/article",
    ],
    ids=["unknown_host", "non_https"],
)
def test_cli_process_boundary_rejects_unsupported_urls_before_acquisition(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
    url: str,
) -> None:
    fetcher, _clients = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main([url])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert fetcher.calls == []


# --- 9/10. Cross-profile boundary vs canonical ownership --------------------


def test_cli_process_boundary_cross_profile_final_url_maps_to_crawl_domain_exit_code(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A final URL resolving to a different registered profile must stop before
    parser composition, using real SourceRegistry/ArticleCrawlService behavior.
    """
    document = HtmlDocument(
        requested_url=_CNN_URL,
        final_url="https://www.kompas.com/invented/article",
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content="<html><head></head><body></body></html>",
        encoding="utf-8",
    )
    fetcher, clients = _install_fake_acquisition(monkeypatch, document=document)
    composer = _install_recording_composer(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    assert fetcher.calls == [(_CNN_URL, None)]
    assert composer.profiles == []
    assert clients[0].close_count == 1


def test_cli_process_boundary_foreign_canonical_is_crawl_failure_not_boundary(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A same-profile transport URL with a foreign JSON-LD canonical must fail
    during real parser composition/execution, not the pre-parser source gate.
    """
    node: dict[str, object] = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": _FOREIGN_URL},
        "headline": "Should not surface",
        "datePublished": "2099-01-01T08:30:00+07:00",
    }
    document = HtmlDocument(
        requested_url=_CNN_URL,
        final_url=_CNN_URL,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=_html_with_jsonld(node, canonical_href=_FOREIGN_URL),
        encoding="utf-8",
    )
    _install_fake_acquisition(monkeypatch, document=document)
    composer = _install_recording_composer(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    # Parser composition DID occur (unlike the cross-profile case above) —
    # proving the failure happened during/after parsing, not before it.
    assert composer.profiles == [CNN_INDONESIA_PROFILE]


# --- 11. Robots denial -------------------------------------------------------


def test_cli_process_boundary_robots_denial_maps_to_crawl_domain_exit_code(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """The real HtmlFetcher, wired to a denying RobotsPolicy, must reject
    acquisition before any transport attempt.
    """
    clients = _install_network_guard(monkeypatch)

    def create_robots_policy(
        *,
        http_client: HttpClient,
        identity: RequestIdentity,
    ) -> DenyingRobotsPolicy:
        return DenyingRobotsPolicy(http_client=http_client, identity=identity)

    monkeypatch.setattr(runtime_module, "RobotsPolicy", create_robots_policy)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    assert exit_code == 3
    assert captured.out == ""
    assert clients[0].send_count == 0
    assert clients[0].close_count == 1


# --- 12. Configuration/bootstrap failure -------------------------------------


def test_cli_process_boundary_unknown_env_variable_maps_to_startup_exit_code(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A real, safe, deterministic bootstrap failure (unknown AA_ variable)."""

    def fail_if_runtime_created() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(
        cli_app_module,
        "create_application_runtime",
        fail_if_runtime_created,
    )
    monkeypatch.setenv("AA_NOT_A_REAL_SETTING", "unexpected")
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    assert exit_code == 4
    assert captured.out == ""


# --- 13/14. Runtime-construction failure and unexpected crawl failure -------


def test_cli_process_boundary_runtime_construction_failure_closes_real_client(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A downstream construction failure must close the already-real client."""
    clients = _install_network_guard(monkeypatch)
    error = RuntimeError("injected downstream construction failure")

    def fail_fetcher(
        *,
        http_client: HttpClient,
        robots_policy: RobotsPolicy,
        identity: RequestIdentity,
    ) -> FakeHtmlFetcher:
        _ = (http_client, robots_policy, identity)
        raise error

    monkeypatch.setattr(runtime_module, "HtmlFetcher", fail_fetcher)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert clients[0].close_count == 1


def test_cli_process_boundary_unexpected_crawl_failure_maps_to_fallback_exit_code(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A bare exception raised during acquisition must close the real client."""
    clients = _install_network_guard(monkeypatch)
    error = RuntimeError("injected unexpected crawl failure")

    class RaisingHtmlFetcher:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def fetch(
            self,
            *,
            url: str,
            metadata: Mapping[str, object] | None = None,
        ) -> HtmlDocument:
            self.calls.append(url)
            _ = metadata
            raise error

    def create_fetcher(
        *,
        http_client: HttpClient,
        robots_policy: RobotsPolicy,
        identity: RequestIdentity,
    ) -> RaisingHtmlFetcher:
        _ = (http_client, robots_policy, identity)
        return RaisingHtmlFetcher()

    monkeypatch.setattr(runtime_module, "HtmlFetcher", create_fetcher)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert clients[0].close_count == 1


# --- 15. Correlation context isolation across invocations -------------------


def test_cli_process_boundary_correlation_context_does_not_leak_across_invocations(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    fetcher, _clients = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)

    assert get_correlation_id() is None
    first_exit = main([_CNN_URL])
    assert get_correlation_id() is None
    second_exit = main([_CNN_URL])
    assert get_correlation_id() is None

    capsys.readouterr()
    assert first_exit == 0
    assert second_exit == 0
    assert fetcher.calls == [(_CNN_URL, None), (_CNN_URL, None)]


# --- 16. CLI-triggered persistence (ADR-027) --------------------------------


def test_cli_process_boundary_output_flag_persists_the_real_result(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """--output must durably write the exact item the real pipeline produced."""
    _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "results.jsonl"

    exit_code = main([_CNN_URL, "--output", str(destination)])

    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    assert exit_code == 0
    assert stdout_payload["source"] == "cnn_indonesia"
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == stdout_payload


def test_cli_process_boundary_default_invocation_writes_no_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Omitting --output must leave the working directory untouched by writes
    beyond bootstrap's own runtime directories.
    """
    _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    capsys.readouterr()
    assert exit_code == 0
    written_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert written_files == []


def test_cli_process_boundary_persistence_failure_still_prints_real_stdout(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A destination whose parent does not exist must fail only persistence,
    never the already-completed crawl.
    """
    _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "missing-directory" / "results.jsonl"

    exit_code = main([_CNN_URL, "--output", str(destination)])

    captured = capsys.readouterr()
    assert exit_code == cli_app_module.EXIT_PERSISTENCE_FAILURE
    payload = json.loads(captured.out)
    assert payload["source"] == "cnn_indonesia"
    assert not destination.exists()


# --- 17. CLI scheduled crawl mode (ADR-028) ----------------------------------


def test_cli_process_boundary_scheduled_mode_produces_json_and_success_exit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Drive the real pipeline through scheduled mode via --interval.

    ``--max-runs 1`` bounds this to exactly one iteration so the loop
    returns before ever calling ``sleep`` (ADR-028 breaks before the wait
    once the bound is reached), keeping this test fully deterministic and
    free of any real wall-clock wait. Repeated-iteration mechanics
    themselves (interval waiting, --max-runs > 1, the recoverable-vs-
    terminal failure policy) are proven in depth against a fake sleep in
    ``tests/cli/test_scheduler.py``; this test proves only that scheduled
    mode reaches the same real bootstrap, runtime, registry, and parser
    composition as single-shot mode does.
    """
    fetcher, clients = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL, "--interval", "300", "--max-runs", "1"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert exit_code == 0
    assert payload["source"] == "cnn_indonesia"
    assert fetcher.calls == [(_CNN_URL, None)]
    assert clients[0].close_count == 1


def test_cli_process_boundary_scheduled_mode_output_persists_the_real_result(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Scheduled mode reuses the same --output persistence path as ADR-027."""
    _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "results.jsonl"

    exit_code = main(
        [
            _CNN_URL,
            "--interval",
            "300",
            "--max-runs",
            "1",
            "--output",
            str(destination),
        ]
    )

    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out.strip())
    assert exit_code == 0
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == stdout_payload


# --- 18. CLI batch/multi-URL input (ADR-029) ---------------------------------


def test_cli_process_boundary_batch_mode_crawls_every_url_and_exits_success(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Drive the real pipeline through --urls-file batch mode.

    Both URLs share the fake acquisition leaf's one synthetic document, so
    this proves the real wiring (registry, runtime, parser composition) is
    reached once per URL — the same real components single-shot mode
    reaches — not that each URL produces distinct content.
    """
    fetcher, clients = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)
    second_url = (
        "https://www.cnnindonesia.com/nasional/20990101010101-20-9999998/"
        "invented-second-batch-story"
    )
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(f"{_CNN_URL}\n{second_url}\n", encoding="utf-8")

    exit_code = main(["--urls-file", str(urls_file)])

    captured = capsys.readouterr()
    lines = captured.out.strip().splitlines()
    assert exit_code == 0
    assert len(lines) == 2
    assert all(json.loads(line)["source"] == "cnn_indonesia" for line in lines)
    assert [call[0] for call in fetcher.calls] == [_CNN_URL, second_url]
    assert clients[0].close_count == 1


def test_cli_process_boundary_scheduled_batch_mode_produces_json_and_success_exit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Drive the real pipeline through scheduled --urls-file batch mode.

    ``--max-runs 1`` bounds this to exactly one pass so the loop returns
    before ever calling ``sleep``, keeping this test fully deterministic
    and free of any real wall-clock wait — mirroring the single-URL
    scheduled-mode integration test's precedent.
    """
    fetcher, clients = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(f"{_CNN_URL}\n", encoding="utf-8")

    exit_code = main(
        ["--urls-file", str(urls_file), "--interval", "300", "--max-runs", "1"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())
    assert exit_code == 0
    assert payload["source"] == "cnn_indonesia"
    assert fetcher.calls == [(_CNN_URL, None)]
    assert clients[0].close_count == 1
