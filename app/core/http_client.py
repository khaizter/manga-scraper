import logging
import ssl
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiohttp

from app.core.proxy import resolve_proxy_url
from app.core.proxy_ca import resolve_proxy_ca_cert_path

logger = logging.getLogger(__name__)


def resolve_http_proxy() -> str | None:
    return resolve_proxy_url()


def _proxy_ssl_context() -> ssl.SSLContext | None:
    cert_path = resolve_proxy_ca_cert_path()
    if cert_path is None:
        logger.warning(
            'CHROME_PROXY_URL is set but no proxy CA cert found for aiohttp; '
            'HTTPS requests through the proxy may fail SSL verification'
        )
        return None

    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=str(cert_path))
    return ctx


def _session_connector() -> aiohttp.TCPConnector | None:
    if not resolve_http_proxy():
        return None

    ssl_context = _proxy_ssl_context()
    if ssl_context is None:
        return aiohttp.TCPConnector(ssl=False)
    return aiohttp.TCPConnector(ssl=ssl_context)


@asynccontextmanager
async def http_session(headers: dict[str, str] | None = None) -> AsyncIterator[aiohttp.ClientSession]:
    connector = _session_connector()
    session_kwargs: dict = {'headers': headers or {}}
    if connector is not None:
        session_kwargs['connector'] = connector

    async with aiohttp.ClientSession(**session_kwargs) as session:
        yield session
