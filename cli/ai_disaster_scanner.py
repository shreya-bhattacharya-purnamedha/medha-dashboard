#!/usr/bin/env python3
"""
AI Disaster Scanner — The Medha Audit Pipeline
================================================
Scans news sources for AI failures, disasters, and risk events.
Categorizes each by SIRA framework layer and suggests relevant metrics.

Usage:
    python ai_disaster_scanner.py                    # Scan all sources
    python ai_disaster_scanner.py --days 3            # Last 3 days only
    python ai_disaster_scanner.py --output report.md  # Save to file
    python ai_disaster_scanner.py --format json       # JSON output

Requires: pip install requests beautifulsoup4 feedparser
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import quote_plus

try:
    import requests
    from bs4 import BeautifulSoup
    import feedparser
except ImportError:
    print("Installing dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", 
                          "requests", "beautifulsoup4", "feedparser",
                          "--break-system-packages", "-q"])
    import requests
    from bs4 import BeautifulSoup
    import feedparser


# ============================================================
# SIRA Framework Classification
# ============================================================

SIRA_LAYERS = {
    "L1": "Energy & Compute",
    "L2": "Infrastructure",
    "L3": "Architecture",
    "L4": "Models",
    "L5": "Application",
    "L6": "Integration",
    "L7": "Human: Cognitive & Emotional",
}

SIRA_METRICS = {
    "MY":  "Medha Yield (risk-adjusted value per ₹1 AI spend)",
    "CRR": "Cognitive Reserve Ratio (% output achievable without AI)",
    "BAI": "AI Dependency Beta (productivity sensitivity to AI availability)",
    "HR":  "Hallucination Rate (% unverified AI output carried as completed)",
    "HHI": "Vendor HHI (concentration index for AI tool stack)",
    "MG":  "Medha Grade (composite ₼AAA to ₼CCC)",
}

# Keyword patterns that signal SIRA layer relevance
LAYER_SIGNALS = {
    "L1": [
        r"energy\s+consumption", r"power\s+grid", r"data\s+cent(er|re)\s+(power|energy|outage)",
        r"gpu\s+shortage", r"compute\s+cost", r"carbon\s+footprint\s+ai",
        r"electricity\s+demand\s+ai", r"cooling\s+(fail|cost)",
    ],
    "L2": [
        r"cloud\s+outage", r"aws\s+(outage|down)", r"azure\s+(outage|down)",
        r"gcp\s+(outage|down)", r"gpu\s+supply", r"chip\s+shortage",
        r"tsmc", r"nvidia\s+(shortage|supply|dominan)", r"infrastructure\s+fail",
        r"server\s+(crash|outage|fail)", r"api\s+(outage|down)",
    ],
    "L3": [
        r"transformer\s+(limit|plateau|bottleneck)", r"scaling\s+law\s+(plateau|limit|diminish)",
        r"architecture\s+(flaw|limit)", r"model\s+collapse",
        r"training\s+on\s+(ai|synthetic)\s+data", r"paradigm\s+(shift|lock)",
    ],
    "L4": [
        r"hallucin", r"confabul", r"fabricat(ed|ing)\s+(information|citation|reference|fact)",
        r"bias(ed)?\s+(output|model|algorithm|training\s+data)",
        r"incorrect\s+(information|answer|response|advice)",
        r"false\s+(information|claim|answer)", r"misinformation",
        r"wrong\s+(answer|information|advice)", r"inaccura(te|cy)",
        r"ai\s+(error|mistake|blunder|gaffe)", r"deepfake",
        r"alignment\s+(fail|problem)", r"jailbreak",
    ],
    "L5": [
        r"data\s+(leak|breach|expos).*\b(ai|chatbot|llm|gpt|claude|gemini)\b",
        r"(ai|chatbot|llm|gpt).*data\s+(leak|breach|expos)",
        r"prompt\s+injection", r"api\s+deprecat", r"vendor\s+lock",
        r"chatbot\s+(fail|error|wrong|mislead|sued|lawsuit)",
        r"ai\s+tool\s+(fail|error|bug|crash)", r"shadow\s+ai",
        r"(copyright|ip)\s+(infring|violat|lawsuit).*ai",
    ],
    "L6": [
        r"autonom(ous|y)\s+(vehicle|car|driv|crash|accident)",
        r"self.driving\s+(crash|accident|fail|recall)",
        r"ai\s+(medical|healthcare|diagnos|treatment)\s*(error|fail|wrong|harm|death)",
        r"algorithm(ic)?\s+(deny|denial|reject|discriminat|bias)",
        r"ai\s+(hiring|recruit|hr)\s*(bias|discriminat|lawsuit|fail)",
        r"ai\s+weapon", r"drone\s+(strike|attack|fail).*ai",
        r"robotic\s+(surgery|procedure)\s*(fail|error|harm)",
        r"cascading\s+fail", r"liability\s+gap",
    ],
    "L7": [
        r"(ai|chatbot)\s*(dependency|addict|attachment|relian)",
        r"deskill", r"cognitive\s+(atrophy|decline|offload|dependency)",
        r"(replac|eliminat|lay\s*off|fire|cut).*\b(worker|employee|staff|job|human)\b.*\bai\b",
        r"\bai\b.*(replac|eliminat|lay\s*off|fire|cut).*\b(worker|employee|staff|job|human)\b",
        r"(mental\s+health|suicide|self.harm).*\b(ai|chatbot)\b",
        r"\b(ai|chatbot)\b.*(mental\s+health|suicide|self.harm)",
        r"emotional\s*(support|companion|relationship).*ai",
        r"ai\s+companion", r"trust\s+(miscalibr|erosion|crisis).*ai",
        r"human\s+oversight\s*(fail|lack|absent)",
        r"ai\s+replace.*human\s+judgment",
        r"over.?relian(ce)?.*\bai\b",
    ],
}

# Metric relevance heuristics
METRIC_SIGNALS = {
    "MY":  [r"roi\b", r"cost\s+saving", r"productivity", r"efficien", r"value", r"spend"],
    "CRR": [r"deskill", r"without\s+ai", r"human\s+(capability|skill|competenc)", r"cognitive\s+reserve"],
    "BAI": [r"dependen", r"outage\s+impact", r"can.?t\s+function\s+without", r"single\s+point\s+of\s+fail"],
    "HR":  [r"hallucin", r"unverified", r"fabricat", r"incorrect", r"inaccura", r"wrong\s+answer"],
    "HHI": [r"vendor\s+(lock|concentrat|single)", r"single\s+provider", r"(aws|azure|openai|google)\s+only"],
    "MG":  [r"systemic", r"multiple\s+(fail|risk|layer)", r"compound", r"cascad"],
}


@dataclass
class AIDisasterEvent:
    """A single AI disaster/failure event discovered from news."""
    title: str
    source: str
    url: str
    published: str
    summary: str
    sira_layers: list = field(default_factory=list)
    sira_metrics: list = field(default_factory=list)
    severity: str = "Medium"  # Low, Medium, High, Critical
    industry: str = "Unknown"
    medha_audit_angle: str = ""


def classify_sira_layers(text: str) -> list:
    """Classify which SIRA layers are relevant based on text content."""
    text_lower = text.lower()
    matched = []
    for layer, patterns in LAYER_SIGNALS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matched.append(layer)
                break
    return matched if matched else ["L4"]  # Default to Model layer


def classify_sira_metrics(text: str) -> list:
    """Identify which SIRA metrics are most relevant."""
    text_lower = text.lower()
    matched = []
    for metric, patterns in METRIC_SIGNALS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matched.append(metric)
                break
    return matched if matched else ["MG"]


def estimate_severity(text: str) -> str:
    """Estimate severity based on keywords."""
    text_lower = text.lower()
    critical_patterns = [r"death", r"killed", r"fatal", r"suicide", r"class.?action", r"billion"]
    high_patterns = [r"lawsuit", r"sued", r"recall", r"banned", r"fired", r"million\s+dollar", r"million\s+loss"]
    medium_patterns = [r"error", r"mistake", r"wrong", r"inaccura", r"mislead", r"fail"]

    for p in critical_patterns:
        if re.search(p, text_lower):
            return "Critical"
    for p in high_patterns:
        if re.search(p, text_lower):
            return "High"
    for p in medium_patterns:
        if re.search(p, text_lower):
            return "Medium"
    return "Low"


def detect_industry(text: str) -> str:
    """Detect the industry sector from text."""
    text_lower = text.lower()
    industries = {
        "Healthcare": [r"health", r"medical", r"hospital", r"patient", r"pharma", r"drug", r"medicare", r"diagnos"],
        "Finance": [r"bank", r"financ", r"insur", r"trading", r"invest", r"fintech", r"payment", r"loan"],
        "Automotive": [r"self.driv", r"autonom.*vehicle", r"tesla", r"waymo", r"cruise", r"car\s+crash"],
        "Legal": [r"lawyer", r"legal", r"law\s+firm", r"court", r"judge", r"attorney"],
        "Education": [r"school", r"student", r"university", r"educat", r"academic", r"cheating"],
        "Retail": [r"retail", r"e.?commerce", r"shopping", r"consumer", r"customer\s+service"],
        "Media": [r"news", r"journal", r"publish", r"media", r"content\s+moderat"],
        "Tech": [r"software", r"saas", r"cloud", r"platform", r"developer", r"startup"],
        "Government": [r"government", r"public\s+sector", r"polic", r"military", r"defense", r"regulat"],
        "HR/Recruitment": [r"hiring", r"recruit", r"resume", r"hr\b", r"workforce", r"employ"],
    }
    for industry, patterns in industries.items():
        for p in patterns:
            if re.search(p, text_lower):
                return industry
    return "General/Cross-Industry"


def generate_audit_angle(event: AIDisasterEvent) -> str:
    """Generate a Medha Audit analysis angle for the event."""
    layer_names = [SIRA_LAYERS.get(l, l) for l in event.sira_layers]
    metric_names = [m for m in event.sira_metrics]

    angles = []
    if "L7" in event.sira_layers:
        angles.append("Human cognitive dependency was the unexamined risk")
    if "HR" in event.sira_metrics:
        angles.append("Unverified AI output was carried as completed work — phantom value")
    if "HHI" in event.sira_metrics:
        angles.append("Single-vendor concentration created fragility")
    if "L6" in event.sira_layers:
        angles.append("AI was integrated into critical decisions without adequate human override")
    if "BAI" in event.sira_metrics:
        angles.append("High β-AI: productivity collapsed when AI failed")
    if "CRR" in event.sira_metrics:
        angles.append("CRR was never measured — nobody knew if the team could function without AI")
    if "MY" in event.sira_metrics:
        angles.append("Gross multiplier looked impressive; risk-adjusted return tells a different story")

    if not angles:
        angles.append(f"SIRA layers {', '.join(event.sira_layers)} exposed — standard risk assessment missed this")

    return ". ".join(angles[:2]) + "."


# ============================================================
# News Source Scanners
# ============================================================

HEADERS = {
    "User-Agent": "MedhaAudit/1.0 (AI Risk Research; contact@purnamedha.ai)"
}

# Search queries designed to find AI disasters
SEARCH_QUERIES = [
    "AI disaster failure 2026",
    "AI chatbot lawsuit sued wrong",
    "AI hallucination error company",
    "AI bias discrimination lawsuit",
    "AI replacement workers failed rehire",
    "artificial intelligence recall safety",
    "AI data leak breach confidential",
    "AI healthcare denial harm patient",
    "autonomous vehicle crash AI",
    "AI deepfake scam fraud",
    "enterprise AI project failed abandoned",
    "AI customer service fail complaint",
    "AI moderation content failure",
    "AI hiring bias discrimination",
    "generative AI copyright lawsuit",
]


def scan_rss_feeds(days: int = 7) -> list:
    """Scan RSS feeds for AI disaster news."""
    events = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Curated RSS feeds covering AI safety, tech failures, and regulation
    feeds = {
        "AI Incident Database": "https://incidentdatabase.ai/rss.xml",
        "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "Ars Technica AI": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "The Register AI": "https://www.theregister.com/software/ai_ml/headlines.atom",
        "MIT Tech Review": "https://www.technologyreview.com/feed/",
        "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
        "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "Reuters Tech": "https://www.reutersagency.com/feed/?best-topics=tech",
        "BBC Tech": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    }

    # Keywords that signal an AI disaster (vs. general AI news)
    disaster_keywords = [
        r"fail", r"error", r"wrong", r"lawsuit", r"sued", r"ban",
        r"recall", r"crash", r"bias", r"discriminat", r"hallucin",
        r"leak", r"breach", r"harm", r"death", r"kill", r"injur",
        r"fired", r"laid\s*off", r"replac", r"mislead", r"scam",
        r"fraud", r"fake", r"deepfake", r"backtrack", r"revers",
        r"abandon", r"shut\s*down", r"apologize", r"apologise",
        r"controversy", r"backlash", r"outrage", r"investigate",
        r"probe", r"fine[ds]?\b", r"penalt", r"violat",
        r"inaccura", r"fabricat", r"misinform", r"dangerous",
        r"unsafe", r"risk", r"vulnerab", r"exploit",
    ]
    disaster_pattern = re.compile("|".join(disaster_keywords), re.IGNORECASE)

    # AI-related keywords to confirm the story is about AI
    ai_keywords = re.compile(
        r"\b(ai|artificial\s+intelligence|machine\s+learn|deep\s+learn|"
        r"chatbot|llm|gpt|gemini|claude|copilot|openai|anthropic|"
        r"automat(ed|ion)|algorithm|neural\s+net|generat(ive|or)|"
        r"self.driv|autonom(ous|y)|robot(ic)?)\b",
        re.IGNORECASE
    )

    for source_name, feed_url in feeds.items():
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:  # Check latest 30 per feed
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                # Strip HTML from summary
                summary = BeautifulSoup(summary, "html.parser").get_text()[:500]
                combined = f"{title} {summary}"

                # Must be AI-related AND contain disaster signals
                if ai_keywords.search(combined) and disaster_pattern.search(combined):
                    # Parse date
                    pub_date = entry.get("published", entry.get("updated", ""))
                    try:
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                            pub_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                        else:
                            pub_dt = datetime.now(timezone.utc)
                    except (TypeError, ValueError):
                        pub_dt = datetime.now(timezone.utc)

                    if pub_dt >= cutoff:
                        event = AIDisasterEvent(
                            title=title.strip(),
                            source=source_name,
                            url=entry.get("link", ""),
                            published=pub_dt.strftime("%Y-%m-%d"),
                            summary=summary[:300].strip(),
                        )
                        event.sira_layers = classify_sira_layers(combined)
                        event.sira_metrics = classify_sira_metrics(combined)
                        event.severity = estimate_severity(combined)
                        event.industry = detect_industry(combined)
                        event.medha_audit_angle = generate_audit_angle(event)
                        events.append(event)
        except Exception as e:
            print(f"  [!] Error scanning {source_name}: {e}", file=sys.stderr)

    return events


def scan_ai_incident_database() -> list:
    """Scan the AI Incident Database (AIID) for recent entries."""
    events = []
    try:
        url = "https://incidentdatabase.ai/api/incidents?limit=20"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for incident in data.get("incidents", []):
                title = incident.get("title", "Untitled Incident")
                desc = incident.get("description", "")
                combined = f"{title} {desc}"

                event = AIDisasterEvent(
                    title=title,
                    source="AI Incident Database",
                    url=f"https://incidentdatabase.ai/cite/{incident.get('incident_id', '')}",
                    published=incident.get("date", "Unknown"),
                    summary=desc[:300],
                )
                event.sira_layers = classify_sira_layers(combined)
                event.sira_metrics = classify_sira_metrics(combined)
                event.severity = estimate_severity(combined)
                event.industry = detect_industry(combined)
                event.medha_audit_angle = generate_audit_angle(event)
                events.append(event)
    except Exception as e:
        print(f"  [!] Error scanning AI Incident Database: {e}", file=sys.stderr)
    return events


def scan_google_news(days: int = 7) -> list:
    """Scan Google News RSS for AI disaster stories."""
    events = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Targeted queries that surface failures, not hype
    queries = [
        "AI failure disaster 2026",
        "AI lawsuit sued bias",
        "AI chatbot wrong misleading",
        "AI workers replaced rehire",
        "AI hallucination company error",
        "AI data breach leak",
        "AI patient harm healthcare",
        "autonomous vehicle crash recall",
    ]

    for query in queries:
        try:
            rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)

            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                summary = BeautifulSoup(summary, "html.parser").get_text()[:500]
                combined = f"{title} {summary}"

                try:
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    else:
                        pub_dt = datetime.now(timezone.utc)
                except (TypeError, ValueError):
                    pub_dt = datetime.now(timezone.utc)

                if pub_dt >= cutoff:
                    event = AIDisasterEvent(
                        title=title.strip(),
                        source="Google News",
                        url=entry.get("link", ""),
                        published=pub_dt.strftime("%Y-%m-%d"),
                        summary=summary[:300].strip(),
                    )
                    event.sira_layers = classify_sira_layers(combined)
                    event.sira_metrics = classify_sira_metrics(combined)
                    event.severity = estimate_severity(combined)
                    event.industry = detect_industry(combined)
                    event.medha_audit_angle = generate_audit_angle(event)
                    events.append(event)
        except Exception as e:
            print(f"  [!] Error scanning Google News for '{query}': {e}", file=sys.stderr)

    return events


# ============================================================
# Deduplication
# ============================================================

def deduplicate(events: list) -> list:
    """Remove near-duplicate events based on title similarity."""
    seen_titles = []
    unique = []

    def normalize(title):
        return re.sub(r"[^a-z0-9\s]", "", title.lower()).strip()

    def is_similar(a, b):
        words_a = set(normalize(a).split())
        words_b = set(normalize(b).split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
        return overlap > 0.6

    for event in events:
        if not any(is_similar(event.title, seen) for seen in seen_titles):
            seen_titles.append(event.title)
            unique.append(event)

    return unique


# ============================================================
# Output Formatters
# ============================================================

def format_markdown(events: list) -> str:
    """Format events as a Markdown report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 🔍 The Medha Audit — AI Disaster Scanner",
        f"**Scan Date:** {now}",
        f"**Events Found:** {len(events)}",
        "",
        "---",
        "",
    ]

    # Summary by severity
    severity_counts = {}
    for e in events:
        severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1
    lines.append("## Severity Summary")
    for sev in ["Critical", "High", "Medium", "Low"]:
        count = severity_counts.get(sev, 0)
        if count:
            emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}[sev]
            lines.append(f"- {emoji} **{sev}:** {count} events")
    lines.append("")

    # Summary by SIRA layer
    layer_counts = {}
    for e in events:
        for l in e.sira_layers:
            layer_counts[l] = layer_counts.get(l, 0) + 1
    lines.append("## SIRA Layer Distribution")
    for layer in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        count = layer_counts.get(layer, 0)
        if count:
            lines.append(f"- **{layer} ({SIRA_LAYERS[layer]}):** {count} events")
    lines.append("")

    # Sort: Critical first, then High, etc.
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    events.sort(key=lambda e: severity_order.get(e.severity, 4))

    lines.append("---")
    lines.append("")
    lines.append("## Events")
    lines.append("")

    for i, event in enumerate(events, 1):
        severity_emoji = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(event.severity, "⚪")
        layer_tags = " · ".join(f"`{l}`" for l in event.sira_layers)
        metric_tags = " · ".join(f"`{m}`" for m in event.sira_metrics)

        lines.append(f"### {i}. {severity_emoji} {event.title}")
        lines.append("")
        lines.append(f"**Source:** {event.source} | **Date:** {event.published} | **Industry:** {event.industry}")
        lines.append(f"**SIRA Layers:** {layer_tags}")
        lines.append(f"**Key Metrics:** {metric_tags}")
        lines.append(f"**Severity:** {event.severity}")
        lines.append(f"**URL:** {event.url}")
        lines.append("")
        lines.append(f"> {event.summary}")
        lines.append("")
        lines.append(f"**Medha Audit Angle:** {event.medha_audit_angle}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Footer with guidance
    lines.extend([
        "## How to Use These for The Medha Audit",
        "",
        "For each event above, ask:",
        "",
        "1. **What was the gross multiplier?** What productivity/cost savings were being reported?",
        "2. **What was the unpriced risk?** Which SIRA layers were exposed but unmeasured?",
        "3. **What would the Medha Grade have been?** Based on CRR, β-AI, Vendor HHI, and Hallucination Rate.",
        "4. **What's the one-line takeaway?** A sentence a CTO could repeat in a board meeting.",
        "",
        "---",
        f"*Generated by AI Disaster Scanner v1.0 — Purna Medha LLP*",
    ])

    return "\n".join(lines)


def format_json(events: list) -> str:
    """Format events as JSON."""
    return json.dumps([asdict(e) for e in events], indent=2, ensure_ascii=False)


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Scan news for AI disasters and classify by SIRA framework"
    )
    parser.add_argument("--days", type=int, default=7,
                       help="Number of days to look back (default: 7)")
    parser.add_argument("--output", type=str, default=None,
                       help="Output file path (default: stdout)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                       help="Output format (default: markdown)")
    args = parser.parse_args()

    print(f"🔍 Scanning for AI disasters (last {args.days} days)...", file=sys.stderr)
    print("", file=sys.stderr)

    all_events = []

    # Scan RSS feeds
    print("  📡 Scanning RSS feeds...", file=sys.stderr)
    rss_events = scan_rss_feeds(days=args.days)
    print(f"     Found {len(rss_events)} events from RSS feeds", file=sys.stderr)
    all_events.extend(rss_events)

    # Scan Google News
    print("  📰 Scanning Google News...", file=sys.stderr)
    google_events = scan_google_news(days=args.days)
    print(f"     Found {len(google_events)} events from Google News", file=sys.stderr)
    all_events.extend(google_events)

    # Scan AI Incident Database
    print("  🗄️  Scanning AI Incident Database...", file=sys.stderr)
    aiid_events = scan_ai_incident_database()
    print(f"     Found {len(aiid_events)} events from AIID", file=sys.stderr)
    all_events.extend(aiid_events)

    # Deduplicate
    print("", file=sys.stderr)
    print(f"  📊 Total raw events: {len(all_events)}", file=sys.stderr)
    unique_events = deduplicate(all_events)
    print(f"  📊 After deduplication: {len(unique_events)}", file=sys.stderr)
    print("", file=sys.stderr)

    # Format output
    if args.format == "json":
        output = format_json(unique_events)
    else:
        output = format_markdown(unique_events)

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"  ✅ Report saved to: {args.output}", file=sys.stderr)
    else:
        print(output)

    print("", file=sys.stderr)
    print(f"  🏁 Done. {len(unique_events)} events classified by SIRA framework.", file=sys.stderr)


if __name__ == "__main__":
    main()
