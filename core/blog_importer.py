"""Hardened, synchronous WordPress and public sitemap importer.

This module intentionally has no public view.  It is called by the superuser-only
admin page and stores an item-level audit trail for every attempt.
"""

from __future__ import annotations

import datetime as dt
import html
import http.client
import ipaddress
import json
import re
import socket
import warnings
from io import BytesIO
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from .models import BlogImportItem, BlogImportRun, BlogPost

try:
    from defusedxml import ElementTree as SafeET
except ImportError:  # pragma: no cover - requirements install defusedxml
    SafeET = None

try:
    import bleach
except ImportError:  # pragma: no cover - requirements install bleach
    bleach = None


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_ITEMS = 500
MAX_SITEMAPS = 20
MAX_REDIRECTS = 5
NETWORK_TIMEOUT = 10
IMAGE_MAX_BYTES = 8 * 1024 * 1024
IMAGE_TIMEOUT = 10
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
ALLOWED_HTML_TAGS = {
    "a", "abbr", "blockquote", "br", "code", "em", "h2", "h3", "h4",
    "hr", "i", "img", "li", "ol", "p", "pre", "strong", "ul",
}
ALLOWED_HTML_ATTRS = {
    "a": {"href", "title", "rel"},
    "img": {"src", "alt", "title", "width", "height"},
}


class ImportErrorMessage(Exception):
    """A safe, user-facing importer validation/network error."""

    def __init__(self, message, bytes_read=0):
        super().__init__(message)
        self.bytes_read = bytes_read


def _local_name(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _text(node):
    return "".join(node.itertext()).strip() if node is not None else ""


def _child(node, name):
    return next((child for child in node if _local_name(child.tag) == name), None)


def _children(node, name):
    return [child for child in node if _local_name(child.tag) == name]


def _parse_datetime(value):
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt.timezone.utc)
    return parsed


def _safe_html(value):
    if not value:
        return ""
    value = re.sub(
        r"(?is)<(script|style|iframe|object|embed|form)\b[^>]*>.*?</\1\s*>",
        "",
        value,
    )
    if bleach is not None:
        return bleach.clean(
            value,
            tags=ALLOWED_HTML_TAGS,
            attributes=ALLOWED_HTML_ATTRS,
            protocols=["http", "https", "mailto"],
            strip=True,
        )
    # The dependency is required in production; this conservative fallback keeps
    # an accidental incomplete environment from persisting executable markup.
    value = re.sub(r"(?is)<(script|style|iframe|object|embed|form)\b.*?</\1\s*>", "", value)
    return re.sub(r"(?is)<[^>]+>", lambda match: match.group(0)
                  if re.match(r"(?is)^</?(?:p|br|h[2-4]|ul|ol|li|strong|em|a|img)\b", match.group(0))
                  else "", value)


def _public_ips(hostname):
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    except (OSError, socket.gaierror):
        raise ImportErrorMessage("The source hostname could not be resolved.")
    if not addresses:
        raise ImportErrorMessage("The source hostname has no usable address.")
    public = set()
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise ImportErrorMessage("The source hostname resolved to an invalid address.")
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified
        ):
            raise ImportErrorMessage("Private, reserved, or link-local source addresses are not allowed.")
        public.add(address)
    return public


# Kept as a seam for tests and deployments with a controlled resolver.
_public_ip = _public_ips


def validate_source_url(value, origin=None):
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ImportErrorMessage("Enter a valid public HTTP(S) URL.")
    if (
        parsed.scheme not in {"http", "https"} or not hostname
        or parsed.username or parsed.password or parsed.fragment
        or port not in {None, 80, 443}
    ):
        raise ImportErrorMessage("Only public HTTP(S) URLs without credentials are allowed.")
    if origin and (parsed.scheme, hostname.casefold(), port or (443 if parsed.scheme == "https" else 80)) != origin:
        raise ImportErrorMessage("Crawled URLs must remain on the original site origin.")
    _public_ip(hostname)
    return parsed


def _read_response(response, limit):
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > limit:
        raise ImportErrorMessage("The remote response exceeds the configured size limit.")
    chunks = []
    size = 0
    while True:
        chunk = response.read(min(64 * 1024, limit - size + 1))
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise ImportErrorMessage(
                "The remote response exceeds the configured size limit.",
                bytes_read=size,
            )
        chunks.append(chunk)
    return b"".join(chunks)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout):
        super().__init__(host, port=port, timeout=timeout)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port, address, timeout):
        super().__init__(host, port=port, timeout=timeout)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


