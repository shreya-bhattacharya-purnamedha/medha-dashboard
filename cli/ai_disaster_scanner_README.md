# AI Disaster Scanner — The Medha Audit Pipeline

Scans news sources for AI failures, disasters, and risk events. Automatically classifies each by SIRA framework layer and suggests relevant metrics for analysis.

Built for Purna Medha's weekly "Medha Audit" publication series.

## Setup

```bash
pip install requests beautifulsoup4 feedparser
```

## Usage

```bash
# Scan last 7 days (default), output to terminal
python ai_disaster_scanner.py

# Scan last 30 days, save markdown report
python ai_disaster_scanner.py --days 30 --output medha_scan.md

# JSON output for further processing
python ai_disaster_scanner.py --days 14 --format json --output scan.json
```

## What It Does

1. **Scans 9 RSS feeds** — TechCrunch, Ars Technica, The Register, MIT Tech Review, Wired, The Verge, Reuters, BBC Tech, AI Incident Database
2. **Scans Google News RSS** — 8 targeted queries designed to surface failures, not hype
3. **Queries the AI Incident Database** — the canonical repository of documented AI incidents
4. **Classifies each event by SIRA layer** (L1–L7) using regex pattern matching on the article text
5. **Identifies relevant SIRA metrics** — Medha Yield, CRR, β-AI, Hallucination Rate, Vendor HHI
6. **Estimates severity** — Critical / High / Medium / Low
7. **Detects industry sector** — Healthcare, Finance, Automotive, Legal, etc.
8. **Generates a "Medha Audit Angle"** — a suggested analysis hook for each event
9. **Deduplicates** — removes near-duplicate stories across sources

## Output

The markdown report includes:
- Severity summary (how many Critical/High/Medium/Low)
- SIRA layer distribution (which layers are getting hit most)
- Each event with full classification and a suggested audit angle
- "How to Use" guide for turning events into Medha Audit articles

## SIRA Layers

| Layer | Name | What It Covers |
|-------|------|----------------|
| L1 | Energy & Compute | Power costs, carbon, data centre strain |
| L2 | Infrastructure | Cloud outages, GPU supply, chip concentration |
| L3 | Architecture | Transformer limits, scaling plateau, model collapse |
| L4 | Models | Hallucination, bias, alignment failures |
| L5 | Application | Data leaks, prompt injection, vendor lock-in |
| L6 | Integration | Autonomous systems, healthcare AI, hiring algorithms |
| L7 | Human | Cognitive dependency, deskilling, emotional attachment |

## Automation

Run weekly via cron:
```bash
# Every Monday at 6am IST
0 6 * * 1 cd /path/to/scanner && python ai_disaster_scanner.py --days 7 --output "scans/medha_scan_$(date +\%Y\%m\%d).md"
```

## Extending

- **Add RSS feeds**: Edit the `feeds` dict in `scan_rss_feeds()`
- **Add search queries**: Edit `queries` in `scan_google_news()`
- **Tune classification**: Edit `LAYER_SIGNALS` and `METRIC_SIGNALS` regex patterns
- **Add a new output format**: Add a `format_xxx()` function alongside `format_markdown()` and `format_json()`
