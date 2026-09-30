import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeURL(ValueError):
    pass


def validate_url(value: str) -> str:
    value = value.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise UnsafeURL('Use a public http or https link without embedded credentials.')
        if parsed.port not in (None, 80, 443):
            raise UnsafeURL('Only standard web ports are supported.')
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise UnsafeURL('Local and private network links are not supported.')
    except (ValueError, OSError) as exc:
        if isinstance(exc, UnsafeURL):
            raise
        raise UnsafeURL('This link has an invalid or unreachable hostname.') from exc
    return value


def friendly_error(raw: str) -> str:
    text = raw.lower()
    if any(s in text for s in ('sign in', 'login', 'cookies', 'private', 'authenticated', '401', '403', 'bot')):
        return 'The site requires a signed-in session or blocked this request. Configure your own cookies (see the setup guide), then try again.'
    if '429' in text or 'rate limit' in text:
        return 'The source is rate limiting requests. Wait a little before trying again.'
    if 'ffmpeg' in text:
        return 'FFmpeg is needed for this format. Install it and restart Landownload.'
    if 'drm' in text:
        return 'This media is protected by DRM and cannot be downloaded.'
    if 'timed out' in text or 'timeout' in text:
        return 'The source took too long to respond. Try again in a moment.'
    return 'Could not retrieve this media. The post may be unavailable, unsupported, or restricted. Try updating the download engines (see the setup guide).'
