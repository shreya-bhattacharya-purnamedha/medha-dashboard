#!/usr/bin/env python3
"""
AI Disaster Scanner — Dashboard Generator
==========================================
Runs the scanner and generates a self-contained HTML dashboard.

Usage:
    python ai_disaster_dashboard.py                     # 7-day scan, opens in browser
    python ai_disaster_dashboard.py --days 30           # 30-day scan
    python ai_disaster_dashboard.py --no-open           # Don't auto-open browser
    python ai_disaster_dashboard.py --from-json scan.json  # Build from existing JSON
"""

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from dataclasses import asdict
from pathlib import Path
from html import escape

# Import the scanner
from ai_disaster_scanner import (
    scan_rss_feeds, scan_google_news, scan_ai_incident_database,
    deduplicate, SIRA_LAYERS, SIRA_METRICS,
)


def run_scan(days: int) -> list:
    """Run the full scan pipeline and return events as dicts."""
    print(f"Scanning for AI disasters (last {days} days)...", file=sys.stderr)

    all_events = []

    print("  Scanning RSS feeds...", file=sys.stderr)
    all_events.extend(scan_rss_feeds(days=days))

    print("  Scanning Google News...", file=sys.stderr)
    all_events.extend(scan_google_news(days=days))

    print("  Scanning AI Incident Database...", file=sys.stderr)
    all_events.extend(scan_ai_incident_database())

    unique = deduplicate(all_events)
    print(f"  {len(unique)} unique events after dedup (from {len(all_events)} raw)", file=sys.stderr)

    return [asdict(e) for e in unique]


