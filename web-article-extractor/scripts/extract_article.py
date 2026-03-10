#!/usr/bin/env python3
"""Extract article body text and in-body images from a web page or HTML file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DROP_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "iframe",
    "svg",
    "canvas",
    "form",
    "button",
    "input",
    "video",
    "audio",
    "source",
)

DEFAULT_NOISE_SELECTORS = (
    "header",
    "footer",
    "nav",
    "aside",
    ".sidebar",
    ".share",
    ".share-bar",
    ".social",
    ".social-share",
    ".newsletter",
    ".comments",
    ".comment-list",
    ".related",
    ".related-posts",
    ".recommendation",
    ".advertisement",
    ".ads",
    ".promo",
    ".knwls-menu",
    ".article-comment-container",
)

CANDIDATE_SELECTORS = (
    "article",
    "main",
    "[role='main']",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".story-body",
    ".article-body",
    ".content",
    ".km-view-content",
    ".km-article-content",
    ".reader-container",
    ".article-main",
    "#article",
    "#content",
    "#main-content",
)

AUTH_URL_HINTS = (
    "passport.",
    "/signin",
    "/login",
    "_auth_login",
    "oauth=",
)

AUTH_TEXT_HINTS = (
    "登录",
    "账号密码",
    "快速登录",
    "sign in",
    "signin",
    "password",
)

X_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
X_RICH_TEXT_SELECTORS = (
    "[data-testid='twitterArticleRichTextView']",
    "[data-testid='longformRichTextComponent']",
    "[data-testid='tweetText']",
)

INVISIBLE_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def clean_invisible_chars(text: str) -> str:
    cleaned = (text or "").replace("\xa0", " ").replace("\u202f", " ")
    return INVISIBLE_CHARS_RE.sub("", cleaned)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", clean_invisible_chars(text)).strip()


def normalize_multiline(text: str) -> str:
    raw = clean_invisible_chars(text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in raw.split("\n")]
    merged = "\n".join(lines)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract article body text and in-body images from a webpage.",
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--url", help="Webpage URL to extract.")
    source_group.add_argument("--html-file", help="Local HTML file path.")

    parser.add_argument(
        "--base-url",
        help="Base URL used to resolve relative links when using --html-file.",
    )
    parser.add_argument(
        "--content-selector",
        help="CSS selector for the main article container.",
    )
    parser.add_argument(
        "--exclude-selector",
        action="append",
        default=[],
        help="CSS selector to remove from extraction scope (repeatable).",
    )
    parser.add_argument(
        "--exclude-selector-file",
        help="Text file with one selector per line.",
    )
    parser.add_argument(
        "--disable-default-noise-filter",
        action="store_true",
        help="Disable built-in removal of common non-content regions.",
    )

    parser.add_argument(
        "--render-js",
        action="store_true",
        help="Use Playwright to render JS before extraction (URL mode only).",
    )
    parser.add_argument(
        "--wait-until",
        choices=("domcontentloaded", "load", "networkidle"),
        default="domcontentloaded",
        help="Playwright page.goto wait mode.",
    )
    parser.add_argument(
        "--wait-selector",
        help="Playwright: wait for a selector before extraction.",
    )
    parser.add_argument(
        "--wait-ms",
        type=int,
        default=2500,
        help="Playwright: additional wait after page load in milliseconds.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Playwright in headed mode.",
    )
    parser.add_argument(
        "--manual-login",
        action="store_true",
        help="In Playwright mode, pause for manual login before extraction.",
    )
    parser.add_argument(
        "--playwright-channel",
        default="chrome",
        help="Playwright browser channel, e.g. chrome/chromium/msedge.",
    )
    parser.add_argument(
        "--playwright-user-data-dir",
        help="Playwright persistent user data dir (profile) path.",
    )
    parser.add_argument(
        "--storage-state",
        help="Playwright storage state JSON file to preload cookies/session.",
    )
    parser.add_argument(
        "--save-storage-state",
        help="Save Playwright storage state to this JSON file.",
    )
    parser.add_argument(
        "--ignore-https-errors",
        action="store_true",
        help="Ignore HTTPS certificate errors (Playwright mode).",
    )

    parser.add_argument(
        "--cookie",
        action="append",
        default=[],
        help="Cookie in name=value format (repeatable).",
    )
    parser.add_argument(
        "--cookie-file",
        help="Cookie file path. Supports JSON or name=value per line.",
    )
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        help="Custom request header in 'Key: Value' format (repeatable).",
    )

    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output files.",
    )
    parser.add_argument("--slug", help="Custom output filename prefix.")
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "both"),
        default="both",
        help="Output format.",
    )
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="Download extracted images into <slug>_images/.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="Maximum images to keep (0 means no limit).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def parse_header_items(raw_headers: list[str], warnings: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    for item in raw_headers:
        if ":" not in item:
            warnings.append(f"Invalid --header ignored (missing ':'): {item}")
            continue
        key, value = item.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            warnings.append(f"Invalid --header ignored (empty key): {item}")
            continue
        headers[key] = value
    return headers


def parse_cookie_kv(line: str) -> dict | None:
    if "=" not in line:
        return None
    name, value = line.split("=", 1)
    name = name.strip()
    value = value.strip()
    if not name:
        return None
    return {"name": name, "value": value}


def load_cookie_file(path: str, warnings: list[str]) -> list[dict]:
    cookie_path = Path(path).expanduser().resolve()
    if not cookie_path.exists():
        warnings.append(f"Cookie file not found: {cookie_path}")
        return []

    text = cookie_path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    cookies: list[dict] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            cookies.append({"name": str(key), "value": str(value)})
        return cookies

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("name") and item.get("value"):
                entry = {"name": str(item["name"]), "value": str(item["value"])}
                if item.get("domain"):
                    entry["domain"] = str(item["domain"])
                if item.get("path"):
                    entry["path"] = str(item["path"])
                cookies.append(entry)
            else:
                warnings.append(f"Invalid cookie entry ignored in JSON list: {item}")
        return cookies

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entry = parse_cookie_kv(line)
        if entry:
            cookies.append(entry)
        else:
            warnings.append(f"Invalid cookie line ignored: {line}")
    return cookies


def load_cookies(args: argparse.Namespace, warnings: list[str]) -> list[dict]:
    cookies: list[dict] = []
    for raw in args.cookie:
        entry = parse_cookie_kv(raw)
        if entry:
            cookies.append(entry)
        else:
            warnings.append(f"Invalid --cookie ignored: {raw}")

    if args.cookie_file:
        cookies.extend(load_cookie_file(args.cookie_file, warnings))

    deduped: list[dict] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for cookie in cookies:
        key = (
            cookie["name"],
            cookie.get("domain"),
            cookie.get("path"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cookie)
    return deduped


def apply_cookies_to_session(session: requests.Session, cookies: list[dict]) -> None:
    for cookie in cookies:
        kwargs: dict = {}
        if cookie.get("domain"):
            kwargs["domain"] = cookie["domain"]
        if cookie.get("path"):
            kwargs["path"] = cookie["path"]
        session.cookies.set(cookie["name"], cookie["value"], **kwargs)


def load_html_via_requests(
    args: argparse.Namespace,
    headers: dict[str, str],
    cookies: list[dict],
) -> tuple[str, str, int, list[str]]:
    session = requests.Session()
    session.headers.update(headers)
    apply_cookies_to_session(session, cookies)

    response = session.get(args.url, timeout=args.timeout, allow_redirects=True)
    response.raise_for_status()
    if response.encoding is None:
        response.encoding = response.apparent_encoding

    history = [item.url for item in response.history]
    history.append(response.url)
    return response.text, response.url, response.status_code, history


def load_html_via_playwright(
    args: argparse.Namespace,
    headers: dict[str, str],
    cookies: list[dict],
    warnings: list[str],
) -> tuple[str, str, int, list[str]]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on runtime env
        raise RuntimeError(f"Playwright is not available: {exc}") from exc

    timeout_ms = max(args.timeout * 1000, 1000)

    with sync_playwright() as playwright:
        context = None
        browser = None
        page = None
        response = None

        context_kwargs = {
            "ignore_https_errors": bool(args.ignore_https_errors),
        }
        if headers.get("User-Agent"):
            context_kwargs["user_agent"] = headers["User-Agent"]

        if args.playwright_user_data_dir:
            user_data_dir = str(Path(args.playwright_user_data_dir).expanduser().resolve())
            if args.storage_state:
                warnings.append("Ignoring --storage-state because --playwright-user-data-dir is set.")
            launch_kwargs = {
                "headless": not args.headed,
                "channel": args.playwright_channel,
                "ignore_https_errors": bool(args.ignore_https_errors),
            }
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                **launch_kwargs,
            )
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = playwright.chromium.launch(
                headless=not args.headed,
                channel=args.playwright_channel,
            )
            if args.storage_state:
                context_kwargs["storage_state"] = str(Path(args.storage_state).expanduser().resolve())
            context = browser.new_context(**context_kwargs)
            page = context.new_page()

        if cookies:
            to_add: list[dict] = []
            for cookie in cookies:
                item = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "path": cookie.get("path", "/"),
                }
                if cookie.get("domain"):
                    item["domain"] = cookie["domain"]
                else:
                    item["url"] = args.url
                to_add.append(item)
            context.add_cookies(to_add)

        response = page.goto(args.url, wait_until=args.wait_until, timeout=timeout_ms)

        if args.manual_login:
            if not args.headed:
                warnings.append("--manual-login requires --headed. Ignoring manual pause.")
            elif not sys.stdin.isatty():
                warnings.append("Cannot pause for manual login because stdin is not interactive.")
            else:
                print("[ACTION] Complete login in the opened browser, then press Enter to continue...")
                input()

        if args.wait_selector:
            try:
                page.wait_for_selector(args.wait_selector, timeout=timeout_ms)
            except PlaywrightTimeoutError:
                warnings.append(f"wait selector timed out: {args.wait_selector}")

        if args.wait_ms > 0:
            page.wait_for_timeout(args.wait_ms)

        host = (urlparse(page.url).hostname or "").lower()
        if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
            stable_rounds = 0
            for _ in range(8):
                prev_height = page.evaluate("() => document.body ? document.body.scrollHeight : 0")
                page.evaluate("() => window.scrollTo(0, document.body ? document.body.scrollHeight : 0)")
                page.wait_for_timeout(700)
                curr_height = page.evaluate("() => document.body ? document.body.scrollHeight : 0")
                if curr_height <= prev_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                if stable_rounds >= 2:
                    break
            page.evaluate("() => window.scrollTo(0, 0)")

        if args.save_storage_state:
            state_path = Path(args.save_storage_state).expanduser().resolve()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(state_path))

        final_url = page.url
        html_text = page.content()
        status = response.status if response else 0

        history = [args.url]
        if final_url != args.url:
            history.append(final_url)

        context.close()
        if browser:
            browser.close()

        return html_text, final_url, status, history


def load_html(
    args: argparse.Namespace,
    headers: dict[str, str],
    cookies: list[dict],
    warnings: list[str],
) -> tuple[str, str, int, list[str]]:
    if args.url:
        if args.render_js:
            return load_html_via_playwright(args, headers, cookies, warnings)
        return load_html_via_requests(args, headers, cookies)

    html_path = Path(args.html_file).expanduser().resolve()
    html_text = html_path.read_text(encoding="utf-8")
    base_url = args.base_url or f"file://{html_path}"
    return html_text, base_url, 200, [base_url]


def load_selector_file(path: str | None) -> list[str]:
    if not path:
        return []
    selectors: list[str] = []
    selector_path = Path(path).expanduser().resolve()
    for raw_line in selector_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        selectors.append(line)
    return selectors


def remove_tags(soup: BeautifulSoup, tag_names: tuple[str, ...]) -> None:
    for name in tag_names:
        for node in soup.find_all(name):
            node.decompose()


def remove_by_selectors(root: Tag | BeautifulSoup, selectors: list[str], warnings: list[str]) -> None:
    for selector in selectors:
        try:
            matched = root.select(selector)
        except Exception as exc:  # pragma: no cover - selector parser varies by bs4 version
            warnings.append(f"Invalid selector ignored: {selector} ({exc})")
            continue
        for node in matched:
            node.decompose()


def get_node_text(node: Tag) -> str:
    return normalize_space(node.get_text(" ", strip=True))


def get_link_density(node: Tag) -> float:
    text = get_node_text(node)
    if not text:
        return 1.0
    link_text = normalize_space(" ".join(a.get_text(" ", strip=True) for a in node.find_all("a")))
    return len(link_text) / max(len(text), 1)


def candidate_score(node: Tag) -> float:
    text = get_node_text(node)
    text_len = len(text)
    paragraph_count = len(node.find_all("p"))
    image_count = len(node.find_all("img"))
    heading_count = len(node.find_all(re.compile(r"^h[1-6]$")))
    link_density = get_link_density(node)
    score = (
        float(text_len)
        + paragraph_count * 220.0
        + image_count * 80.0
        + heading_count * 50.0
        - link_density * text_len * 0.8
    )
    return score


def iter_candidates(soup: BeautifulSoup) -> list[Tag]:
    seen_ids: set[int] = set()
    candidates: list[Tag] = []
    for selector in CANDIDATE_SELECTORS:
        for node in soup.select(selector):
            node_id = id(node)
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            candidates.append(node)
    if soup.body:
        node_id = id(soup.body)
        if node_id not in seen_ids:
            candidates.append(soup.body)
    return candidates


def choose_content_root(
    soup: BeautifulSoup,
    content_selector: str | None,
    warnings: list[str],
) -> tuple[Tag, str]:
    if content_selector:
        try:
            explicit = soup.select_one(content_selector)
        except Exception as exc:  # pragma: no cover
            warnings.append(f"Invalid --content-selector ignored: {content_selector} ({exc})")
        else:
            if explicit:
                return explicit, content_selector
            warnings.append(f"--content-selector did not match: {content_selector}")

    candidates = iter_candidates(soup)
    if not candidates:
        if soup.body:
            return soup.body, "body"
        return soup, "document"

    best = max(candidates, key=candidate_score)
    return best, "auto-detected"


def parse_srcset(srcset: str) -> str:
    best_url = ""
    best_weight = -1.0
    for item in srcset.split(","):
        piece = item.strip()
        if not piece:
            continue
        parts = piece.split()
        url = parts[0]
        weight = 1.0
        if len(parts) > 1:
            descriptor = parts[1].strip().lower()
            if descriptor.endswith("w"):
                try:
                    weight = float(descriptor[:-1])
                except ValueError:
                    weight = 1.0
            elif descriptor.endswith("x"):
                try:
                    weight = float(descriptor[:-1]) * 1000.0
                except ValueError:
                    weight = 1.0
        if weight > best_weight:
            best_weight = weight
            best_url = url
    return best_url


def resolve_image_url(base_url: str, node: Tag) -> str:
    candidates = [
        node.get("src"),
        node.get("data-src"),
        node.get("data-original"),
        node.get("data-lazy-src"),
    ]
    srcset = node.get("srcset") or node.get("data-srcset")
    if srcset:
        candidates.insert(0, parse_srcset(srcset))
    for raw in candidates:
        if not raw:
            continue
        cleaned = raw.strip()
        if not cleaned or cleaned.startswith("data:"):
            continue
        return urljoin(base_url, cleaned)
    return ""


def extract_images(root: Tag, base_url: str, max_images: int) -> list[dict]:
    images: list[dict] = []
    seen_urls: set[str] = set()
    for img in root.find_all("img"):
        image_url = resolve_image_url(base_url, img)
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        image = {"url": image_url}
        alt_text = normalize_space(img.get("alt", ""))
        title_text = normalize_space(img.get("title", ""))
        if alt_text:
            image["alt"] = alt_text
        if title_text:
            image["title"] = title_text
        images.append(image)
        if max_images > 0 and len(images) >= max_images:
            break
    return images


def is_x_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in X_HOSTS


def extract_x_rich_text_node(root: Tag) -> tuple[Tag | None, str, str]:
    best_node: Tag | None = None
    best_text = ""
    best_selector = ""
    for selector in X_RICH_TEXT_SELECTORS:
        try:
            nodes = root.select(selector)
        except Exception:
            continue
        for node in nodes:
            text = normalize_multiline(node.get_text("\n", strip=True))
            if len(text) > len(best_text):
                best_text = text
                best_node = node
                best_selector = selector
    return best_node, best_text, best_selector


def clean_x_text_noise(text: str) -> str:
    cleaned = normalize_space(text)
    if not cleaned:
        return cleaned

    cleaned = re.sub(r"^[^\n]{0,120}@[\w_]{1,40}\s+", "", cleaned)
    cleaned = re.sub(r"^(?:\d+(?:\.\d+)?[万kK]?\s+){2,8}", "", cleaned)

    cleaned = re.sub(
        r"(想发布自己的文章？|升级为 Premium|查看详情|登录|注册)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(上午|下午)?\d{1,2}[:：]\d{2}\s*[·•]\s*\d{4}年\d{1,2}月\d{1,2}日\s*[·•]\s*\d+(?:\.\d+)?[万kK]?\s*查看.*$",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+[·•]\s+\d+(?:\.\d+)?[万kK]?\s*查看.*$", "", cleaned)
    return normalize_space(cleaned)


def normalize_x_rich_text(text: str) -> str:
    lines = normalize_multiline(text).split("\n")
    out: list[str] = []
    in_fence = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(stripped)
            i += 1
            continue

        if not in_fence and stripped == "-":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                merged = lines[j].strip()
                consumed = j
                if consumed + 1 < len(lines):
                    next_line = lines[consumed + 1].strip()
                    if next_line.startswith(":"):
                        merged = f"{merged}{next_line}"
                        consumed += 1
                out.append(f"- {merged.lstrip('- ').strip()}")
                i = consumed + 1
                continue
            out.append("\\-")
            i += 1
            continue

        if not in_fence and stripped.startswith(":") and out:
            out[-1] = out[-1].rstrip() + stripped
            i += 1
            continue

        out.append(lines[i].rstrip())
        i += 1

    # Insert explicit blank lines when leaving a list item; this prevents
    # downstream markdown renderers from swallowing following sections into
    # the last bullet item.
    fixed: list[str] = []
    in_fence = False
    prev_nonempty = ""
    for line in out:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            fixed.append(stripped)
            if stripped:
                prev_nonempty = stripped
            continue

        if (
            not in_fence
            and prev_nonempty.startswith("- ")
            and stripped
            and not stripped.startswith("- ")
        ):
            if fixed and fixed[-1] != "":
                fixed.append("")

        fixed.append(line)
        if stripped:
            prev_nonempty = stripped

    return normalize_multiline("\n".join(fixed))


def should_fallback_to_rich_text(markdown: str, rich_text: str) -> bool:
    markdown_flat = normalize_space(markdown)
    rich_flat = normalize_space(rich_text)
    if not rich_flat:
        return False
    if not markdown_flat:
        return True

    # X rich text frequently uses div/span blocks. A markdown rebuild may
    # preserve headings and bullets but silently drop long narrative chunks.
    return len(markdown_flat) < int(len(rich_flat) * 0.7)


def markdown_line_dedupe_key(line: str) -> str:
    key = line.strip()
    key = re.sub(r"^#+\s+", "", key)
    key = re.sub(r"^[-*>]\s+", "", key)
    key = normalize_space(key)
    return key.lower()


def extract_pre_block_text(node: Tag) -> str:
    snapshot = BeautifulSoup(str(node), "html.parser")
    pre_node = snapshot.find(node.name) or snapshot
    parts: list[str] = []
    block_like_tags = {
        "code",
        "div",
        "p",
        "li",
        "ul",
        "ol",
        "section",
        "article",
        "header",
        "footer",
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }

    def ensure_newline() -> None:
        if parts and not parts[-1].endswith("\n"):
            parts.append("\n")

    def walk(curr: Tag | NavigableString) -> None:
        if isinstance(curr, NavigableString):
            parts.append(str(curr))
            return
        if not isinstance(curr, Tag):
            return

        name = (curr.name or "").lower()
        if name == "br":
            ensure_newline()
            return

        is_block_like = name in block_like_tags
        if is_block_like and parts:
            ensure_newline()

        for child in curr.children:
            walk(child)

        if is_block_like:
            ensure_newline()

    for child in pre_node.children:
        walk(child)

    return normalize_multiline("".join(parts))


def build_markdown_body(root: Tag, extracted_text: str, include_div_leaves: bool = False) -> str:
    block_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"]
    if include_div_leaves:
        block_tags.append("div")

    blocks: list[str] = []
    last_line = ""
    last_key = ""
    for node in root.find_all(block_tags):
        if node.name == "pre":
            raw = extract_pre_block_text(node)
            if not raw:
                continue
            line = "```\n" + raw + "\n```"
        elif include_div_leaves and node.name == "div":
            # Use only leaf-level div blocks to avoid repeating nested text.
            if node.find(block_tags, recursive=False):
                continue
            if node.find_parent(["li", "p", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6"]):
                continue
            text = normalize_multiline(node.get_text("\n", strip=True))
            if not text:
                continue
            line = text
        else:
            text = get_node_text(node)
            if not text:
                continue
            if re.match(r"^h[1-6]$", node.name or ""):
                level = int((node.name or "h2")[1])
                line = "#" * max(min(level, 6), 1) + " " + text
            elif node.name == "li":
                line = "- " + text
            elif node.name == "blockquote":
                line = "> " + text
            else:
                line = text
        line_key = markdown_line_dedupe_key(line)
        if line == last_line or line_key == last_key:
            continue
        blocks.append(line)
        last_line = line
        last_key = line_key
    markdown = "\n\n".join(blocks) if blocks else ""
    fallback_text = (
        normalize_multiline(extracted_text)
        if "\n" in (extracted_text or "")
        else normalize_space(extracted_text)
    )

    if not markdown:
        return fallback_text

    # Some dynamic pages (for example X/Twitter) store body text in div/span nodes.
    # If markdown extraction is too sparse, fall back to full extracted text.
    if fallback_text and len(markdown) < max(320, int(len(fallback_text) * 0.35)):
        return fallback_text
    return markdown


def strip_redundant_leading_title(body_markdown: str, title: str) -> str:
    lines = (body_markdown or "").splitlines()
    if not lines:
        return body_markdown

    first_nonempty = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_nonempty is None:
        return body_markdown

    heading = lines[first_nonempty].strip()
    match = re.match(r"^#{1,6}\s+(.+)$", heading)
    if not match:
        return body_markdown

    if normalize_space(match.group(1)).lower() != normalize_space(title).lower():
        return body_markdown

    del lines[first_nonempty]
    while first_nonempty < len(lines) and not lines[first_nonempty].strip():
        del lines[first_nonempty]
    return "\n".join(lines).strip()


def extract_title(soup: BeautifulSoup, root: Tag) -> str:
    for meta_key in ("og:title", "twitter:title"):
        meta = soup.find("meta", attrs={"property": meta_key}) or soup.find("meta", attrs={"name": meta_key})
        if meta and meta.get("content"):
            return normalize_space(meta["content"])
    h1 = root.find("h1") or soup.find("h1")
    if h1:
        return get_node_text(h1)
    if soup.title and soup.title.string:
        return normalize_space(soup.title.string)
    return "Untitled"


def slugify(value: str) -> str:
    cleaned = normalize_space(value)
    cleaned = re.sub(r"[\\\\/:*?\"<>|]+", "-", cleaned)
    cleaned = re.sub(r"[“”‘’`'!@#$%^&*()+={}\[\];,.，。！？、：；（）【】《》…·]+", "-", cleaned)
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", cleaned)
    cleaned = re.sub(r"[\s]+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._ ")
    if cleaned:
        return cleaned[:120]
    return "article"


def derive_slug(manual_slug: str | None, title: str, source_url: str) -> str:
    if manual_slug:
        return slugify(manual_slug)

    normalized_title = normalize_space(title)
    if normalized_title and normalized_title.lower() != "untitled":
        title_slug = slugify(normalized_title)
        if title_slug != "article":
            return title_slug

    parsed = urlparse(source_url)
    path_tail = Path(parsed.path).name if parsed.path else ""
    path_slug = slugify(path_tail)
    if path_slug and path_slug != "index":
        return path_slug
    return slugify(title)


def markdown_document(
    title: str,
    requested_url: str,
    final_url: str,
    extracted_at: str,
    body_markdown: str,
    images: list[dict],
) -> str:
    final_body = strip_redundant_leading_title(body_markdown, title) or "(empty)"
    lines = [
        f"# {title}",
        "",
        f"- Requested URL: {requested_url}",
        f"- Final URL: {final_url}",
        f"- Extracted at: {extracted_at}",
        "",
        "## Content",
        "",
        final_body,
        "",
        "## Images",
        "",
    ]
    if images:
        for image in images:
            alt = image.get("alt", "").strip() or "image"
            lines.append(f"- ![{alt}]({image['url']})")
    else:
        lines.append("- No in-body images found.")
    return "\n".join(lines).rstrip() + "\n"


def detect_file_extension(image_url: str, content_type: str) -> str:
    path_suffix = Path(urlparse(image_url).path).suffix.lower()
    if path_suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".avif"}:
        return path_suffix
    content_type = (content_type or "").lower()
    if "jpeg" in content_type:
        return ".jpg"
    if "png" in content_type:
        return ".png"
    if "gif" in content_type:
        return ".gif"
    if "webp" in content_type:
        return ".webp"
    if "svg" in content_type:
        return ".svg"
    if "bmp" in content_type:
        return ".bmp"
    if "avif" in content_type:
        return ".avif"
    return ".bin"


def download_images(images: list[dict], output_dir: Path, slug: str, timeout: int, headers: dict[str, str]) -> None:
    image_dir = output_dir / f"{slug}_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    for idx, image in enumerate(images, start=1):
        url = image["url"]
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            extension = detect_file_extension(url, response.headers.get("Content-Type", ""))
            file_path = image_dir / f"{idx:03d}{extension}"
            file_path.write_bytes(response.content)
            image["local_path"] = str(file_path.resolve())
        except Exception as exc:  # pragma: no cover - network errors are runtime dependent
            image["download_error"] = str(exc)


def is_auth_wall(requested_url: str, final_url: str, soup: BeautifulSoup) -> bool:
    final_lower = (final_url or "").lower()
    requested_host = (urlparse(requested_url).hostname or "").lower()
    final_host = (urlparse(final_url).hostname or "").lower()

    auth_url_hit = any(hint in final_lower for hint in AUTH_URL_HINTS)
    host_jump_to_auth = final_host != requested_host and "passport" in final_host

    title_text = normalize_space(soup.title.string if soup.title and soup.title.string else "").lower()
    body_text = normalize_space(soup.get_text(" ", strip=True)[:3000]).lower()
    auth_text_hit = any(hint.lower() in title_text or hint.lower() in body_text for hint in AUTH_TEXT_HINTS)

    return host_jump_to_auth or (auth_url_hit and auth_text_hit)


def main() -> int:
    args = parse_args()
    warnings: list[str] = []

    if args.render_js and args.html_file:
        print("[ERROR] --render-js only works with --url.", file=sys.stderr)
        return 2

    headers = parse_header_items(args.header, warnings)
    cookies = load_cookies(args, warnings)

    requested_url = args.url or (args.base_url or f"file://{Path(args.html_file).expanduser().resolve()}")
    html_text, final_url, http_status, visited_urls = load_html(args, headers, cookies, warnings)

    soup = BeautifulSoup(html_text, "html.parser")
    auth_wall_detected = False
    if args.url:
        auth_wall_detected = is_auth_wall(requested_url, final_url, soup)
        if auth_wall_detected:
            warnings.append(
                "Authentication wall detected. Provide valid login state "
                "(--storage-state / --cookie / --manual-login with --headed)."
            )

    remove_tags(soup, DROP_TAGS)

    selectors = list(args.exclude_selector)
    selectors.extend(load_selector_file(args.exclude_selector_file))
    selectors = [selector for selector in selectors if selector]

    if not args.disable_default_noise_filter:
        remove_by_selectors(soup, list(DEFAULT_NOISE_SELECTORS), warnings)
    if selectors:
        remove_by_selectors(soup, selectors, warnings)

    root, content_selector_used = choose_content_root(soup, args.content_selector, warnings)

    if not args.disable_default_noise_filter:
        remove_by_selectors(root, list(DEFAULT_NOISE_SELECTORS), warnings)
    if selectors:
        remove_by_selectors(root, selectors, warnings)

    title = extract_title(soup, root)
    extracted_text = normalize_space(root.get_text(" ", strip=True))
    body_markdown = build_markdown_body(root, extracted_text)
    images = extract_images(root, final_url, args.max_images)

    if is_x_host(final_url):
        rich_node, rich_text, rich_selector = extract_x_rich_text_node(root)
        if rich_node is not None and rich_text:
            extracted_text = normalize_x_rich_text(rich_text)
            rich_markdown = build_markdown_body(rich_node, extracted_text, include_div_leaves=True)
            if should_fallback_to_rich_text(rich_markdown, extracted_text):
                body_markdown = extracted_text
                warnings.append("X cleanup: markdown fallback to normalized rich text")
            else:
                body_markdown = rich_markdown
            warnings.append(f"X cleanup: using rich text node {rich_selector}")
        else:
            cleaned = clean_x_text_noise(extracted_text)
            if cleaned and cleaned != extracted_text:
                extracted_text = cleaned
                body_markdown = extracted_text
                warnings.append("X cleanup: removed metadata and trailing UI text")

    slug = derive_slug(args.slug, title, requested_url)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    result = {
        "title": title,
        "requested_url": requested_url,
        "final_url": final_url,
        "http_status": http_status,
        "visited_urls": visited_urls,
        "render_js": bool(args.render_js),
        "auth_wall_detected": auth_wall_detected,
        "content_selector_used": content_selector_used,
        "excluded_selectors": selectors,
        "markdown_body": body_markdown,
        "extracted_text": extracted_text,
        "images": images,
        "extracted_at": extracted_at,
        "warnings": warnings,
    }

    if args.download_images and images:
        download_images(images, output_dir, slug, args.timeout, headers)

    json_path = output_dir / f"{slug}.json"
    md_path = output_dir / f"{slug}.md"

    if args.format in ("json", "both"):
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.format in ("markdown", "both"):
        md_path.write_text(
            markdown_document(title, requested_url, final_url, extracted_at, body_markdown, images),
            encoding="utf-8",
        )

    print(f"[OK] title: {title}")
    print(f"[OK] images: {len(images)}")
    print(f"[OK] content selector: {content_selector_used}")
    print(f"[OK] final url: {final_url}")
    print(f"[OK] auth wall detected: {auth_wall_detected}")
    if args.format in ("json", "both"):
        print(f"[OK] json: {json_path}")
    if args.format in ("markdown", "both"):
        print(f"[OK] markdown: {md_path}")
    if warnings:
        print("[WARN] extraction warnings:")
        for warn in warnings:
            print(f"  - {warn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
