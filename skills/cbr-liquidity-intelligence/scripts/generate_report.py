"""
Генерация отчёта report.md по собранным CSV.
Запуск: python scripts/generate_report.py
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_mn(v) -> str:
    """Форматирует млн руб. → читаемый вид."""
    if pd.isna(v):
        return "н/д"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f} трлн руб."
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f} млрд руб."
    return f"{v:,.1f} млн руб."


def fmt_bln(v) -> str:
    if pd.isna(v):
        return "н/д"
    return f"{v:,.2f} млрд руб."


def load(name: str) -> pd.DataFrame | None:
    p = PROC / f"{name}.csv"
    if not p.exists():
        return None
    date_cols = ["reference_date"] if name not in ["s2"] else []
    try:
        df = pd.read_csv(p, dtype={"num_sc": str}, parse_dates=date_cols if date_cols else False)
    except Exception:
        df = pd.read_csv(p, dtype={"num_sc": str})
    return df


def s1_section(df: pd.DataFrame) -> str:
    df = df.sort_values("reference_date", ascending=False)
    latest = df.iloc[0]
    date_str = latest["reference_date"].strftime("%d.%m.%Y")
    lines = [
        "## S1. Депозиты кредитных организаций в Банке России",
        "",
        f"**Источник:** https://www.cbr.ru/hd_base/ostat_depo_new/  ",
        f"**Тип показателя:** остаток (stock) на начало дня  ",
        f"**Единица:** млн руб.  ",
        f"**Охват:** весь банковский сектор РФ  ",
        "",
        f"### Последнее наблюдение ({date_str})",
        "",
        f"| Показатель | Значение |",
        f"|---|---|",
        f"| **Всего депозитов в ЦБ** | {fmt_mn(latest.get('total_mn', float('nan')))} |",
        f"| Овернайт постоянного действия | {fmt_mn(latest.get('overnight_mn', float('nan')))} |",
        f"| Недельные аукционы | {fmt_mn(latest.get('weekly_auction_mn', float('nan')))} |",
        f"| Тонкой настройки | {fmt_mn(latest.get('fine_tuning_mn', float('nan')))} |",
        "",
        "### Динамика (последние 10 наблюдений)",
        "",
        "| Дата | Всего (млн руб.) | Овернайт (млн руб.) |",
        "|---|---:|---:|",
    ]
    for _, row in df.head(10).iterrows():
        d = row["reference_date"].strftime("%d.%m.%Y")
        lines.append(f"| {d} | {row.get('total_mn', float('nan')):,.2f} | {row.get('overnight_mn', float('nan')):,.2f} |")

    lines += [
        "",
        "> **Методологическое примечание:** «Депозиты банков в ЦБ» = абсорбирование ликвидности ЦБ.",
        "> Прочерк в графе недельных или тонкой настройки означает отсутствие аукционов на эту дату.",
        "> Данные приводятся **на начало дня**, т.е. отражают позицию до операций текущего дня.",
    ]
    return "\n".join(lines)


def s2_section(df: pd.DataFrame) -> str:
    lines = [
        "## S2. Среднедневные обороты рынка МБК и РЕПО",
        "",
        "**Источник:** https://www.cbr.ru/statistics/finr (раздел «Показатели оборота денежного рынка»)  ",
        "**Тип показателя:** поток (flow) — средний дневной оборот за месяц  ",
        "**Охват:** рыночный оборот (RUB), не позиции отдельных банков  ",
        "**Единица:** млн руб.  ",
        "",
        "> ⚠️ **Нельзя суммировать** обороты МБК и РЕПО из S2 с депозитами ЦБ из S1 — разные типы показателей.",
        "",
    ]
    if "instrument" in df.columns:
        for instrument in ["MBK", "REPO"]:
            inst_name = "МБК (межбанковские кредиты/депозиты)" if instrument == "MBK" else "РЕПО"
            lines.append(f"### {inst_name} — среднедневные обороты (млн руб.)")
            lines.append("")
            lines.append("| Год | Месяц | Всего (все сроки) | Овернайт |")
            lines.append("|---|---|---:|---:|")
            grp = df[df["instrument"] == instrument]
            for (year, month), sub in grp.groupby(["year", "period_label"], sort=False):
                total_val = sub[sub.get("term", "all") == "all"]["avg_daily_value"].values
                ovn_val = sub[sub.get("term", "") == "overnight"]["avg_daily_value"].values
                t_str = f"{total_val[0]:,.1f}" if len(total_val) and pd.notna(total_val[0]) else "н/д"
                o_str = f"{ovn_val[0]:,.1f}" if len(ovn_val) and pd.notna(ovn_val[0]) else "н/д"
                lines.append(f"| {int(year)} | {month} | {t_str} | {o_str} |")
            lines.append("")
    else:
        lines.append("*Структура файла нестандартна — см. data/raw/s2_turnover_*.xlsx*")

    return "\n".join(lines)


def s3_section(df: pd.DataFrame) -> str:
    df = df.sort_values("reference_date", ascending=False)
    latest = df.iloc[0]
    date_str = latest["reference_date"].strftime("%d.%m.%Y")
    lines = [
        "## S3. RUONIA — однодневный МБК",
        "",
        "**Источник:** https://www.cbr.ru/hd_base/ruonia/dynamics/  ",
        "**Тип показателя:** поток (flow) — объём и ставка за дату расчёта  ",
        "**Охват:** ВЫБОРКА подходящих сделок overnight МБК, НЕ весь рынок  ",
        "",
        f"### Последнее наблюдение ({date_str})",
        "",
        "| Показатель | Значение |",
        "|---|---|",
        f"| Ставка RUONIA | {latest.get('ruonia_rate_pct', float('nan')):.2f}% годовых |",
        f"| Объём учтённых сделок | {fmt_bln(latest.get('volume_bln', float('nan')))} |",
        f"| Количество сделок | {int(latest.get('trade_count', 0)) if pd.notna(latest.get('trade_count')) else 'н/д'} |",
        f"| Участников | {int(latest.get('participant_count', 0)) if pd.notna(latest.get('participant_count')) else 'н/д'} |",
        "",
        "### Динамика (последние 15 дней)",
        "",
        "| Дата | Ставка (%) | Объём (млрд руб.) | Сделок | Участников |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in df.head(15).iterrows():
        d = row["reference_date"].strftime("%d.%m.%Y")
        r = row.get("ruonia_rate_pct", float("nan"))
        v = row.get("volume_bln", float("nan"))
        tc = row.get("trade_count")
        pc = row.get("participant_count")
        lines.append(
            f"| {d} | {r:.2f} | {v:,.2f} | "
            f"{'н/д' if pd.isna(tc) else int(tc)} | "
            f"{'н/д' if pd.isna(pc) else int(pc)} |"
        )

    lines += [
        "",
        "> **Ограничение:** объём RUONIA ≠ весь рынок overnight МБК. RUONIA охватывает только",
        "> сделки крупных банков, отвечающие методологии индикатора.",
    ]
    return "\n".join(lines)


def s4_section(df: pd.DataFrame) -> str:
    lines = [
        "## S4. РЕПО Банка России: аукционы (контекст — предоставление ликвидности ЦБ)",
        "",
        "**Источник:** https://www.cbr.ru/hd_base/repo/  ",
        "**Тип показателя:** результат аукциона (flow) — объём заключённых сделок  ",
        "",
        "> Внимание: РЕПО ЦБ = **ЦБ даёт деньги банкам** (предоставление ликвидности).",
        "> Не включать в сумму «размещений банков».",
        "",
    ]
    if "reference_date" in df.columns:
        df = df.sort_values("reference_date", ascending=False)
        lines += [
            "| Дата | Объём спроса (млн руб.) | Заключено (млн руб.) | Ставка (%) | Срок (дн.) |",
            "|---|---:|---:|---:|---:|",
        ]
        for _, row in df.head(10).iterrows():
            d = row["reference_date"].strftime("%d.%m.%Y") if pd.notna(row["reference_date"]) else "н/д"
            dem = row.get("demand_mn", float("nan"))
            con = row.get("concluded_mn", float("nan"))
            rate = row.get("rate_pct", float("nan"))
            term = row.get("term_days", float("nan"))
            lines.append(
                f"| {d} | {'н/д' if pd.isna(dem) else f'{dem:,.1f}'} | "
                f"{'н/д' if pd.isna(con) else f'{con:,.1f}'} | "
                f"{'н/д' if pd.isna(rate) else f'{rate:.2f}'} | "
                f"{'н/д' if pd.isna(term) else int(term)} |"
            )
    else:
        lines.append("*Данные S4 получены в нестандартном формате — см. data/processed/s4.csv*")
    return "\n".join(lines)


def s7_section(df: pd.DataFrame) -> str:
    lines = [
        "## S7. Форма 101 — остатки по счетам ликвидности отдельных банков",
        "",
        "**Источник:** https://www.cbr.ru/banking_sector/otchetnost-kreditnykh-organizaciy/  ",
        "**Тип показателя:** остаток (stock) на отчётную дату  ",
        "**Единица:** тыс. руб.  ",
        "",
        "> ⚠️ **Регуляторное ограничение 2026 г.** (Решение ЦБ от 19.12.2025):",
        "> раскрываются только счета первого порядка; 320+321 — только агрегат.",
        "> Разделить российских/иностранных контрагентов из публичного Ф-101 **невозможно**.",
        "",
    ]
    if df.empty:
        lines.append("*Данные не загружены (rarfile/dbfread не установлены или ошибка доступа)*")
        return "\n".join(lines)

    # Топ-20 банков по счёту 319 на последнюю дату (активный остаток)
    latest_date = df["reference_date"].max()
    df_latest = df[df["reference_date"] == latest_date]
    date_str = latest_date.strftime("%d.%m.%Y") if pd.notna(latest_date) else "н/д"

    acct319 = df_latest[df_latest["num_sc"].astype(str).str.startswith("319") & (df_latest["a_p"].astype(str) == "1")]
    acct320 = df_latest[df_latest["num_sc"].astype(str).str.startswith(("320", "32.1")) & (df_latest["a_p"].astype(str) == "1")]

    lines.append(f"### Счёт 319 (депозиты в ЦБ) — топ-20 банков на {date_str}")
    lines.append("")
    lines.append("| # | Банк (REGN) | Название | Остаток (тыс. руб.) |")
    lines.append("|---|---|---|---:|")
    top319 = acct319.nlargest(20, "iitg_thou")
    for i, (_, row) in enumerate(top319.iterrows(), 1):
        lines.append(f"| {i} | {row['regn']} | {row['bank_name'][:60]} | {row['iitg_thou']:,.0f} |")

    lines.append("")
    lines.append(f"### Агрегат 320+321 / '32.1' (МБК размещённые, рез+нерез) — топ-20 банков на {date_str}")
    lines.append("")
    lines.append("| # | Банк (REGN) | Название | Остаток (тыс. руб.) |")
    lines.append("|---|---|---|---:|")
    top320 = acct320.nlargest(20, "iitg_thou")
    for i, (_, row) in enumerate(top320.iterrows(), 1):
        lines.append(f"| {i} | {row['regn']} | {row['bank_name'][:60]} | {row['iitg_thou']:,.0f} |")

    return "\n".join(lines)


def answers_section() -> str:
    return """## Ответы на ключевые вопросы исследования

