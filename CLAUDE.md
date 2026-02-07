# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Intelligence Currency Tracker — a personal productivity analytics tool that measures ROI on AI-assisted development. The core concept is calculating an "intelligence multiplier": value created through AI-assisted projects divided by subscription cost.

## Current State

The project is in early stages. Currently contains:
- `Usage Logs.md` — Documents Claude Code stats file locations

The primary data source is `~/.claude/stats-cache.json`, which contains:
- Daily activity (messages, sessions, tool calls per day)
- Daily model token usage broken down by model ID
- Aggregate model usage (input/output tokens, cache read/creation tokens)
- Session metadata (total sessions, total messages, longest session, first session date)
- Hourly activity distribution

## Key Data Source: `~/.claude/stats-cache.json`

Structure (version 2):
- `dailyActivity[]` — `{date, messageCount, sessionCount, toolCallCount}`
- `dailyModelTokens[]` — `{date, tokensByModel: {modelId: tokenCount}}`
- `modelUsage.{modelId}` — `{inputTokens, outputTokens, cacheReadInputTokens, cacheCreationInputTokens}`
- `totalSessions`, `totalMessages`, `firstSessionDate`, `longestSession`, `hourCounts`

## Architecture Intent

The project aims to build:
1. **A Python CLI tracker** — reads Claude stats + user-logged projects, calculates intelligence multiplier
2. **A web dashboard** — static HTML/JS that visualizes exported data

Key metrics to compute:
- API-equivalent cost (what the usage would cost at API rates vs. flat subscription)
- Value created (project hours saved × category hourly rate)
- Intelligence multiplier (total value / subscription cost)
- Net currency gained (value - subscription cost)

## Development Notes

- No external Python dependencies — use only the standard library
- No build system or package manager needed
- Python 3.9+ assumed
