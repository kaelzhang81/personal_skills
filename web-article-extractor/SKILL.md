---
name: web-article-extractor
description: Extract clean article body text and in-body images from web pages while excluding irrelevant regions such as headers, sidebars, ads, footers, recommendation blocks, and comments. Use when users ask to scrape/read/save article content from a URL and need selector-based control over what to keep or remove.
---

# Web Article Extractor

## Overview

Extract the main article content and in-body images from a webpage with controllable CSS selectors.
Use this skill when default extraction includes noise and a precise keep/remove strategy is needed.

## Quick Start

1. Run extraction with URL only.
2. Review Markdown and JSON outputs.
3. Rerun with `--exclude-selector` if noise remains.
4. Set `--content-selector` if auto-detection misses the main body.

```bash
python3 scripts/extract_article.py \
  --url "https://example.com/post/123" \
  --output-dir /tmp/article-out
```

## Workflow

### 1) Pick Input Mode

- Use `--url` for live pages.
- Use `--html-file` for offline debugging.
- Use `--base-url` with `--html-file` to resolve relative image links.
- Use `--render-js` for SPA or login-gated pages that need browser rendering.

### 2) Exclude Non-content Regions

Add repeated `--exclude-selector` values for page regions that should not be extracted.

```bash
python3 scripts/extract_article.py \
  --url "https://example.com/post/123" \
  --exclude-selector "header" \
  --exclude-selector "footer" \
  --exclude-selector ".sidebar" \
  --exclude-selector ".related-posts" \
  --exclude-selector ".comments"
```

You can also pass a selector file:

```bash
python3 scripts/extract_article.py \
  --url "https://example.com/post/123" \
  --exclude-selector-file references/noise-selectors.example.txt
```

### 3) Lock Main Body With Content Selector (Optional)

When the page has a stable article wrapper, force extraction from that container.

```bash
python3 scripts/extract_article.py \
  --url "https://example.com/post/123" \
  --content-selector "article .article-body" \
  --exclude-selector ".paywall" \
  --exclude-selector ".author-card"
```

### 4) Handle Login-gated Pages (Optional)

If output is a login page, use browser rendering and login state:

```bash
python3 scripts/extract_article.py \
  --url "https://example.com/post/123" \
  --render-js \
  --storage-state /tmp/auth_state.json \
  --content-selector ".article-content" \
  --exclude-selector ".comments" \
  --output-dir /tmp/article-out
```

For first-time login state capture:

```bash
python3 scripts/extract_article.py \
  --url "https://example.com/post/123" \
  --render-js \
  --headed \
  --manual-login \
  --wait-ms 6000 \
  --save-storage-state /tmp/auth_state.json \
  --output-dir /tmp/article-out
```

KM (Tencent) practical selector example:

```bash
python3 scripts/extract_article.py \
  --url "https://km.woa.com/knowledge/10431/node/17" \
  --render-js \
  --content-selector ".km-view-content.km-article-content" \
  --exclude-selector ".article-comment-container" \
  --output-dir /tmp/article-out
```

### 5) Save Output Format

- Default is `--format both` (Markdown + JSON).
- Use `--format markdown` or `--format json` when only one output is needed.
- Enable `--download-images` to save image files locally.

## Output Contract

Script output files:
- `<slug>.md`
- `<slug>.json`
- `<slug>_images/` (only when `--download-images` is enabled)

JSON fields:
- `title`
- `requested_url`
- `final_url`
- `http_status`
- `auth_wall_detected`
- `content_selector_used`
- `excluded_selectors`
- `markdown_body`
- `extracted_text`
- `images` (image URL + alt/title + optional local path)
- `extracted_at`

## Quality Checklist

- Main body should not include nav/footer/ads/recommendation/comments content.
- Image list should match images inside the article body.
- Add or refine selectors if noise exists.
- Narrow selectors if content is over-pruned.
- If `auth_wall_detected=true`, provide valid login state and retry.

## Resources

- `scripts/extract_article.py`: Main extractor script.
- `references/noise-selectors.example.txt`: Starter selector list.
