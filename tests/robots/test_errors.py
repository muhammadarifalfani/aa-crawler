from aa_crawler.crawler import CrawlerError
from aa_crawler.robots import RobotsError


def test_robots_error_inherits_crawler_error() -> None:
    error = RobotsError("robots failure")

    assert isinstance(error, CrawlerError)
    assert str(error) == "robots failure"
