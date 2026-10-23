"""Turn WordPress/Elementor HTML into clean, editable content blocks."""
import html as html_lib
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, NavigableString

SITE_HOSTS = {"isu-armac.com", "www.isu-armac.com"}
UPLOADS = "/wp-content/uploads/"

ALLOWED = {
    "p": [], "h2": ["id"], "h3": ["id"], "h4": ["id"], "ul": [], "ol": [], "li": [], "br": [],
    "a": ["href", "title", "target", "rel"], "strong": [], "em": [], "img": ["src", "alt", "width", "height"],
    "blockquote": [], "table": [], "thead": [], "tbody": [], "tr": [], "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"], "figure": [], "figcaption": [], "hr": [],
}
RENAME = {"b": "strong", "i": "em", "h1": "h2", "h5": "h4", "h6": "h4"}
DROP = {"script", "style", "noscript", "form", "input", "button", "select", "textarea", "svg", "iframe", "nav", "label"}

# Widgets that are theme decoration, forms or dynamic lists; the new templates replace them.
SKIP_WIDGETS = ("spacer", "divider", "html", "posts", "portfolio", "pagetitle", "page-form", "contact-page-form",
                "google_maps", "home-01-page", "team-01-page-team", "icon.default", "page-banner")
FAQ_WIDGETS = ("accordion", "eael-adv-accordion", "toggle")


def site_path(url):
    """https://isu-armac.com/x/ -> /x/ ; uploads -> /media/uploads/... ; other hosts unchanged."""
    if not url:
        return url
    url = url.strip()
    if url.startswith("#"):
        return url
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.lower() not in SITE_HOSTS:
        return url
    path = parsed.path or "/"
    if path.startswith(UPLOADS):
        return "/media/uploads/" + path[len(UPLOADS):]
    out = path + (f"?{parsed.query}" if parsed.query else "") + (f"#{parsed.fragment}" if parsed.fragment else "")
    return out


def best_img_src(img):
    """Lazy-loaded images keep the real URL in data-* attributes; prefer the largest srcset entry."""
    for attr in ("data-lazy-src", "data-src", "src"):
        val = img.get(attr)
        if val and not val.startswith("data:"):
            src = val
            break
    else:
        return None
    srcset = img.get("data-lazy-srcset") or img.get("srcset") or ""
    best_w = 0
    for part in srcset.split(","):
        bits = part.strip().split()
        if len(bits) == 2 and bits[1].endswith("w"):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                continue
            if w > best_w and w <= 1600:
                best_w, src = w, bits[0]
    return src