def _open_validated_response(parsed, addresses, timeout, headers):
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    address = sorted(addresses)[0]
    connection_class = (
        _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
    )
    connection = connection_class(parsed.hostname, port, address, timeout)
    target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connection.request("GET", target, headers=headers)
    return connection, connection.getresponse()


def fetch_url(
    url, *, origin=None, max_bytes=MAX_RESPONSE_BYTES, image=False,
    remaining_bytes=None, return_bytes=False,
):
    limit = min(
        IMAGE_MAX_BYTES if image else max_bytes,
        remaining_bytes if remaining_bytes is not None else MAX_TOTAL_BYTES,
    )
    if limit <= 0:
        raise ImportErrorMessage("The total network response limit was exhausted.")
    current = url
    downloaded_total = 0
    for _ in range(MAX_REDIRECTS + 1):
        parsed = validate_source_url(current, origin=origin)
        addresses = _public_ip(parsed.hostname)
        connection = None
        try:
            connection, response = _open_validated_response(
                parsed,
                addresses,
                IMAGE_TIMEOUT if image else NETWORK_TIMEOUT,
                {"User-Agent": "Django WordPress importer/1.0", "Accept": "*/*"},
            )
            with response:
                status = getattr(response, "status", getattr(response, "code", 200))
                if status in {301, 302, 303, 307, 308}:
                    try:
                        redirect_body = _read_response(response, limit - downloaded_total)
                    except ImportErrorMessage as exc:
                        exc.bytes_read += downloaded_total
                        raise
                    downloaded_total += len(redirect_body)
                    location = response.headers.get("Location")
                    if not location:
                        raise ImportErrorMessage("The remote server returned an invalid redirect.")
                    current = urljoin(current, location)
                    continue
                try:
                    data = _read_response(response, limit - downloaded_total)
                except ImportErrorMessage as exc:
                    exc.bytes_read += downloaded_total
                    raise
                downloaded_total += len(data)
                result = (
                    data,
                    response.headers.get("Content-Type", "").split(";", 1)[0].lower(),
                    current,
                )
                return (*result, downloaded_total) if return_bytes else result
        except ImportErrorMessage:
            raise
        except (OSError, ValueError) as exc:
            raise ImportErrorMessage(f"Could not fetch the source URL: {exc}") from exc
        finally:
            if connection is not None:
                connection.close()
    raise ImportErrorMessage("The source URL exceeded the redirect limit.")


def _parse_xml(payload):
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ImportErrorMessage("The XML document exceeds the configured size limit.")
    if b"\x00" in payload or re.search(rb"<!\s*(DOCTYPE|ENTITY)\b", payload, re.I):
        raise ImportErrorMessage("DTD and entity declarations are not allowed.")
    try:
        if SafeET is not None:
            return SafeET.fromstring(payload)
        from xml.etree import ElementTree
        return ElementTree.fromstring(payload)
    except Exception as exc:
        raise ImportErrorMessage("The XML document is invalid or unsafe.") from exc


def _meta_map(parser):
    values = {}
    for key, value in parser.meta:
        values.setdefault(key.casefold(), value.strip())
    return values


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.meta = []
        self.canonical = ""
        self.author = ""
        self.images = []
        self.article = []
        self.body = []
        self.schema = []
        self._title_depth = 0
        self._article_depth = 0
        self._main_depth = 0
        self._script_type = ""
        self._script_data = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.casefold()
        if tag == "title":
            self._title_depth = 1
        if tag in {"article", "main"}:
            if tag == "article":
                self._article_depth += 1
            else:
                self._main_depth += 1
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property") or ""
            value = attrs.get("content", "")
            if key and value:
                self.meta.append((key, value))
                if key.casefold() in {"author", "article:author"}:
                    self.author = value
        if tag == "link" and attrs.get("rel", "").casefold() == "canonical":
            self.canonical = attrs.get("href", "")
        if tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
        if tag == "script":
            self._script_type = attrs.get("type", "").casefold()
            self._script_data = []
        serialized = "<" + tag
        for key, value in attrs.items():
            if value is not None:
                serialized += f' {key}="{html.escape(value, quote=True)}"'
        serialized += ">"
        self._append(serialized)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag == "title":
            self._title_depth = 0
        if tag == "article":
            self._article_depth = max(0, self._article_depth - 1)
        if tag == "main":
            self._main_depth = max(0, self._main_depth - 1)
        if tag == "script" and self._script_type == "application/ld+json":
            self.schema.append("".join(self._script_data))
        self._append(f"</{tag}>")

    def handle_data(self, data):
        if self._title_depth:
            self.title.append(data)
        if self._script_type == "application/ld+json":
            self._script_data.append(data)
        self._append(html.escape(data))

    def handle_entityref(self, name):
        self.handle_data(html.unescape(f"&{name};"))

    def handle_charref(self, name):
        self.handle_data(html.unescape(f"&#{name};"))

    def _append(self, value):
        self.body.append(value)
        if self._article_depth or self._main_depth:
            self.article.append(value)


