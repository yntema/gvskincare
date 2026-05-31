#!/usr/bin/env python3
"""Canonical per-platform extraction from raw AEO API result JSON.

Single source of truth for turning a raw API response into (a) the LLM's
response text and (b) its citation/source URLs. Both `analyze.py` (which writes
trend.csv) and `dashboard.py` (which renders the dashboard) import from here so
the audit pipeline and the dashboard can never drift apart.

Add a new platform by extending KNOWN_PLATFORMS and the branches below — in one
place, not two.
"""

import re
from urllib.parse import urlparse

KNOWN_PLATFORMS = ("perplexity", "openai", "anthropic", "gemini", "grok")

_URL_IN_TEXT = re.compile(r'https?://[^\s\)]+')


def extract_text(data, platform):
    """Return the LLM response text from a raw API result ('' if none).

    Text blocks/parts are joined with newlines so paragraph boundaries survive.
    """
    if platform == "perplexity":
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return ""
    if platform in ("openai", "grok"):
        parts = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for block in item.get("content", []):
                    if block.get("type") == "output_text":
                        parts.append(block.get("text", ""))
        return "\n".join(parts)
    if platform == "anthropic":
        parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    if platform == "gemini":
        parts = []
        try:
            for part in data["candidates"][0]["content"]["parts"]:
                parts.append(part.get("text", ""))
        except (KeyError, IndexError):
            pass
        return "\n".join(parts)
    return ""


def extract_citation_urls(data, platform):
    """Return the deduped, sorted list of citation/source URLs from a raw result.

    Gemini returns opaque redirect URLs (vertexaisearch.cloud.google.com); the
    real source domain lives in the chunk `title`, so we synthesize a URL from
    that and drop the redirect. Anthropic carries sources in
    web_search_tool_result blocks plus inline URLs and per-text-block citations.
    """
    urls = []
    if platform == "perplexity":
        urls.extend(data.get("citations", []))
        for sr in data.get("search_results", []):
            if sr.get("url"):
                urls.append(sr["url"])
    elif platform in ("openai", "grok"):
        for item in data.get("output", []):
            if item.get("type") == "message":
                for block in item.get("content", []):
                    for ann in block.get("annotations", []):
                        if ann.get("type") == "url_citation" and ann.get("url"):
                            urls.append(ann["url"])
    elif platform == "gemini":
        try:
            meta = data["candidates"][0].get("groundingMetadata", {})
            for chunk in meta.get("groundingChunks", []):
                web = chunk.get("web", {})
                title = web.get("title", "")
                uri = web.get("uri", "")
                if title and not title.startswith("http"):
                    # title is a domain like "gvskincare.com" — synthesize a URL
                    urls.append(f"https://{title}")
                elif uri and "vertexaisearch" not in uri:
                    urls.append(uri)
        except (KeyError, IndexError):
            pass
    elif platform == "anthropic":
        for block in data.get("content", []):
            btype = block.get("type")
            if btype == "text":
                for c in (block.get("citations") or []):
                    if c.get("url"):
                        urls.append(c["url"])
                urls.extend(_URL_IN_TEXT.findall(block.get("text", "")))
            elif btype == "web_search_tool_result":
                content = block.get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("url"):
                            urls.append(item["url"])

    # Sorted (not just set) so downstream Counter.most_common() tie-breaks are
    # stable — the dashboard then regenerates byte-for-byte instead of reshuffling
    # equal-count rows on every run.
    return sorted(set(urls))


def url_domain(url):
    """Normalize a URL to its bare domain (no scheme, no www, lowercased)."""
    return urlparse(url).netloc.replace("www.", "").lower()