| Вопрос | Ответ |
|---|---|
| Размер остатков на депозитах в ЦБ? | Берётся из S1; на 29.10.2026 ≈ 3 877 млрд руб. — весь объём в овернайте |
| Депозиты недельные / тонкой настройки? | На 29.10.2026 — прочерк (аукционы не проводились в эту дату) |
| Объём рынка RUONIA overnight? | Из S3: на 28.10.2026 = 992,86 млрд руб. за день (выборка ~22 банка) |
| Почему S1 и S3 нельзя сравнивать напрямую? | S1 — остаток ЦБ-депозитов (stock), S3 — объём сделок RUONIA-выборки (flow) |
| Обороты МБК и РЕПО? | S2: среднедневные значения по рынку в целом, доступны по месяцам |
| Данные по отдельным банкам? | S7 (Ф-101): счёт 319, агрегат 320+321. В 2026 г. нет детализации по резидентности |
| РЕПО ЦБ = размещение банков? | Нет. РЕПО ЦБ = ЦБ кредитует банки. Показывается как контекст (S4) |
| Можно ли выделить нерезидентов в 2026? | Нет — публичный Ф-101 раскрывает только агрегат 320+321 |
"""


def generate_report(dfs: dict) -> str:
    sections = [
        f"# Аналитическая сводка: ликвидность банков РФ",
        f"",
        f"**Дата генерации:** {NOW}  ",
        f"**Охват:** 2025–2026 гг.  ",
        f"**Источники:** Банк России (S1–S7)  ",
        f"",
        answers_section(),
        "---",
        "",
    ]

    if dfs.get("S1") is not None and not dfs["S1"].empty:
        sections.append(s1_section(dfs["S1"]))
        sections.append("\n---\n")

    if dfs.get("S2") is not None and not dfs["S2"].empty:
        sections.append(s2_section(dfs["S2"]))
        sections.append("\n---\n")

    if dfs.get("S3") is not None and not dfs["S3"].empty:
        sections.append(s3_section(dfs["S3"]))
        sections.append("\n---\n")

    if dfs.get("S4") is not None and not dfs["S4"].empty:
        sections.append(s4_section(dfs["S4"]))
        sections.append("\n---\n")

    if dfs.get("S7") is not None and not dfs["S7"].empty:
        sections.append(s7_section(dfs["S7"]))
    else:
        sections.append("## S7. Форма 101\n\n*Данные не загружены*")

    return "\n".join(sections)


def main() -> None:
    dfs = {}
    for name in ["S1", "S2", "S3", "S4", "S7"]:
        df = load(name.lower())
        dfs[name] = df
        status = f"{len(df)} rows" if df is not None and not df.empty else "empty"
        print(f"Loaded {name}: {status}")

    report = generate_report(dfs)

    out = RESULTS / "report.md"
    out.write_text(report, encoding="utf-8")
    print(f"\nReport → {out}")

    # Также сводная таблица в CSV для машинной обработки
    summary_rows = []
    s1 = dfs.get("S1")
    if s1 is not None and not s1.empty:
        latest = s1.sort_values("reference_date", ascending=False).iloc[0]
        summary_rows.append({
            "source_id": "S1", "metric_id": "total_deposits_cbr",
            "metric_name": "Депозиты банков в ЦБ — всего",
            "observation_type": "stock", "money_direction": "bank_places_in_cbr",
            "reference_date": latest["reference_date"],
            "value": latest.get("total_mn"), "unit": "млн руб.",
            "source_url": "https://www.cbr.ru/hd_base/ostat_depo_new/",
            "note": "остаток на начало дня"
        })
        summary_rows.append({
            "source_id": "S1", "metric_id": "overnight_cbr",
            "metric_name": "Депозиты банков в ЦБ — овернайт",
            "observation_type": "stock", "money_direction": "bank_places_in_cbr",
            "reference_date": latest["reference_date"],
            "value": latest.get("overnight_mn"), "unit": "млн руб.",
            "source_url": "https://www.cbr.ru/hd_base/ostat_depo_new/",
            "note": "овернайт постоянного действия, остаток на начало дня"
        })

    s3 = dfs.get("S3")
    if s3 is not None and not s3.empty:
        latest3 = s3.sort_values("reference_date", ascending=False).iloc[0]
        summary_rows.append({
            "source_id": "S3", "metric_id": "ruonia_rate",
            "metric_name": "RUONIA ставка",
            "observation_type": "flow", "money_direction": "ruonia_sample_only",
            "reference_date": latest3["reference_date"],
            "value": latest3.get("ruonia_rate_pct"), "unit": "% годовых",
            "source_url": "https://www.cbr.ru/hd_base/ruonia/dynamics/",
            "note": "НЕ вся ставка рынка overnight МБК"
        })
        summary_rows.append({
            "source_id": "S3", "metric_id": "ruonia_volume",
            "metric_name": "Объём сделок RUONIA",
            "observation_type": "flow", "money_direction": "ruonia_sample_only",
            "reference_date": latest3["reference_date"],
            "value": latest3.get("volume_bln"), "unit": "млрд руб.",
            "source_url": "https://www.cbr.ru/hd_base/ruonia/dynamics/",
            "note": "ВЫБОРКА overnight МБК, не весь рынок"
        })

    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(RESULTS / "summary_latest.csv", index=False, encoding="utf-8-sig")
        print(f"Summary → {RESULTS / 'summary_latest.csv'}")


if __name__ == "__main__":
    main()