def _schema_images(values):
    found = []
    for raw in values:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            continue
        objects = parsed if isinstance(parsed, list) else [parsed]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            kind = obj.get("@type", "")
            kinds = kind if isinstance(kind, list) else [kind]
            if any(str(item).casefold() in {"article", "blogposting", "newsarticle"} for item in kinds):
                image = obj.get("image")
                if isinstance(image, str):
                    found.append(image)
                elif isinstance(image, dict) and image.get("url"):
                    found.append(image["url"])
                elif isinstance(image, list):
                    found.extend(item if isinstance(item, str) else item.get("url", "")
                                 for item in image)
    return [item for item in found if item]


def extract_page(payload, source_url):
    parser = _PageParser()
    try:
        parser.feed(payload.decode("utf-8", errors="replace"))
    except Exception as exc:
        raise ImportErrorMessage("The page HTML could not be parsed.") from exc
    meta = _meta_map(parser)
    title = meta.get("og:title") or "".join(parser.title).strip()
    description = meta.get("description") or meta.get("og:description", "")
    images = (
        [meta[key] for key in ("og:image", "twitter:image") if meta.get(key)]
        + _schema_images(parser.schema)
        + parser.images
    )
    body = _safe_html("".join(parser.article) or "".join(parser.body))
    return {
        "title": html.unescape(title).strip()[:240],
        "summary": html.unescape(description).strip()[:500],
        "meta_description": html.unescape(description).strip()[:300],
        "body": body,
        "canonical_url": urljoin(source_url, parser.canonical) if parser.canonical else source_url,
        "source_url": source_url,
        "author_name": parser.author[:255],
        "image_urls": [urljoin(source_url, item) for item in images if item],
        "slug": slugify(urlsplit(source_url).path.rstrip("/").split("/")[-1])[:240],
    }


def _wxr_items(root):
    channel = next((child for child in root if _local_name(child.tag) == "channel"), root)
    return [child for child in channel if _local_name(child.tag) == "item"]


def parse_wxr(payload):
    root = _parse_xml(payload)
    attachments = {}
    items = []
    raw_items = _wxr_items(root)
    # WordPress may place attachment items after their parent post.
    for item in raw_items:
        post_type = _text(next((c for c in item if _local_name(c.tag) == "post_type"), None))
        post_id = _text(next((c for c in item if _local_name(c.tag) == "post_id"), None))
        attachment_url = _text(next((c for c in item if _local_name(c.tag) == "attachment_url"), None))
        if post_type == "attachment" and post_id and attachment_url:
            attachments[post_id] = attachment_url
    for item in raw_items:
        post_type = _text(next((c for c in item if _local_name(c.tag) == "post_type"), None))
        post_id = _text(next((c for c in item if _local_name(c.tag) == "post_id"), None))
        attachment_url = _text(next((c for c in item if _local_name(c.tag) == "attachment_url"), None))
        if post_type == "attachment":
            continue
        if post_type and post_type != "post":
            continue
        def value(name):
            return _text(next((c for c in item if _local_name(c.tag) == name), None))
        meta = {}
        for child in item:
            if _local_name(child.tag) == "postmeta":
                key = value_from_child(child, "meta_key")
                meta[key] = value_from_child(child, "meta_value")
        guid_node = next((c for c in item if _local_name(c.tag) == "guid"), None)
        source_url = value("link")
        guid = _text(guid_node)
        body = value("encoded")
        excerpt = value("encoded")  # overwritten below when namespaced duplicates exist
        encoded = [c for c in item if _local_name(c.tag) == "encoded"]
        if len(encoded) > 1:
            body, excerpt = _text(encoded[0]), _text(encoded[1])
        items.append({
            "title": value("title")[:240],
            "slug": slugify(value("post_name"))[:240],
            "body": _safe_html(body),
            "summary": _safe_html(excerpt)[:500],
            "meta_description": _safe_html(excerpt)[:300],
            "source_url": source_url,
            "canonical_url": source_url,
            "source_guid": guid,
            "author_name": value("creator")[:255],
            "original_published_at": _parse_datetime(value("post_date_gmt") or value("pubDate")),
            "original_modified_at": _parse_datetime(value("post_modified_gmt")),
            "image_urls": [attachments.get(meta.get("_thumbnail_id", ""))] if meta.get("_thumbnail_id") in attachments else [],
        })
    return items


