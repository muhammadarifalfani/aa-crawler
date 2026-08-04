"""Public synchronous HTTP client API for AA Crawler."""

from aa_crawler.http.client import HttpClient
from aa_crawler.http.policies import RetryPolicy, TimeoutPolicy

__all__ = ["HttpClient", "RetryPolicy", "TimeoutPolicy"]
