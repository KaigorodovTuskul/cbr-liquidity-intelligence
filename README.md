<div align="center">
  <h1>CBR Liquidity Intelligence</h1>
  <p><strong>Bank of Russia Liquidity, Money Markets & Balance Sheet Analytics</strong></p>
  <p>An open-source Agent Skill & high-performance workflow for analyzing Russian banking liquidity (2024–2026),<br>Form 101/135/123 balances, interbank market (MBK), REPO, RUONIA, and CBR operations.</p>
  <p>
    <a href="https://agentskills.io/specification"><img src="https://img.shields.io/badge/Agent_Skills-open_standard-00B8C8" alt="Agent Skills"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-586776" alt="MIT"></a>
    <img src="https://img.shields.io/badge/version-1.0.0-00B8C8" alt="Version 1.0.0">
    <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  </p>
  <p><a href="#quick-start">Quick start</a> · <a href="#data-sources">Data sources</a> · <a href="#key-findings">Key findings</a> · <a href="#how-it-works">How it works</a> · <a href="#methodology-guardrails">Methodology</a></p>
  <p><strong>Русский</strong> · <strong>English</strong></p>
</div>

---

## Why CBR Liquidity Intelligence?

Analyzing the liquidity of the Russian banking sector is fraught with complex regulatory changes, opaque accounts, and subtle methodology traps:
- **Sanction-era Account Changes:** In public Form 101 files, the Bank of Russia stopped publishing 2nd-order accounts. Accounts 320 and 321 are aggregated into `"32.1"`, while account `91314` (pledged securities under REPO) is omitted completely.
- **Methodology Fallacy (Stock vs Flow):** LLM agents and human analysts routinely commit the critical error of summing balance sheet balances (Stock) with daily trading turnovers (Flow).
- **Speed & Autonomy:** Instead of relying on slow web scraping or paid API gateways, this skill streams DBF archives directly from `cbr.ru` into memory, processing 3+ years of balance sheets across 350 banks in under 15 seconds without a database.

---

## Quick Start

### Install for AI Agents (Antigravity, Codex, Claude Code, Cursor)

Via Agent Skills CLI:
```bash
npx skills add KaigorodovTuskul/cbr-liquidity-intelligence --skill cbr-liquidity-intelligence
```

Or install locally with the zero-dependency Python installer:
```bash
python scripts/install.py --project /path/to/your/project
```

### Give the AI Agent a task:
```text
Используй навык cbr-liquidity-intelligence.
Проанализируй, кто из банков в 2026 году является главным донором ликвидности на МБК,
и сопоставь это с их нормативами мгновенной ликвидности Н2.
```

---

## Data Sources

| Code | Indicator | Type | Official Source | Focus |
|---|---|---|---|---|
| **S1** | CBR Deposits (Total, O/N, Auctions) | Stock | `cbr.ru/hd_base/ostat_depo_new/` | CBR liquidity absorption |
| **S2** | MBK & REPO Average Daily Turnovers | Flow | `cbr.ru/statistics/finr` | Money market transaction volumes |
| **S3** | RUONIA Overnight Index & Volume | Flow | `cbr.ru/hd_base/ruonia/dynamics/` | Benchmark interbank O/N rate |
| **S4** | CBR REPO Auctions | Flow | `cbr.ru/hd_base/repo/` | Regulatory liquidity provision |
| **S7** | Form 101 Balance Sheet (DBF) | Stock | `cbr.ru/banking_sector/` | Accounts 319 (CBR), 32.1 (MBK), 301 |
| **F135** | Form 135 Regulatory Ratios | Ratio | `cbr.ru/banking_sector/` | Instant (H2) & Current (H3) liquidity |
| **F123** | Form 123 Equity Capital | Stock | `cbr.ru/banking_sector/` | Bank equity (code 000) |

---

## Key Findings (2024–2026)

1. **Foreign Bank "Liquidity Trap" (Account 319):**  
   Out of 3.30 trillion RUB parked on CBR deposits, **over 52% (1.72 trln RUB)** is held by just 3 European subsidiary banks: **Raiffeisenbank** (959.2 bln RUB), **OTP Bank** (437.0 bln RUB), and **UniCredit** (327.0 bln RUB). Constrained by parent groups from growing loan portfolios, they park excess float in CBR deposits, driving H2 ratios above 300%–650%.
2. **Fintech & Marketplaces as Market Donors:**  
   Neobanks have emerged as the primary net lenders on the interbank market: **Ozon Bank** (+350.0 bln RUB), **Tochka** (+252.5 bln RUB), **Yandex Bank** (+107.9 bln RUB).
3. **Large Corporate Banks as Recipients:**  
   The primary net borrowers absorbing market liquidity for lending are **Gazprombank** (-1.38 trln RUB net position), **Sberbank** (-469.5 bln RUB), and **Alfa-Bank** (-408.7 bln RUB).
4. **REPO Market Boom:**  
   Average daily REPO market turnover surged from **1.72 trln RUB/day** (Jan 2024) to **2.92 trln RUB/day** (Sep 2026), with over 90% executed in overnight contracts.

---

## Methodology Guardrails

1. **Stock ≠ Flow:** Never sum balance sheet stocks (Form 101, account 319) with turnover flows (S2 daily turnovers, RUONIA).
2. **CBR REPO is Liquidity Provision:** CBR REPO (S4) represents the Central Bank *loaning money to banks* against collateral. It is not bank placement.
3. **Supervisory Secrecy:** Deal-level forms (Form 0409501 and 0409701) are confidential bank secrecy and are never published per individual bank.

---

## Repository Structure

```text
cbr-liquidity-intelligence/
├── skills/
│   └── cbr-liquidity-intelligence/
│       ├── SKILL.md                 # Agent entry point (token-optimized frontmatter)
│       ├── references/
│       │   ├── workflow.md          # In-depth source & DBF parsing specs
│       │   └── methodology.md       # Financial logic & guardrails
│       └── scripts/
│           ├── fetch_cbr_liquidity.py
│           ├── fetch_multiyear_liquidity.py
│           ├── build_visual_dashboard.py
│           └── generate_report.py
├── examples/
│   ├── quickstart.py                # 5-line quick start
│   ├── fetch_s1_minimal.py
│   └── parse_f101_minimal.py
├── scripts/
│   ├── install.py                   # Zero-dependency multi-agent installer
│   └── validate.py                  # Spec compliance & link validator
├── tests/
│   └── test_structure.py            # Unit test
├── AGENTS.md                        # Fallback instructions for LLMs
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                          # MIT License
└── requirements.txt
```

---

## License

MIT License (c) 2026 Tuskul Kaigorodov. See [LICENSE](LICENSE) for details.