def value_from_child(node, name):
    return _text(next((child for child in node if _local_name(child.tag) == name), None))


def _origin(parsed):
    return (parsed.scheme, parsed.hostname.casefold(), parsed.port or (443 if parsed.scheme == "https" else 80))


def sitemap_urls(source_url, total_budget):
    parsed = validate_source_url(source_url)
    origin = _origin(parsed)
    queue = [source_url]
    pages = []
    seen = set()
    used = 0
    while queue and len(seen) < MAX_SITEMAPS:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        try:
            payload, _content_type, _final, downloaded = fetch_url(
                current,
                origin=origin,
                remaining_bytes=total_budget - used,
                return_bytes=True,
            )
        except ImportErrorMessage as exc:
            used += exc.bytes_read
            raise
        used += downloaded
        if used > total_budget:
            raise ImportErrorMessage(
                "The total network response limit was exceeded.", bytes_read=used
            )
        root = _parse_xml(payload)
        root_name = _local_name(root.tag)
        if root_name == "sitemapindex":
            for entry in root:
                loc = _text(_child(entry, "loc"))
                if loc:
                    candidate = urljoin(current, loc)
                    validate_source_url(candidate, origin=origin)
                    queue.append(candidate)
        elif root_name == "urlset":
            for entry in root:
                loc = _text(_child(entry, "loc"))
                if loc:
                    candidate = urljoin(current, loc)
                    validate_source_url(candidate, origin=origin)
                    pages.append(candidate)
                    if len(pages) >= MAX_ITEMS:
                        return pages, origin, used
        else:
            raise ImportErrorMessage("The source is not a supported sitemap.")
    return pages, origin, used


def _verified_image_extension(content_type, data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image.verify()
                image_format = image.format
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise ImportErrorMessage("The featured image exceeds the pixel limit.")
                image.load()
                verified_format = image.format
    except (ImportErrorMessage, Image.DecompressionBombError, Image.DecompressionBombWarning,
            UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, ImportErrorMessage):
            raise
        raise ImportErrorMessage("The featured image is not a valid safe image.") from exc
    if image_format != verified_format:
        raise ImportErrorMessage("The featured image format could not be verified.")
    formats = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"),
               "GIF": ("image/gif", ".gif"), "WEBP": ("image/webp", ".webp")}
    expected = formats.get(verified_format)
    if not expected or content_type != expected[0]:
        raise ImportErrorMessage("The featured image content type does not match its format.")
    return expected[1]


def download_image(url, origin, used_bytes):
    validate_source_url(url, origin=origin)
    try:
        data, content_type, _final, downloaded = fetch_url(
            url,
            origin=origin,
            max_bytes=IMAGE_MAX_BYTES,
            image=True,
            remaining_bytes=MAX_TOTAL_BYTES - used_bytes,
            return_bytes=True,
        )
    except ImportErrorMessage as exc:
        exc.bytes_read = max(exc.bytes_read, 0)
        raise
    if used_bytes + len(data) > MAX_TOTAL_BYTES:
        raise ImportErrorMessage("The total network response limit was exceeded.", downloaded)
    try:
        extension = _verified_image_extension(content_type, data)
    except ImportErrorMessage as exc:
        exc.bytes_read = max(exc.bytes_read, downloaded)
        raise
    if not extension:
        raise ImportErrorMessage("The featured image is not a verified allowed image type.", downloaded)
    return data, extension, used_bytes + downloaded


def _save_image(post, source_url, origin, used_bytes):
    data, extension, used_bytes = download_image(source_url, origin, used_bytes)
    name = default_storage.get_available_name(f"blog-posts/import-{slugify(post.slug)[:180]}{extension}")
    post.featured_image.save(name, ContentFile(data), save=True)
    return used_bytes


def _duplicate(item):
    query = BlogPost.objects.all()
    if item.get("source_guid"):
        found = query.filter(source_guid=item["source_guid"]).first()
        if found:
            return found
    if item.get("source_url"):
        return query.filter(source_url=item["source_url"]).first()
    return None


def _unique_slug(value):
    base = slugify(value)[:230] or "imported-post"
    slug = base
    suffix = 2
    while BlogPost.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"[:240]
        suffix += 1
    return slug


