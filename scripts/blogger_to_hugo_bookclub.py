#!/usr/bin/env python3
"""
Convert Blogger Atom feed (Reading, Writing, & Arithmetic Club) to Hugo markdown posts.
Filters for LIVE POSTs by L. Barker only.
"""

import xml.etree.ElementTree as ET
import re
import html
import os
from datetime import datetime
import unicodedata

# --- Configuration ---
FEED_PATH = "/Users/lancebarker/Desktop/BlogArchives/Blogger/Blogs/Reading, Writing, &amp_ Arithmetic Club/feed.atom"
OUTPUT_DIR = "/Users/lancebarker/Documents/lancefb.github.io/content/blogs/"
AUTHOR_FILTER = "L. Barker"
TAG = "book club"

# XML namespaces
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "blogger": "http://schemas.google.com/blogger/2018",
}


def slugify(text):
    """Convert text to a URL-friendly slug."""
    text = unicodedata.normalize("NFKD", text)
    text = html.unescape(text)
    text = text.lower().strip()
    text = text.replace("&", "and")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text


def html_to_markdown(html_content):
    """Convert HTML content to clean markdown using regex."""
    if not html_content:
        return ""

    text = html_content

    # Decode HTML entities in the content (Blogger double-encodes)
    text = html.unescape(text)
    text = html.unescape(text)

    # Handle images - convert <img> tags to markdown
    def img_to_md(match):
        tag = match.group(0)
        src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', tag)
        alt_match = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', tag)
        if src_match:
            src = src_match.group(1)
            alt = alt_match.group(1) if alt_match else ""
            return f"![{alt}]({src})"
        return ""

    text = re.sub(r"<img\b[^>]*>", img_to_md, text, flags=re.IGNORECASE)

    # Handle links - convert <a href="...">text</a> to [text](url)
    def link_to_md(match):
        href = match.group(1)
        inner = match.group(2)
        if inner.strip().startswith("!["):
            return inner.strip()
        if inner.strip():
            return f"[{inner.strip()}]({href})"
        return ""

    text = re.sub(
        r'<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        link_to_md,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Handle blockquotes
    def blockquote_to_md(match):
        inner = match.group(1)
        inner = re.sub(r"</?blockquote[^>]*>", "", inner, flags=re.IGNORECASE)
        inner_clean = re.sub(r"<[^>]+>", "", inner).strip()
        inner_clean = html.unescape(inner_clean)
        lines = inner_clean.split("\n")
        quoted = "\n".join(f"> {line.strip()}" for line in lines if line.strip())
        return f"\n\n{quoted}\n\n"

    text = re.sub(
        r"<blockquote[^>]*>(.*?)</blockquote>",
        blockquote_to_md,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Handle headers
    for i in range(6, 0, -1):
        text = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            lambda m, level=i: f"\n\n{'#' * level} {m.group(1).strip()}\n\n",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Handle lists
    text = re.sub(
        r"<li[^>]*>(.*?)</li>",
        lambda m: f"\n- {m.group(1).strip()}",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"</?[ou]l[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Bold
    text = re.sub(
        r"<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>",
        r"**\1**",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Italic
    text = re.sub(
        r"<(?:i|em)[^>]*>(.*?)</(?:i|em)>",
        r"*\1*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Strikethrough
    text = re.sub(
        r"<(?:s|strike|del)[^>]*>(.*?)</(?:s|strike|del)>",
        r"~~\1~~",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Horizontal rules
    text = re.sub(r"<hr[^>]*/?>", "\n\n---\n\n", text, flags=re.IGNORECASE)

    # <br> to newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # Paragraphs
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)

    # Divs
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<div[^>]*>", "", text, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Clean up entities
    text = html.unescape(text)

    # Non-breaking spaces
    text = text.replace("\xa0", " ")
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)

    # Trailing spaces per line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


def format_date(date_str):
    """Parse Blogger date and format for Hugo front matter."""
    date_str = re.sub(r"\.\d+Z$", "Z", date_str)
    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%S-07:00"), dt.strftime("%Y-%m-%d")


def escape_title(title):
    """Escape title for YAML front matter."""
    title = title.replace('"', '\\"')
    return title


def main():
    print(f"Parsing feed: {FEED_PATH}")
    tree = ET.parse(FEED_PATH)
    root = tree.getroot()

    created_files = []
    blogger_image_posts = []
    skipped = {"not_post": 0, "not_live": 0, "wrong_author": 0}

    for entry in root.findall("atom:entry", NS):
        btype_elem = entry.find("blogger:type", NS)
        btype = btype_elem.text if btype_elem is not None else ""
        if btype != "POST":
            skipped["not_post"] += 1
            continue

        bstatus_elem = entry.find("blogger:status", NS)
        bstatus = bstatus_elem.text if bstatus_elem is not None else ""
        if bstatus != "LIVE":
            skipped["not_live"] += 1
            continue

        author_elem = entry.find("atom:author/atom:name", NS)
        author = author_elem.text if author_elem is not None else ""
        if author != AUTHOR_FILTER:
            skipped["wrong_author"] += 1
            continue

        title_elem = entry.find("atom:title", NS)
        title = (title_elem.text or "").strip() if title_elem is not None else "Untitled"

        content_elem = entry.find("atom:content", NS)
        content_html = content_elem.text or "" if content_elem is not None else ""

        published_elem = entry.find("atom:published", NS)
        published_str = published_elem.text if published_elem is not None else ""

        hugo_date, date_prefix = format_date(published_str)

        slug = slugify(title)
        if not slug:
            slug = "untitled"

        filename = f"{date_prefix}-{slug}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        has_blogger_images = "blogger.googleusercontent.com" in content_html
        if has_blogger_images:
            blogger_image_posts.append(filename)

        body = html_to_markdown(content_html)

        front_matter = f'---\ntitle: "{escape_title(title)}"\ndate: {hugo_date}\ndraft: false\ntags: ["{TAG}"]\n---\n'

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(front_matter)
            f.write("\n")
            f.write(body)
            f.write("\n")

        created_files.append(filename)
        print(f"  Created: {filename}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total entries in feed: {len(root.findall('atom:entry', NS))}")
    print(f"Skipped (not POST):    {skipped['not_post']}")
    print(f"Skipped (not LIVE):    {skipped['not_live']}")
    print(f"Skipped (wrong author): {skipped['wrong_author']}")
    print(f"Posts created:         {len(created_files)}")
    print()

    if blogger_image_posts:
        print(f"Posts with Blogger-hosted images ({len(blogger_image_posts)}):")
        for f in blogger_image_posts:
            print(f"  - {f}")
        print("  (Image URLs left as-is in markdown)")
        print()

    print("Created files:")
    for f in sorted(created_files):
        print(f"  {f}")


if __name__ == "__main__":
    main()
