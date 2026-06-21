import base64
import hashlib
import logging
import os
from pathlib import Path

from pydoll.browser.options import ChromiumOptions

logger = logging.getLogger(__name__)


def resolve_proxy_ca_cert_path() -> Path | None:
    explicit = os.getenv('CHROME_PROXY_CA_CERT', '').strip().strip('"').strip("'")
    if explicit:
        explicit_path = Path(explicit)
        if explicit_path.is_file():
            return explicit_path
        logger.warning('CHROME_PROXY_CA_CERT not found at %s; trying auto-discovery', explicit_path)

    for candidate in _brightdata_cert_candidates():
        if candidate.is_file():
            return candidate

    return None


def _brightdata_cert_candidates() -> tuple[Path, ...]:
    dirs = (Path('credentials/brightdata'), Path('/app/credentials/brightdata'))
    candidates: list[Path] = []

    for directory in dirs:
        if not directory.is_dir():
            continue
        for name in (
            'BrightData SSL certificate (port 33335).crt',
            'CA.crt',
            'ca.crt',
        ):
            candidates.append(directory / name)
        candidates.extend(sorted(directory.glob('*.crt')))

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return tuple(unique)


def configure_chrome_proxy_ssl(options: ChromiumOptions) -> None:
    """
    Load Bright Data CA from file into Chrome (like curl --cacert).

    Chrome has no --cacert flag. We read the .crt file, derive its SPKI
    fingerprint, and pass --ignore-certificate-errors-spki-list so only this
    CA is trusted. Nothing is installed to the OS certificate store.
    """
    if not os.getenv('CHROME_PROXY_URL', '').strip():
        return

    cert_path = resolve_proxy_ca_cert_path()
    if cert_path is None or not cert_path.is_file():
        logger.warning(
            'CHROME_PROXY_URL is set but no Bright Data SSL certificate was found. '
            'Place the port 33335 .crt in credentials/brightdata/ or set CHROME_PROXY_CA_CERT '
            '(https://docs.brightdata.com/general/account/ssl-certificate).'
        )
        return

    spki_hash = _cert_spki_sha256_base64(cert_path)
    if not spki_hash:
        logger.error('Could not load proxy CA certificate from %s', cert_path)
        return

    options.add_argument(f'--ignore-certificate-errors-spki-list={spki_hash}')
    logger.info('Loaded Bright Data proxy CA from %s', cert_path)


def _cert_spki_sha256_base64(cert_path: Path) -> str | None:
    try:
        spki_der = _subject_public_key_info_der(cert_path)
    except ValueError as exc:
        logger.error('Failed to parse proxy CA certificate %s: %s', cert_path, exc)
        return None

    return base64.b64encode(hashlib.sha256(spki_der).digest()).decode('ascii')


def _subject_public_key_info_der(cert_path: Path) -> bytes:
    pem = cert_path.read_bytes()
    lines = [line for line in pem.decode().splitlines() if line and not line.startswith('-----')]
    cert_der = base64.b64decode(''.join(lines))

    _, cert_body, _ = _read_tlv(cert_der, 0)
    cert_parts = _sequence_children(cert_body)
    if not cert_parts:
        raise ValueError('certificate is empty')

    _, tbs_body, _ = _read_tlv(cert_parts[0], 0)
    tbs_parts = _sequence_children(tbs_body)
    if not tbs_parts:
        raise ValueError('TBSCertificate is empty')

    spki_index = 6 if tbs_parts[0][0] == 0xA0 else 5
    if spki_index >= len(tbs_parts):
        raise ValueError('SubjectPublicKeyInfo not found in certificate')

    return tbs_parts[spki_index]


def _read_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset

    num_octets = first & 0x7F
    length = int.from_bytes(data[offset:offset + num_octets], 'big')
    return length, offset + num_octets


def _read_tlv(data: bytes, offset: int) -> tuple[bytes, bytes, int]:
    tag = data[offset:offset + 1]
    offset += 1
    length, offset = _read_length(data, offset)
    value = data[offset:offset + length]
    return tag, value, offset + length


def _sequence_children(sequence_value: bytes) -> list[bytes]:
    children: list[bytes] = []
    offset = 0
    while offset < len(sequence_value):
        start = offset
        _, _, offset = _read_tlv(sequence_value, offset)
        children.append(sequence_value[start:offset])
    return children