def _record(run, item, status, post=None, error="", details=None):
    BlogImportItem.objects.create(
        run=run, source_url=item.get("source_url", "")[:1000],
        source_guid=item.get("source_guid", "")[:1000], title=item.get("title", "")[:240],
        status=status, blog_post=post, error_summary=error[:2000], details=details or {},
    )


def run_import(*, user, mode, payload=None, source_url="", uploaded_name=""):
    limits = {
        "max_upload_bytes": MAX_UPLOAD_BYTES, "max_response_bytes": MAX_RESPONSE_BYTES,
        "max_total_bytes": MAX_TOTAL_BYTES, "max_items": MAX_ITEMS,
    }
    run = BlogImportRun.objects.create(
        mode=mode, source_url=source_url[:1000], uploaded_name=uploaded_name[:255],
        limits=limits, created_by=user,
    )
    used_bytes = 0
    exhausted = False
    try:
        if mode == BlogImportRun.Mode.WXR:
            if not payload or len(payload) > MAX_UPLOAD_BYTES:
                raise ImportErrorMessage("The WXR upload exceeds the configured size limit.")
            items = parse_wxr(payload)
            origin = None
        elif mode == BlogImportRun.Mode.SITEMAP:
            items, origin, used_bytes = sitemap_urls(source_url, MAX_TOTAL_BYTES)
        else:
            raise ImportErrorMessage("Select a supported import mode.")
        for item in items[:MAX_ITEMS]:
            if isinstance(item, str):
                item = {"source_url": item}
            duplicate = _duplicate(item)
            if duplicate:
                run.duplicate_count += 1
                _record(run, item, BlogImportItem.Status.DUPLICATE, duplicate)
                continue
            try:
                if mode == BlogImportRun.Mode.WXR and not item.get("title"):
                    raise ImportErrorMessage("The item has no title.")
                if mode == BlogImportRun.Mode.SITEMAP:
                    page_bytes, _ctype, _final, downloaded = fetch_url(
                        item["source_url"],
                        origin=origin,
                        remaining_bytes=MAX_TOTAL_BYTES - used_bytes,
                        return_bytes=True,
                    )
                    used_bytes += downloaded
                    item = extract_page(page_bytes, item["source_url"])
                if not item.get("title"):
                    raise ImportErrorMessage("The item has no title.")
                item["slug"] = _unique_slug(item.get("slug") or item["title"])
                with transaction.atomic():
                    post = BlogPost.objects.create(
                        title=item["title"], slug=item["slug"], summary=item.get("summary", ""),
                        body=item.get("body", ""), meta_description=item.get("meta_description", ""),
                        canonical_url=item.get("canonical_url", ""), source_url=item.get("source_url", ""),
                        source_guid=item.get("source_guid", ""), author_name=item.get("author_name", ""),
                        original_published_at=item.get("original_published_at"),
                        original_modified_at=item.get("original_modified_at"), is_published=False,
                    )
                image_error = ""
                for image_url in item.get("image_urls", []):
                    if not image_url:
                        continue
                    try:
                        used_bytes = _save_image(post, image_url, origin, used_bytes)
                        if used_bytes >= MAX_TOTAL_BYTES:
                            exhausted = True
                        break
                    except ImportErrorMessage as exc:
                        used_bytes += exc.bytes_read
                        image_error = str(exc)
                        if used_bytes >= MAX_TOTAL_BYTES:
                            exhausted = True
                            break
                run.imported_count += 1
                _record(run, item, BlogImportItem.Status.IMPORTED, post, image_error,
                        {"featured_image_error": image_error} if image_error else {})
                if exhausted:
                    break
            except (ImportErrorMessage, IntegrityError) as exc:
                used_bytes += exc.bytes_read
                run.failed_count += 1
                _record(run, item, BlogImportItem.Status.FAILED, error=str(exc))
                if used_bytes >= MAX_TOTAL_BYTES:
                    exhausted = True
                    break
        run.status = BlogImportRun.Status.FAILED if exhausted else BlogImportRun.Status.COMPLETED
        if exhausted:
            run.error_summary = "The total network response limit was exhausted."
    except ImportErrorMessage as exc:
        run.status = BlogImportRun.Status.FAILED
        run.error_summary = str(exc)
    except Exception:
        run.status = BlogImportRun.Status.FAILED
        run.error_summary = "The import could not be completed safely."
    run.finished_at = timezone.now()
    run.save(update_fields=[
        "status", "error_summary", "imported_count", "duplicate_count", "failed_count",
        "finished_at", "updated_at",
    ])
    return run