import sys
import re

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run:  pip install requests beautifulsoup4")
    sys.exit(1)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Patterns to strip from output (translator notes, dividers, nav links, etc.)
NOISE_PATTERNS = re.compile(
    r"(^\s*※\s*(?:※\s*)*$"
    r"|ALL RIGHTS BELONG TO"
    r"|Translated by\s*:"
    r"|Proofread by\s*:"
    r"|Art Sources"
    r"|Loading comments"
    r"|^Previous\s+Chapter"
    r"|^Next\s+Chapter"
    r"|^\s*[←→]\s*"
    r"|^\s*\[\s*\]\s*$)",
    re.IGNORECASE | re.MULTILINE,
)


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def extract(html: str) -> tuple[str, str]:
    """Return (title, body_text) from a WCT chapter page."""
    soup = BeautifulSoup(html, "html.parser")

    # --- Title ---
    title_tag = (
        soup.find("h1", class_="entry-title")
        or soup.find("h2", class_="entry-title")
        or soup.find("title")
    )
    title = title_tag.get_text(" ", strip=True) if title_tag else "Unknown Chapter"
    # Clean " | Witch Cult Translations" suffix from <title> tags
    title = re.sub(r"\s*\|\s*Witch Cult Translations.*$", "", title).strip()

    # --- Content ---
    content_div = (
        soup.find("div", class_="entry-content")
        or soup.find("div", class_="post-content")
        or soup.find("div", class_="post-body")
    )
    if not content_div:
        return title, ""

    # Remove junk sub-elements (comments, sharing, nav)
    for el in content_div.find_all(
        True,
        class_=re.compile(r"sharedaddy|wpcnt|comments|navigation|post-nav|entry-footer|wp-block-separator"),
    ):
        el.decompose()
    for el_id in ("comments", "respond", "disqus_thread"):
        el = content_div.find(id=el_id)
        if el:
            el.decompose()

    # Walk block elements and collect text
    lines = []
    for el in content_div.find_all(["p", "h1", "h2", "h3", "h4", "h5", "blockquote", "li"]):
        text = el.get_text(" ", strip=True)
        text = text.replace("\xa0", " ").replace("\u200b", "").strip()
        if text:
            lines.append(text)
            lines.append("")  # blank line after each block

    body = "\n".join(lines)

    # Strip noise lines
    body = NOISE_PATTERNS.sub("", body)

    # Collapse 3+ consecutive newlines to 2
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    return title, body


def derive_filename(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^a-z0-9\-]", "", slug.lower())
    return slug[:80] + ".txt"


def scrape(url: str, output_path: str | None = None):
    print(f"Fetching:  {url}")
    html = fetch(url)

    title, body = extract(html)

    if not body.strip():
        print("ERROR: No content found. The page structure may have changed.")
        sys.exit(1)

    if output_path is None:
        output_path = derive_filename(url)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(title + "\n")
        f.write("=" * len(title) + "\n\n")
        f.write(body)
        f.write("\n")

    word_count = len(body.split())
    print(f"Saved to:  {output_path}")
    print(f"Title:     {title}")
    print(f"~Words:    {word_count:,}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    url_arg = sys.argv[1]
    out_arg = sys.argv[2] if len(sys.argv) >= 3 else None

    if not url_arg.startswith("http"):
        print(f"ERROR: Expected a URL, got: {url_arg}")
        sys.exit(1)

    scrape(url_arg, out_arg)