def generate_dashboard(events: list, days: int) -> str:
    """Generate a self-contained HTML dashboard from event data."""

    # Compute stats
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(events)

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

    # Sort industries by count
    sorted_industries = sorted(industry_counts.items(), key=lambda x: -x[1])
    # Sort metrics by count
    sorted_metrics = sorted(metric_counts.items(), key=lambda x: -x[1])

    # Sort events: Critical first
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    events.sort(key=lambda e: severity_order.get(e["severity"], 4))

    # Escape event data for embedding in JS
    events_json = json.dumps(events, ensure_ascii=False)

    # SIRA layer labels for JS
    sira_layers_json = json.dumps(SIRA_LAYERS)
    sira_metrics_json = json.dumps(SIRA_METRICS)

    # Build layer bar data (each layer gets its own color class)
    max_layer = max(layer_counts.values()) if any(layer_counts.values()) else 1
    layer_bars_html = ""
    for lid in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        count = layer_counts[lid]
        pct = (count / max_layer * 100) if max_layer else 0
        name = SIRA_LAYERS[lid]
        layer_bars_html += f"""
        <div class="bar-row" data-layer="{lid}">
          <div class="bar-label">{lid}</div>
          <div class="bar-track">
            <div class="bar-fill layer-{lid}" style="width:{pct}%"></div>
          </div>
          <div class="bar-value">{count}</div>
          <div class="bar-sublabel">{escape(name)}</div>
        </div>"""

    # Build industry bar data (each industry gets a rotating color)
    max_ind = sorted_industries[0][1] if sorted_industries else 1
    industry_bars_html = ""
    for idx, (ind, count) in enumerate(sorted_industries[:8]):
        pct = (count / max_ind * 100) if max_ind else 0
        industry_bars_html += f"""
        <div class="bar-row">
          <div class="bar-label ind-label">{escape(ind)}</div>
          <div class="bar-track">
            <div class="bar-fill ind-{idx}" style="width:{pct}%"></div>
          </div>
          <div class="bar-value">{count}</div>
        </div>"""

    # Build metric bar data (each metric gets a rotating color)
    max_met = sorted_metrics[0][1] if sorted_metrics else 1
    metric_bars_html = ""
    for idx, (met, count) in enumerate(sorted_metrics[:6]):
        pct = (count / max_met * 100) if max_met else 0
        full_name = SIRA_METRICS.get(met, met)
        metric_bars_html += f"""
        <div class="bar-row">
          <div class="bar-label">{escape(met)}</div>
          <div class="bar-track">
            <div class="bar-fill met-{idx}" style="width:{pct}%"></div>
          </div>
          <div class="bar-value">{count}</div>
          <div class="bar-sublabel">{escape(full_name)}</div>
        </div>"""

    # Build SIRA framework reference
    sira_layer_descriptions = {
        "L1": "Power costs, carbon footprint, data centre strain, cooling failures",
        "L2": "Cloud outages, GPU supply chains, chip concentration, API downtime",
        "L3": "Transformer limits, scaling plateau, model collapse, training on synthetic data",
        "L4": "Hallucination, bias, alignment failures, deepfakes, jailbreaks",
        "L5": "Data leaks, prompt injection, vendor lock-in, copyright infringement",
        "L6": "Autonomous systems, healthcare AI, hiring algorithms, liability gaps",
        "L7": "Cognitive dependency, deskilling, emotional attachment, over-reliance",
    }

    sira_layer_colors = {
        "L1": "#e74c3c", "L2": "#e67e22", "L3": "#f1c40f", "L4": "#248fef",
        "L5": "#9b59b6", "L6": "#1abc9c", "L7": "#e84393",
    }

    sira_layer_cards_html = ""
    for lid in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
        name = SIRA_LAYERS[lid]
        desc = sira_layer_descriptions[lid]
        color = sira_layer_colors[lid]
        sira_layer_cards_html += f"""
      <div class="sira-layer-card">
        <div class="sira-layer-badge" style="background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12);color:{color}">{lid}</div>
        <div class="sira-layer-info">
          <h3>{escape(name)}</h3>
          <p>{escape(desc)}</p>
        </div>
      </div>"""

    sira_metric_details = {
        "MY": {
            "name": "Medha Yield",
            "tagline": "Risk-adjusted value per unit of AI spend",
            "formula": "MY = (Value Created \u2212 Risk-Adjusted Losses) \u00f7 Total AI Spend",
            "inputs": [
                "Value Created = hours saved \u00d7 hourly rate + revenue from AI-enabled output",
                "Risk-Adjusted Losses = P(failure) \u00d7 cost-of-failure for each SIRA layer exposed",
                "Total AI Spend = subscriptions + API costs + compute + integration labour",
            ],
            "interpretation": "MY > 1.0 = net positive return. MY < 1.0 = AI costs more than it delivers after accounting for risk. Most organisations report gross multipliers of 3\u201310\u00d7 but ignore risk; risk-adjusted MY is typically 0.4\u20131.8\u00d7.",
            "color": "#248fef",
        },
        "CRR": {
            "name": "Cognitive Reserve Ratio",
            "tagline": "Could your team still function without AI?",
            "formula": "CRR = (Output achievable without AI \u00f7 Current total output) \u00d7 100%",
            "inputs": [
                "Numerator = team output if all AI tools were removed for 2 weeks",
                "Denominator = current output with AI assistance",
                "Measured per function: engineering, legal, content, support, etc.",
            ],
            "interpretation": "CRR > 70% = healthy reserve. CRR 40\u201370% = moderate dependency. CRR < 40% = critical \u2014 the team cannot deliver without AI. Most teams have never measured this.",
            "color": "#e74c3c",
        },
        "BAI": {
            "name": "AI Dependency Beta (\u03b2-AI)",
            "tagline": "How hard does productivity crash when AI goes down?",
            "formula": "\u03b2-AI = % Productivity Drop \u00f7 % AI Availability Drop",
            "inputs": [
                "Productivity Drop = (normal output \u2212 output during AI outage) \u00f7 normal output",
                "AI Availability Drop = (expected uptime \u2212 actual uptime) \u00f7 expected uptime",
                "Measured during real outages or simulated \u201cAI fire drills\u201d",
            ],
            "interpretation": "\u03b2-AI = 1.0 = linear dependency. \u03b2-AI > 1.5 = amplified fragility (small outage \u2192 large productivity collapse). \u03b2-AI < 0.5 = resilient. High \u03b2-AI with low CRR is the most dangerous combination.",
            "color": "#e67e22",
        },
        "HR": {
            "name": "Hallucination Rate",
            "tagline": "How much unverified AI output is treated as done?",
            "formula": "HR = (Unverified AI outputs accepted as final \u00f7 Total AI outputs) \u00d7 100%",
            "inputs": [
                "Unverified = AI-generated work shipped without human review or validation",
                "Total AI outputs = all code, text, analysis, or decisions where AI contributed",
                "Tracked via review logs, QA audits, or spot-check sampling",
            ],
            "interpretation": "HR < 5% = strong verification culture. HR 5\u201320% = typical enterprise. HR > 20% = phantom value \u2014 the organisation is booking AI output as completed work without confirming accuracy.",
            "color": "#9b59b6",
        },
        "HHI": {
            "name": "Vendor HHI",
            "tagline": "How concentrated is your AI tool stack?",
            "formula": "HHI = \u03a3(s\u1d62)\u00b2 where s\u1d62 = spend share of vendor i",
            "inputs": [
                "List every AI vendor (OpenAI, Anthropic, Google, AWS Bedrock, etc.)",
                "s\u1d62 = annual spend on vendor i \u00f7 total AI spend across all vendors",
                "Square each share and sum: HHI = s\u2081\u00b2 + s\u2082\u00b2 + \u2026 + s\u2099\u00b2",
            ],
            "interpretation": "HHI < 0.15 = diversified. HHI 0.15\u20130.40 = moderate concentration. HHI > 0.40 = high concentration risk. HHI = 1.0 = single vendor (maximum fragility). Standard Herfindahl\u2013Hirschman Index adapted for AI procurement.",
            "color": "#1abc9c",
        },
        "MG": {
            "name": "Medha Grade",
            "tagline": "The composite AI risk rating (\u20bcAAA to \u20bcCCC)",
            "formula": "MG = f(CRR, \u03b2-AI, HHI, HR) \u2192 mapped to \u20bcAAA \u2013 \u20bcCCC",
            "inputs": [
                "Each sub-metric scored 1\u20135: CRR (higher = better), \u03b2-AI (lower = better), HHI (lower = better), HR (lower = better)",
                "Weighted composite: 30% CRR + 25% \u03b2-AI + 25% HHI + 20% HR",
                "Score mapped: 4.0\u20135.0 = \u20bcAAA, 3.0\u20133.9 = \u20bcAA, 2.0\u20132.9 = \u20bcBBB, 1.0\u20131.9 = \u20bcCCC",
            ],
            "interpretation": "\u20bcAAA = low AI risk, strong reserves, diversified stack, verified outputs. \u20bcCCC = high dependency, single vendor, unverified AI output, no fallback. Think credit ratings, but for your AI posture.",
            "color": "#f1c40f",
        },
    }

    sira_metric_rows_html = ""
    for code, detail in sira_metric_details.items():
        c = detail["color"]
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        inputs_html = "".join(f"<li>{escape(inp)}</li>" for inp in detail["inputs"])
        sira_metric_rows_html += f"""
        <div class="sira-metric-card">
          <div class="sira-metric-header" onclick="this.parentElement.classList.toggle('open')">
            <span class="sira-metric-badge" style="background:rgba({r},{g},{b},0.12);color:{c}">{escape(code)}</span>
            <div class="sira-metric-title-block">
              <span class="sira-metric-title">{escape(detail['name'])}</span>
              <span class="sira-metric-tagline">{escape(detail['tagline'])}</span>
            </div>
            <span class="metric-chevron">&#9654;</span>
          </div>
          <div class="sira-metric-detail">
            <div class="metric-formula-box">
              <div class="metric-formula-label">Formula</div>
              <div class="metric-formula">{escape(detail['formula'])}</div>
            </div>
            <div class="metric-inputs-box">
              <div class="metric-inputs-label">Inputs</div>
              <ul class="metric-inputs-list">{inputs_html}</ul>
            </div>
            <div class="metric-interp-box">
              <div class="metric-interp-label">How to read it</div>
              <div class="metric-interp">{escape(detail['interpretation'])}</div>
            </div>
          </div>
        </div>"""

    # Build event cards HTML
    event_cards_html = ""
    for i, e in enumerate(events):
        sev = e["severity"]
        sev_class = sev.lower()
        layers_tags = " ".join(
            f'<span class="tag tag-layer">{escape(l)}</span>' for l in e["sira_layers"]
        )
        metrics_tags = " ".join(
            f'<span class="tag tag-metric">{escape(m)}</span>' for m in e["sira_metrics"]
        )
        industry_tag = f'<span class="tag tag-industry">{escape(e["industry"])}</span>'

        event_cards_html += f"""
    <div class="event-card severity-{sev_class}"
         data-severity="{sev}"
         data-layers="{','.join(e['sira_layers'])}"
         data-industry="{escape(e['industry'])}">
      <div class="event-header">
        <span class="sev-dot {sev_class}"></span>
        <span class="event-title">{escape(e['title'])}</span>
        <span class="event-date">{escape(e['published'])}</span>
      </div>
      <div class="event-meta">
        <span class="event-source">{escape(e['source'])}</span>
        {industry_tag}
        {layers_tags}
        {metrics_tags}
      </div>
      <div class="event-body">
        <p class="event-summary">{escape(e['summary'])}</p>
        <p class="event-angle"><strong>Medha Audit Angle:</strong> {escape(e['medha_audit_angle'])}</p>
        <a class="event-link" href="{escape(e['url'])}" target="_blank" rel="noopener">Read source article &rarr;</a>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Medha Audit — AI Disaster Scanner</title>
<style>
  :root {{
    --bg: #f0f4f8;
    --surface: #ffffff;
    --surface2: #e8eef4;
    --border: #d0dbe6;
    --text: #1a2332;
    --text2: #5a6b7d;
    --accent: #248fef;
    --accent-light: #1a7ad4;
    --accent-dim: rgba(36, 143, 239, 0.10);
    --critical: #dc2f4a;
    --high: #e07a2f;
    --medium: #c9a020;
    --low: #2ba866;
    --layer-fill: #248fef;
    --ind-fill: #3a7bd5;
    --met-fill: #1a9bcf;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --mono: "SF Mono", "Fira Code", "Fira Mono", Menlo, monospace;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    line-height: 1.5;
    min-height: 100vh;
  }}

  .container {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 24px 20px;
  }}

  /* Header */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 32px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
  }}
  .header-left h1 {{
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.02em;
  }}
  .header-left h1 span {{ color: var(--accent); }}
  .header-left .subtitle {{
    color: var(--text2);
    font-size: 0.85rem;
    margin-top: 4px;
  }}
  .header-right {{
    text-align: right;
    color: var(--text2);
    font-size: 0.8rem;
    font-family: var(--mono);
  }}
  .header-right .scan-date {{ color: var(--text); font-weight: 600; }}

  /* Summary Cards */
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 32px;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    transition: transform 0.15s, border-color 0.15s;
    cursor: pointer;
  }}
  .stat-card:hover {{
    transform: translateY(-2px);
    border-color: var(--accent);
  }}
  .stat-card.active {{
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }}
  .stat-card .stat-value {{
    font-size: 2rem;
    font-weight: 800;
    font-family: var(--mono);
    line-height: 1;
  }}
  .stat-card .stat-label {{
    font-size: 0.75rem;
    color: var(--text2);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 8px;
  }}
  .stat-card.total .stat-value {{ color: var(--accent); }}
  .stat-card.critical .stat-value {{ color: var(--critical); }}
  .stat-card.high .stat-value {{ color: var(--high); }}
  .stat-card.medium .stat-value {{ color: var(--medium); }}
  .stat-card.low .stat-value {{ color: var(--low); }}

  /* Chart Panels */
  .charts-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .chart-panel {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }}
  .chart-panel h2 {{
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text2);
    margin-bottom: 16px;
  }}

  /* Bar Charts */
  .bar-row {{
    display: grid;
    grid-template-columns: 36px 1fr 32px;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    cursor: pointer;
    padding: 4px 6px;
    border-radius: 6px;
    transition: background 0.12s;
  }}
  .bar-row:hover {{ background: var(--surface2); }}
  .bar-row.active {{ background: var(--surface2); }}
  .bar-label {{
    font-family: var(--mono);
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text2);
    text-align: right;
  }}
  .bar-label.ind-label {{
    font-family: var(--font);
    font-size: 0.72rem;
    text-align: left;
    grid-column: 1 / 2;
    min-width: 100px;
  }}
  .bar-track {{
    height: 22px;
    background: var(--surface2);
    border-radius: 4px;
    overflow: hidden;
  }}
  .bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    min-width: 3px;
  }}
  .layer-fill {{ background: var(--layer-fill); }}
  .ind-fill {{ background: var(--ind-fill); }}
  .met-fill {{ background: var(--met-fill); }}

  /* Distinct SIRA layer colors */
  .layer-L1 {{ background: #e74c3c; }}
  .layer-L2 {{ background: #e67e22; }}
  .layer-L3 {{ background: #f1c40f; }}
  .layer-L4 {{ background: #248fef; }}
  .layer-L5 {{ background: #9b59b6; }}
  .layer-L6 {{ background: #1abc9c; }}
  .layer-L7 {{ background: #e84393; }}

  /* Distinct industry colors */
  .ind-0 {{ background: #248fef; }}
  .ind-1 {{ background: #9b59b6; }}
  .ind-2 {{ background: #e67e22; }}
  .ind-3 {{ background: #1abc9c; }}
  .ind-4 {{ background: #e74c3c; }}
  .ind-5 {{ background: #2ecc71; }}
  .ind-6 {{ background: #f1c40f; }}
  .ind-7 {{ background: #e84393; }}

  /* Distinct metric colors */
  .met-0 {{ background: #248fef; }}
  .met-1 {{ background: #e74c3c; }}
  .met-2 {{ background: #1abc9c; }}
  .met-3 {{ background: #e67e22; }}
  .met-4 {{ background: #9b59b6; }}
  .met-5 {{ background: #f1c40f; }}
  .bar-value {{
    font-family: var(--mono);
    font-size: 0.8rem;
    font-weight: 600;
    text-align: right;
  }}
  .bar-sublabel {{
    grid-column: 1 / -1;
    font-size: 0.7rem;
    color: var(--text2);
    margin-top: -4px;
    margin-bottom: 4px;
    padding-left: 46px;
  }}

  /* Industry bars need wider label */
  .chart-panel.industry-chart .bar-row {{
    grid-template-columns: 120px 1fr 32px;
  }}
  .chart-panel.metric-chart .bar-row {{
    grid-template-columns: 36px 1fr 32px;
  }}

  /* Filter bar */
  .filter-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 20px;
  }}
  .filter-bar label {{
    font-size: 0.75rem;
    color: var(--text2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-right: 4px;
  }}
  .filter-btn {{
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text2);
    font-size: 0.78rem;
    padding: 6px 14px;
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.12s;
    font-family: var(--font);
  }}
  .filter-btn:hover {{ border-color: var(--accent); color: var(--text); }}
  .filter-btn.active {{
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }}
  .filter-sep {{
    width: 1px;
    height: 20px;
    background: var(--border);
    margin: 0 4px;
  }}

  /* Events Section */
  .events-section {{
    margin-bottom: 40px;
  }}
  .events-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }}
  .events-header h2 {{
    font-size: 1.1rem;
    font-weight: 600;
  }}
  .events-count {{
    font-family: var(--mono);
    font-size: 0.8rem;
    color: var(--text2);
  }}

  /* Event Cards */
  .event-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 10px;
    overflow: hidden;
    transition: border-color 0.12s;
    border-left: 3px solid var(--border);
  }}
  .event-card.severity-critical {{ border-left-color: var(--critical); }}
  .event-card.severity-high {{ border-left-color: var(--high); }}
  .event-card.severity-medium {{ border-left-color: var(--medium); }}
  .event-card.severity-low {{ border-left-color: var(--low); }}
  .event-card:hover {{ border-color: var(--accent); }}

  .event-header {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 14px 16px;
    cursor: pointer;
  }}
  .sev-dot {{
    flex-shrink: 0;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-top: 6px;
  }}
  .sev-dot.critical {{ background: var(--critical); }}
  .sev-dot.high {{ background: var(--high); }}
  .sev-dot.medium {{ background: var(--medium); }}
  .sev-dot.low {{ background: var(--low); }}

  .event-title {{
    flex: 1;
    font-weight: 600;
    font-size: 0.92rem;
    line-height: 1.4;
  }}
  .event-date {{
    flex-shrink: 0;
    font-family: var(--mono);
    font-size: 0.75rem;
    color: var(--text2);
    margin-top: 2px;
  }}

  .event-meta {{
    display: none;
    flex-wrap: wrap;
    gap: 6px;
    padding: 0 16px 10px 36px;
  }}
  .event-card.open .event-meta {{ display: flex; }}

  .event-body {{
    display: none;
    padding: 0 16px 16px 36px;
  }}
  .event-card.open .event-body {{ display: block; }}

  .event-summary {{
    color: var(--text2);
    font-size: 0.85rem;
    margin-bottom: 10px;
    line-height: 1.6;
  }}
  .event-angle {{
    font-size: 0.85rem;
    margin-bottom: 10px;
    padding: 10px 14px;
    background: var(--surface2);
    border-radius: 8px;
    border-left: 3px solid var(--accent);
  }}
  .event-source {{
    font-size: 0.72rem;
    color: var(--text2);
    background: var(--surface2);
    padding: 3px 10px;
    border-radius: 10px;
  }}
  .event-link {{
    color: var(--accent);
    font-size: 0.82rem;
    text-decoration: none;
  }}
  .event-link:hover {{ text-decoration: underline; }}

  /* Tags */
  .tag {{
    display: inline-block;
    font-size: 0.7rem;
    padding: 2px 10px;
    border-radius: 10px;
    font-family: var(--mono);
    font-weight: 500;
  }}
  .tag-layer {{
    background: var(--accent-dim);
    color: var(--accent);
  }}
  .tag-metric {{
    background: rgba(26, 155, 207, 0.10);
    color: var(--met-fill);
  }}
  .tag-industry {{
    background: rgba(58, 123, 213, 0.10);
    color: var(--ind-fill);
  }}

  /* SIRA Framework Reference */
  .sira-section {{
    margin-bottom: 32px;
  }}
  .sira-toggle {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    cursor: pointer;
    transition: border-color 0.12s;
  }}
  .sira-toggle:hover {{ border-color: var(--accent); }}
  .sira-toggle h2 {{
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
  }}
  .sira-toggle h2 span {{ color: var(--accent); }}
  .sira-toggle .toggle-hint {{
    font-size: 0.75rem;
    color: var(--text2);
    font-family: var(--mono);
  }}
  .sira-toggle .chevron {{
    display: inline-block;
    transition: transform 0.2s;
    color: var(--accent);
    font-size: 1.1rem;
    margin-left: 8px;
  }}
  .sira-section.open .sira-toggle .chevron {{ transform: rotate(90deg); }}

  .sira-content {{
    display: none;
    margin-top: 12px;
  }}
  .sira-section.open .sira-content {{ display: block; }}

  .sira-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }}

  .sira-layer-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    display: flex;
    gap: 14px;
    align-items: flex-start;
    transition: border-color 0.12s;
  }}
  .sira-layer-card:hover {{ border-color: var(--accent); }}

  .sira-layer-badge {{
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: 10px;
    background: var(--accent-dim);
    color: var(--accent);
    font-family: var(--mono);
    font-weight: 800;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }}

  .sira-layer-info h3 {{
    font-size: 0.88rem;
    font-weight: 600;
    margin-bottom: 4px;
  }}
  .sira-layer-info p {{
    font-size: 0.78rem;
    color: var(--text2);
    line-height: 1.5;
  }}

  .sira-metrics-panel {{
    background: transparent;
    padding: 0;
  }}
  .sira-metrics-panel h3 {{
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text2);
    margin-bottom: 14px;
  }}
  .sira-metric-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 10px;
    overflow: hidden;
    transition: border-color 0.12s;
  }}
  .sira-metric-card:hover {{ border-color: var(--accent); }}
  .sira-metric-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    cursor: pointer;
  }}
  .sira-metric-badge {{
    flex-shrink: 0;
    width: 44px;
    height: 32px;
    border-radius: 8px;
    font-family: var(--mono);
    font-weight: 800;
    font-size: 0.78rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .sira-metric-title-block {{
    flex: 1;
    display: flex;
    flex-direction: column;
  }}
  .sira-metric-title {{
    font-weight: 600;
    font-size: 0.9rem;
  }}
  .sira-metric-tagline {{
    font-size: 0.78rem;
    color: var(--text2);
    margin-top: 2px;
  }}
  .metric-chevron {{
    color: var(--accent);
    font-size: 0.85rem;
    transition: transform 0.2s;
    flex-shrink: 0;
  }}
  .sira-metric-card.open .metric-chevron {{ transform: rotate(90deg); }}

  .sira-metric-detail {{
    display: none;
    padding: 0 16px 16px 16px;
  }}
  .sira-metric-card.open .sira-metric-detail {{ display: block; }}

  .metric-formula-box {{
    background: var(--surface2);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
  }}
  .metric-formula-label,
  .metric-inputs-label,
  .metric-interp-label {{
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text2);
    margin-bottom: 6px;
    font-weight: 600;
  }}
  .metric-formula {{
    font-family: var(--mono);
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--accent);
    line-height: 1.5;
  }}
  .metric-inputs-box {{
    margin-bottom: 12px;
  }}
  .metric-inputs-list {{
    list-style: none;
    padding: 0;
  }}
  .metric-inputs-list li {{
    font-size: 0.82rem;
    color: var(--text);
    padding: 4px 0 4px 16px;
    position: relative;
    line-height: 1.5;
  }}
  .metric-inputs-list li::before {{
    content: "\u2023";
    position: absolute;
    left: 0;
    color: var(--accent);
    font-weight: 700;
  }}
  .metric-interp-box {{
    background: var(--surface2);
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 3px solid var(--accent);
  }}
  .metric-interp {{
    font-size: 0.82rem;
    color: var(--text);
    line-height: 1.6;
  }}

  /* Empty state */
  .empty-state {{
    text-align: center;
    padding: 60px 20px;
    color: var(--text2);
  }}
  .empty-state .empty-icon {{ font-size: 2rem; margin-bottom: 12px; }}

  /* Footer */
  .footer {{
    text-align: center;
    padding: 24px;
    border-top: 1px solid var(--border);
    color: var(--text2);
    font-size: 0.75rem;
  }}
  .footer a {{ color: var(--accent); text-decoration: none; }}

  /* Responsive */
  @media (max-width: 600px) {{
    .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .charts-grid {{ grid-template-columns: 1fr; }}
    .header {{ flex-direction: column; }}
    .header-right {{ text-align: left; }}
  }}

  /* Animations */
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .event-card {{
    animation: fadeIn 0.3s ease both;
  }}
</style>
</head>
<body>

<div class="container">

  <!-- Header -->
  <div class="header">
    <div class="header-left">
      <h1><span>Medha Audit</span> &mdash; AI Disaster Scanner</h1>
      <div class="subtitle">SIRA Framework Classification &middot; Purna-Medha LLP</div>
    </div>
    <div class="header-right">
      <div class="scan-date">{now}</div>
      <div>Last {days} days &middot; {total} events</div>
    </div>
  </div>

  <!-- Summary Cards -->
  <div class="summary-grid">
    <div class="stat-card total" data-filter="all" onclick="filterSeverity('all', this)">
      <div class="stat-value">{total}</div>
      <div class="stat-label">Total Events</div>
    </div>
    <div class="stat-card critical" data-filter="Critical" onclick="filterSeverity('Critical', this)">
      <div class="stat-value">{severity_counts['Critical']}</div>
      <div class="stat-label">Critical</div>
    </div>
    <div class="stat-card high" data-filter="High" onclick="filterSeverity('High', this)">
      <div class="stat-value">{severity_counts['High']}</div>
      <div class="stat-label">High</div>
    </div>
    <div class="stat-card medium" data-filter="Medium" onclick="filterSeverity('Medium', this)">
      <div class="stat-value">{severity_counts['Medium']}</div>
      <div class="stat-label">Medium</div>
    </div>
    <div class="stat-card low" data-filter="Low" onclick="filterSeverity('Low', this)">
      <div class="stat-value">{severity_counts['Low']}</div>
      <div class="stat-label">Low</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="charts-grid">
    <div class="chart-panel">
      <h2>SIRA Layer Distribution</h2>
      {layer_bars_html}
    </div>
    <div class="chart-panel industry-chart">
      <h2>Industry Breakdown</h2>
      {industry_bars_html}
    </div>
    <div class="chart-panel metric-chart">
      <h2>Key Metrics Triggered</h2>
      {metric_bars_html}
    </div>
  </div>

  <!-- SIRA Framework Reference -->
  <div class="sira-section" id="siraSection">
    <div class="sira-toggle" onclick="document.getElementById('siraSection').classList.toggle('open')">
      <h2><span>SIRA</span> Framework Reference</h2>
      <div>
        <span class="toggle-hint">7 Layers &middot; 6 Metrics</span>
        <span class="chevron">&#9654;</span>
      </div>
    </div>
    <div class="sira-content">
      <div class="sira-grid">
        {sira_layer_cards_html}
      </div>
      <div class="sira-metrics-panel">
        <h3>SIRA Metrics</h3>
        {sira_metric_rows_html}
      </div>
    </div>
  </div>

  <!-- Filter Bar -->
  <div class="filter-bar" id="filterBar">
    <label>Layer:</label>
    <button class="filter-btn active" data-layer="all" onclick="filterLayer('all', this)">All</button>
    <button class="filter-btn" data-layer="L1" onclick="filterLayer('L1', this)">L1</button>
    <button class="filter-btn" data-layer="L2" onclick="filterLayer('L2', this)">L2</button>
    <button class="filter-btn" data-layer="L3" onclick="filterLayer('L3', this)">L3</button>
    <button class="filter-btn" data-layer="L4" onclick="filterLayer('L4', this)">L4</button>
    <button class="filter-btn" data-layer="L5" onclick="filterLayer('L5', this)">L5</button>
    <button class="filter-btn" data-layer="L6" onclick="filterLayer('L6', this)">L6</button>
    <button class="filter-btn" data-layer="L7" onclick="filterLayer('L7', this)">L7</button>
    <div class="filter-sep"></div>
    <button class="filter-btn" onclick="toggleAll(true)">Expand All</button>
    <button class="filter-btn" onclick="toggleAll(false)">Collapse All</button>
  </div>

  <!-- Events -->
  <div class="events-section">
    <div class="events-header">
      <h2>Events</h2>
      <div class="events-count" id="visibleCount">{total} of {total}</div>
    </div>
    <div id="eventsList">
      {event_cards_html}
    </div>
    <div class="empty-state" id="emptyState" style="display:none">
      <div class="empty-icon">-_-</div>
      <div>No events match the current filters.</div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    AI Disaster Scanner v1.0 &middot; Purna-Medha LLP &middot; SIRA Framework Classification
    <br>Generated {now}
  </div>
</div>

<script>
  // State
  let activeSeverity = 'all';
  let activeLayer = 'all';

  // Toggle event card expand/collapse
  document.querySelectorAll('.event-header').forEach(header => {{
    header.addEventListener('click', () => {{
      header.parentElement.classList.toggle('open');
    }});
  }});

  function filterSeverity(sev, el) {{
    activeSeverity = sev;
    document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('active'));
    if (el) el.classList.add('active');
    applyFilters();
  }}

  function filterLayer(layer, el) {{
    activeLayer = layer;
    document.querySelectorAll('#filterBar .filter-btn[data-layer]').forEach(b => b.classList.remove('active'));
    if (el) el.classList.add('active');
    applyFilters();
  }}

  function applyFilters() {{
    const cards = document.querySelectorAll('.event-card');
    let visible = 0;
    cards.forEach(card => {{
      const sevMatch = activeSeverity === 'all' || card.dataset.severity === activeSeverity;
      const layers = card.dataset.layers.split(',');
      const layerMatch = activeLayer === 'all' || layers.includes(activeLayer);
      if (sevMatch && layerMatch) {{
        card.style.display = '';
        visible++;
      }} else {{
        card.style.display = 'none';
      }}
    }});
    document.getElementById('visibleCount').textContent = visible + ' of ' + cards.length;
    document.getElementById('emptyState').style.display = visible === 0 ? '' : 'none';
  }}

  function toggleAll(open) {{
    document.querySelectorAll('.event-card').forEach(card => {{
      if (card.style.display !== 'none') {{
        if (open) card.classList.add('open');
        else card.classList.remove('open');
      }}
    }});
  }}

  // Clicking a SIRA layer card filters events to that layer
  document.querySelectorAll('.sira-layer-card').forEach(card => {{
    card.style.cursor = 'pointer';
    card.addEventListener('click', () => {{
      const badge = card.querySelector('.sira-layer-badge');
      if (badge) {{
        const layer = badge.textContent.trim();
        const btn = document.querySelector(`#filterBar .filter-btn[data-layer="${{layer}}"]`);
        filterLayer(layer, btn);
      }}
    }});
  }});

  // Clickable bar rows for layer filtering
  document.querySelectorAll('.bar-row[data-layer]').forEach(row => {{
    row.addEventListener('click', () => {{
      const layer = row.dataset.layer;
      const btn = document.querySelector(`#filterBar .filter-btn[data-layer="${{layer}}"]`);
      filterLayer(layer, btn);
    }});
  }});
</script>

</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="Generate AI Disaster Scanner dashboard")
    parser.add_argument("--days", type=int, default=7, help="Days to scan (default: 7)")
    parser.add_argument("--output", type=str, default=None, help="Output HTML path")
    parser.add_argument("--no-open", action="store_true", help="Don't open in browser")
    parser.add_argument("--from-json", type=str, default=None, help="Build from existing JSON file")
    args = parser.parse_args()

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as f:
            events = json.load(f)
        print(f"Loaded {len(events)} events from {args.from_json}", file=sys.stderr)
    else:
        events = run_scan(args.days)

    html = generate_dashboard(events, args.days)

    out_path = args.output or f"scans/medha_dashboard_{datetime.now().strftime('%Y%m%d')}.html"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard saved to: {out_path}", file=sys.stderr)

    if not args.no_open:
        webbrowser.open(f"file://{Path(out_path).resolve()}")


if __name__ == "__main__":
    main()