def clean_fragment(fragment_html, image_urls=None):
    """Sanitize a chunk of HTML to the ALLOWED set. Collects upload image URLs into image_urls."""
    soup = BeautifulSoup(fragment_html, "lxml")
    body = soup.body or soup
    for c in body.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in body.find_all(DROP):
        tag.decompose()
    for tag in body.find_all(True):
        if tag.name in RENAME:
            tag.name = RENAME[tag.name]
        if tag.name == "img":
            src = best_img_src(tag)
            if not src:
                tag.decompose()
                continue
            alt = tag.get("alt", "")
            tag.attrs = {"src": site_path(src), "alt": alt, "loading": "lazy"}
            if image_urls is not None and urlparse(src).path.startswith(UPLOADS):
                image_urls.add(src.split("?")[0])
            continue
        if tag.name not in ALLOWED:
            tag.unwrap()
            continue
        keep = ALLOWED[tag.name]
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in keep}
        if tag.name == "a":
            if tag.get("href"):
                tag["href"] = site_path(tag["href"])
            if tag.get("target") == "_blank":
                tag["rel"] = "noopener"
    out = "".join(str(c) for c in body.contents)
    out = repair_html(out)
    out = out.replace("\xa0", " ")
    out = re.sub(r"<p>\s*(<br/?>\s*)*</p>", "", out)
    out = re.sub(r"(<br/?>\s*){3,}", "<br><br>", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    # Bare text (Elementor text-editor without <p>) gets wrapped.
    if out and not out.startswith("<"):
        out = f"<p>{out}</p>"
    return out


def text_of(tag):
    return " ".join(tag.get_text(" ", strip=True).split())


def extract_faq(widget):
    """Q&A pairs from Elementor/EAEL accordions and Rank Math FAQ blocks."""
    pairs = []
    for item in widget.select(".elementor-accordion-item, .elementor-toggle-item, .eael-accordion-list, .rank-math-list-item, .faq-item"):
        q = item.select_one(".elementor-tab-title, .eael-accordion-tab-title, .rank-math-question, .eael-accordion-header, .faq-question")
        a = item.select_one(".elementor-tab-content, .eael-accordion-content, .rank-math-answer, .faq-answer")
        if q and a:
            pairs.append((text_of(q), clean_fragment(a.decode_contents())))
    return pairs


def page_blocks(rendered, title, image_urls):
    """Ordered blocks for a page: ("html", str) | ("faq", [(q, a)]) | ("cards", [(title, text, img)]) | ("testimonials", [...])."""
    soup = BeautifulSoup(rendered, "lxml")
    widgets = soup.select("[data-widget_type]")
    if not widgets:
        return [("html", clean_fragment(rendered, image_urls))] if rendered.strip() else []
    blocks = []
    seen_questions = set()
    skipped_title = False
    norm_title = re.sub(r"\W+", " ", title).strip().lower()

    seen_fragments = set()

    def add_html(fragment):
        if not fragment or fragment in seen_fragments:
            return
        seen_fragments.add(fragment)
        if blocks and blocks[-1][0] == "html":
            blocks[-1] = ("html", blocks[-1][1] + "\n" + fragment)
        else:
            blocks.append(("html", fragment))

    for w in widgets:
        kind = w["data-widget_type"]
        if any(s in kind for s in SKIP_WIDGETS):
            continue
        if kind.startswith("heading"):
            h = w.find(["h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "div"], class_=re.compile("heading-title")) or w
            text = text_of(h)
            if not text:
                continue
            norm = re.sub(r"\W+", " ", text).strip().lower()
            if not skipped_title and (norm == norm_title or (h.name == "h1")):
                skipped_title = True
                continue
            level = "h3" if h.name in ("h3", "h4", "h5", "h6") else "h2"
            add_html(f"<{level}>{html_lib.escape(text)}</{level}>")
        elif kind.startswith("text-editor"):
            container = w.select_one(".elementor-widget-container") or w
            add_html(clean_fragment(container.decode_contents(), image_urls))
        elif any(kind.startswith(f) for f in FAQ_WIDGETS) or kind.startswith("shortcode"):
            pairs = [(q, a) for q, a in extract_faq(w) if q.lower() not in seen_questions]
            if pairs:
                seen_questions.update(q.lower() for q, _ in pairs)
                blocks.append(("faq", pairs))
            elif kind.startswith("shortcode"):
                container = w.select_one(".elementor-widget-container") or w
                add_html(clean_fragment(container.decode_contents(), image_urls))
        elif kind.startswith("image-box"):
            t = w.select_one(".elementor-image-box-title")
            d = w.select_one(".elementor-image-box-description")
            img = w.find("img")
            src = best_img_src(img) if img else None
            if src and urlparse(src).path.startswith(UPLOADS):
                image_urls.add(src.split("?")[0])
            card = (text_of(t) if t else "", text_of(d) if d else "", site_path(src) if src else "")
            if blocks and blocks[-1][0] == "cards":
                blocks[-1][1].append(card)
            else:
                blocks.append(("cards", [card]))
        elif kind.startswith("image") or kind.startswith("image-gallery"):
            add_html(clean_fragment(str(w), image_urls))
        elif kind.startswith("button"):
            a = w.find("a")
            if a and a.get("href") and text_of(a):
                add_html(f'<p><a href="{html_lib.escape(site_path(a["href"]))}">{html_lib.escape(text_of(a))}</a></p>')
        elif "testimonial" in kind:
            quotes = []
            for body in w.select("p.lead"):
                name = body.find_next(["h4", "h5"])
                org = name.find_next_sibling("span") if name else None
                who = text_of(name) if name else ""
                if org and text_of(org):
                    who += ", " + text_of(org).lstrip("- ").strip()
                quotes.append((text_of(body), who))
            if quotes:
                blocks.append(("testimonials", quotes))
        else:
            container = w.select_one(".elementor-widget-container") or w
            add_html(clean_fragment(container.decode_contents(), image_urls))
    return [b for b in blocks if b[1]]


def plain_text(html_fragment):
    return " ".join(BeautifulSoup(html_fragment or "", "lxml").get_text(" ").split())


TITLE_SUFFIX = re.compile(r"\s*(?:[|–—-]|&#8211;|&#8212;)\s*(?:ISU[\s-]*Armac.*|ARMAC.*|Insurance in Victorville.*)$", re.I)


def clean_title(raw):
    t = html_lib.unescape(raw or "").strip()
    t = TITLE_SUFFIX.sub("", t).strip()
    t = re.sub(r"\s{2,}", " ", t)
    return t


# Repairs for damage left by earlier automated editing of the WordPress content -----------------

MD_LINK = re.compile(r"\(?\[([^\]]{1,120})\]\((https?://[^)\s]+)\)\)?")
UTM_OPENAI = re.compile(r"[?&]utm_source=openai")


def _strip_utm(url):
    url = UTM_OPENAI.sub("", url)
    return url


def repair_html(fragment):
    """Remove writer-facing notes, convert pasted markdown citations to links, drop stray image URLs."""
    if not fragment:
        return fragment
    soup = BeautifulSoup(fragment, "lxml")
    body = soup.body or soup
    for p in body.find_all("p"):
        text = text_of(p)
        if (re.match(r"^(header image|(iptc|image|photo) metadata\b|suggested image metadata|alt text\b|!\[|\{: \.align)", text, re.I)
                or re.search(r"\bIPTC\b|data-iptc|includes IPTC metadata", text)):
            nxt = p.find_next_sibling()
            if nxt is not None and nxt.name in ("ul", "ol"):
                nxt.decompose()
            p.decompose()
            continue
        if re.fullmatch(r"https?://\S+\.(jpe?g|png|webp|gif)", text, re.I):
            p.decompose()
            continue
        if "[object Object]" in text and re.search(r"internal link", text, re.I):
            p.decompose()  # the AI writer's note about a missing link, published by mistake
            continue
        if re.search(r"\bvocab( to learn)?\s*:\s*$", text, re.I):
            p.clear()
            strong = soup.new_tag("strong")
            strong.string = "Related reading"
            p.append(strong)
    for h in body.find_all(["h2", "h3", "h4"]):
        if re.fullmatch(r"header image", text_of(h), re.I):
            h.decompose()
    for li in body.find_all("li"):
        if re.match(r"^(alt text|iptc (headline|description|keywords)|image (title|caption))\s*:", text_of(li), re.I):
            li.decompose()
    for a in body.find_all("a"):
        if not a.get("href") and not text_of(a):
            a.decompose()
            continue
        if a.get("href"):
            a["href"] = _strip_utm(a["href"])
    for p in body.find_all("p"):
        if not text_of(p) and not p.find("img"):
            p.decompose()
    for node in list(body.find_all(string=MD_LINK)):
        if node.find_parent("a"):
            continue
        parts, last = [], 0
        for m in MD_LINK.finditer(node):
            parts.append(node[last:m.start()])
            link = soup.new_tag("a", href=_strip_utm(m.group(2)), rel="noopener", target="_blank")
            link.string = m.group(1)
            parts.extend(["(", link, ")"])
            last = m.end()
        parts.append(node[last:])
        for piece in parts:
            node.insert_before(piece if not isinstance(piece, str) else NavigableString(piece))
        node.extract()
    return "".join(str(c) for c in body.contents)
