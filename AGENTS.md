# CBR Liquidity Intelligence — Agent Rules & Operational Guidance

Canonical skill: [`skills/cbr-liquidity-intelligence/SKILL.md`](skills/cbr-liquidity-intelligence/SKILL.md).  
This file provides rules for AI coding agents (Antigravity, Codex, Claude Code, Cursor) analyzing Russian banking liquidity.

## Core Rules

1. **Token Efficiency:** Do not preload large balance tables into conversational context. Direct the user to generated artifacts (`dashboard.html`, CSV reports) or execute scripts to answer targeted metrics.
2. **Economic Guardrail (Stock vs Flow):** Never sum balance sheet stocks (account 319, account 32.1) with turnover flows (S2 daily REPO/MBK turnover, RUONIA volume).
3. **CBR REPO Interpretation:** Operations of CBR REPO (S4) are liquidity provision (credits to banks), not placements.
4. **Data Privacy Boundaries:** Never hallucinate individual bank deal logs from supervisory forms 0409501 and 0409701 (confidential supervisory reporting). Use Form 101, 135 and 123 for bank-level insights.
