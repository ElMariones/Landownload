from contextlib import contextmanager
from urllib.parse import urljoin

import httpx

from .security import validate_url


@contextmanager
def public_stream(url):
    # Redirects must pass the same public-address check as the original URL.
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        for _ in range(6):
            validate_url(url)
            with client.stream('GET', url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                response.raise_for_status()
                yield response
                return
        raise ValueError('Too many redirects.')
