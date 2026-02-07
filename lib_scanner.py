"""
AI Disaster Scanner — Core Module
Scans news sources for AI failures, disasters, and risk events.
Categorizes each by SIRA framework layer and suggests relevant metrics.
"""

import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
import feedparser

# Timeout for all HTTP requests (seconds) — important for serverless
HTTP_TIMEOUT = 8


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
    "MY":  "Medha Yield (risk-adjusted value per AI spend)",
    "CRR": "Cognitive Reserve Ratio (% output achievable without AI)",
    "BAI": "AI Dependency Beta (productivity sensitivity to AI availability)",
    "HR":  "Hallucination Rate (% unverified AI output carried as completed)",
    "HHI": "Vendor HHI (concentration index for AI tool stack)",
    "MG":  "Medha Grade (composite AAA to CCC)",
}

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

METRIC_SIGNALS = {
    "MY":  [r"roi\b", r"cost\s+saving", r"productivity", r"efficien", r"value", r"spend"],
    "CRR": [r"deskill", r"without\s+ai", r"human\s+(capability|skill|competenc)", r"cognitive\s+reserve"],
    "BAI": [r"dependen", r"outage\s+impact", r"can.?t\s+function\s+without", r"single\s+point\s+of\s+fail"],
    "HR":  [r"hallucin", r"unverified", r"fabricat", r"incorrect", r"inaccura", r"wrong\s+answer"],
    "HHI": [r"vendor\s+(lock|concentrat|single)", r"single\s+provider", r"(aws|azure|openai|google)\s+only"],
    "MG":  [r"systemic", r"multiple\s+(fail|risk|layer)", r"compound", r"cascad"],
}

HEADERS = {
    "User-Agent": "MedhaAudit/1.0 (AI Risk Research; contact@purna-medha.ai)"
}


@dataclass
class AIDisasterEvent:
    title: str
    source: str
    url: str
    published: str
    summary: str
    sira_layers: list = field(default_factory=list)
    sira_metrics: list = field(default_factory=list)
    severity: str = "Medium"
    industry: str = "Unknown"
    medha_audit_angle: str = ""


def classify_sira_layers(text: str) -> list:
    text_lower = text.lower()
    matched = []
    for layer, patterns in LAYER_SIGNALS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matched.append(layer)
                break
    return matched if matched else ["L4"]


def classify_sira_metrics(text: str) -> list:
    text_lower = text.lower()
    matched = []
    for metric, patterns in METRIC_SIGNALS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matched.append(metric)
                break
    return matched if matched else ["MG"]


def estimate_severity(text: str) -> str:
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
        angles.append("High beta-AI: productivity collapsed when AI failed")
    if "CRR" in event.sira_metrics:
        angles.append("CRR was never measured — nobody knew if the team could function without AI")
    if "MY" in event.sira_metrics:
        angles.append("Gross multiplier looked impressive; risk-adjusted return tells a different story")
    if not angles:
        angles.append(f"SIRA layers {', '.join(event.sira_layers)} exposed — standard risk assessment missed this")
    return ". ".join(angles[:2]) + "."


def _classify_event(event: AIDisasterEvent, combined: str):
    event.sira_layers = classify_sira_layers(combined)
    event.sira_metrics = classify_sira_metrics(combined)
    event.severity = estimate_severity(combined)
    event.industry = detect_industry(combined)
    event.medha_audit_angle = generate_audit_angle(event)


# ============================================================
# News Source Scanners
# ============================================================

def scan_rss_feeds(days: int = 7) -> list:
    events = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
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
    ai_keywords = re.compile(
        r"\b(ai|artificial\s+intelligence|machine\s+learn|deep\s+learn|"
        r"chatbot|llm|gpt|gemini|claude|copilot|openai|anthropic|"
        r"automat(ed|ion)|algorithm|neural\s+net|generat(ive|or)|"
        r"self.driv|autonom(ous|y)|robot(ic)?)\b",
        re.IGNORECASE
    )
    for source_name, feed_url in feeds.items():
        try:
            resp = requests.get(feed_url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                summary = BeautifulSoup(summary, "html.parser").get_text()[:500]
                combined = f"{title} {summary}"
                if ai_keywords.search(combined) and disaster_pattern.search(combined):
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
                            title=title.strip(), source=source_name,
                            url=entry.get("link", ""),
                            published=pub_dt.strftime("%Y-%m-%d"),
                            summary=summary[:300].strip(),
                        )
                        _classify_event(event, combined)
                        events.append(event)
        except Exception:
            pass
    return events


def scan_ai_incident_database() -> list:
    events = []
    try:
        url = "https://incidentdatabase.ai/api/incidents?limit=20"
        resp = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            for incident in data.get("incidents", []):
                title = incident.get("title", "Untitled Incident")
                desc = incident.get("description", "")
                combined = f"{title} {desc}"
                event = AIDisasterEvent(
                    title=title, source="AI Incident Database",
                    url=f"https://incidentdatabase.ai/cite/{incident.get('incident_id', '')}",
                    published=incident.get("date", "Unknown"),
                    summary=desc[:300],
                )
                _classify_event(event, combined)
                events.append(event)
    except Exception:
        pass
    return events


def scan_google_news(days: int = 7) -> list:
    events = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
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
            resp = requests.get(rss_url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            feed = feedparser.parse(resp.content)
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
                        title=title.strip(), source="Google News",
                        url=entry.get("link", ""),
                        published=pub_dt.strftime("%Y-%m-%d"),
                        summary=summary[:300].strip(),
                    )
                    _classify_event(event, combined)
                    events.append(event)
        except Exception:
            pass
    return events


def deduplicate(events: list) -> list:
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


def run_scan(days: int = 7) -> dict:
    """Run the full scan pipeline and return structured results."""
    all_events = []
    all_events.extend(scan_rss_feeds(days=days))
    all_events.extend(scan_google_news(days=days))
    all_events.extend(scan_ai_incident_database())
    unique = deduplicate(all_events)

    # Convert to dicts
    events = [asdict(e) for e in unique]

    # Compute aggregates
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    layer_counts = {f"L{i}": 0 for i in range(1, 8)}
    industry_counts = {}
    metric_counts = {}

    for e in events:
        severity_counts[e["severity"]] = severity_counts.get(e["severity"], 0) + 1
        for l in e["sira_layers"]:
            layer_counts[l] = layer_counts.get(l, 0) + 1
        industry_counts[e["industry"]] = industry_counts.get(e["industry"], 0) + 1
        for m in e["sira_metrics"]:
            metric_counts[m] = metric_counts.get(m, 0) + 1

    # Sort events by severity
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    events.sort(key=lambda e: sev_order.get(e["severity"], 4))

    return {
        "scan_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "days": days,
        "total": len(events),
        "severity_counts": severity_counts,
        "layer_counts": layer_counts,
        "industry_counts": dict(sorted(industry_counts.items(), key=lambda x: -x[1])),
        "metric_counts": dict(sorted(metric_counts.items(), key=lambda x: -x[1])),
        "sira_layers": SIRA_LAYERS,
        "sira_metrics": SIRA_METRICS,
        "events": events,
    }
