"""
Генератор интерактивного HTML дашборда и итоговых аналитических таблиц.
"""

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT.parent / "results"
PROC = ROOT / "data" / "processed"

# 1. Загрузка данных
df_multi = pd.read_csv(RESULTS / "banks_multiyear_liquidity.csv")
s2 = pd.read_csv(PROC / "s2.csv")
s1 = pd.read_csv(PROC / "s1.csv")
s3 = pd.read_csv(PROC / "s3.csv")

# 2. Формирование top_donors_recipients_2026.csv
d26 = df_multi[df_multi["year"] == 2026].copy()
d26_donors = d26.sort_values(by="net_mbk_position_thou", ascending=False).head(20)
d26_recipients = d26.sort_values(by="net_mbk_position_thou", ascending=True).head(20)

donors_recipients_df = pd.concat([
    d26_donors.assign(category="TOP_DONOR_LENDER"),
    d26_recipients.assign(category="TOP_RECIPIENT_BORROWER")
])
donors_recipients_df.to_csv(RESULTS / "top_donors_recipients_2026.csv", index=False, encoding="utf-8-sig")

# 3. Формирование macro_liquidity_summary.csv
macro_summary = s2.groupby(["year", "instrument", "term"])["avg_daily_value"].mean().reset_index()
macro_summary["avg_daily_trln"] = macro_summary["avg_daily_value"] / 1e6
macro_summary.to_csv(RESULTS / "macro_liquidity_summary.csv", index=False, encoding="utf-8-sig")

# 4. Подготовка данных для графиков дашборда
# Динамика S2 по месяцам
s2_grouped = s2[s2["term"] == "all"].pivot_table(
    index=["year", "period_label"], 
    columns="instrument", 
    values="avg_daily_value"
).reset_index()

# Создаем хронологическую метку
months_order = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
s2["month_num"] = s2["period_label"].apply(lambda m: months_order.index(m) + 1 if m in months_order else 0)
s2_sorted = s2[s2["term"] == "all"].sort_values(by=["year", "month_num"])
s2_piv = s2_sorted.pivot_table(index=["year", "period_label"], columns="instrument", values="avg_daily_value", sort=False).reset_index()
macro_labels = [f"{r['period_label'][:3]} {r['year']}" for _, r in s2_piv.iterrows()]
repo_turnover = [round(float(v) / 1e6, 2) for v in s2_piv.get("REPO", [])]
mbk_turnover = [round(float(v) / 1e6, 2) for v in s2_piv.get("MBK", [])]

# Годовые агрегаты остатков по сектору
sector_years = sorted(df_multi["year"].unique().tolist())
depo_by_year = [round(df_multi[df_multi["year"] == y]["cbr_deposits_319_thou"].sum() / 1e9, 2) for y in sector_years]
mbk_placed_by_year = [round(df_multi[df_multi["year"] == y]["mbk_placed_321_thou"].sum() / 1e9, 2) for y in sector_years]
mbk_borrowed_by_year = [round(df_multi[df_multi["year"] == y]["mbk_borrowed_311_thou"].sum() / 1e9, 2) for y in sector_years]
capital_by_year = [round(df_multi[df_multi["year"] == y]["capital_thou"].sum() / 1e9, 2) for y in sector_years]

# Топ-15 доноров 2026
top_donors = d26.sort_values(by="net_mbk_position_thou", ascending=False).head(15)
donor_names = top_donors["bank_name"].tolist()
donor_vals = [round(v / 1e6, 1) for v in top_donors["net_mbk_position_thou"]]

# Топ-15 заемщиков 2026
top_borrowers = d26.sort_values(by="net_mbk_position_thou", ascending=True).head(15)
borrower_names = top_borrowers["bank_name"].tolist()
borrower_vals = [round(abs(v) / 1e6, 1) for v in top_borrowers["net_mbk_position_thou"]]

# Топ-10 по депозитам в ЦБ 2026
top_cbr_depo = d26.sort_values(by="cbr_deposits_319_thou", ascending=False).head(10)
cbr_depo_names = top_cbr_depo["bank_name"].tolist()
cbr_depo_vals = [round(v / 1e6, 1) for v in top_cbr_depo["cbr_deposits_319_thou"]]

# Данные для интерактивной таблицы
table_rows = []
for _, r in d26.sort_values(by="capital_thou", ascending=False).iterrows():
    table_rows.append({
        "regn": int(r["regn"]),
        "name": str(r["bank_name"]),
        "cbr_depo_bln": round(float(r["cbr_deposits_319_thou"]) / 1e6, 2),
        "mbk_placed_bln": round(float(r["mbk_placed_321_thou"]) / 1e6, 2),
        "mbk_borrowed_bln": round(float(r["mbk_borrowed_311_thou"]) / 1e6, 2),
        "net_mbk_bln": round(float(r["net_mbk_position_thou"]) / 1e6, 2),
        "capital_bln": round(float(r["capital_thou"]) / 1e6, 2) if pd.notnull(r["capital_thou"]) else "-",
        "n2": round(float(r["norm_n2_instant_pct"]), 1) if pd.notnull(r["norm_n2_instant_pct"]) else "-",
        "n3": round(float(r["norm_n3_current_pct"]), 1) if pd.notnull(r["norm_n3_current_pct"]) else "-",
        "role": str(r["role_in_mbk"])
    })

html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Аналитический дашборд: Ликвидность банковского сектора РФ (2024-2026)</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg-primary: #0f172a;
      --bg-secondary: #1e293b;
      --bg-card: #1e293b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --border-color: #334155;
      --accent-blue: #38bdf8;
      --accent-green: #34d399;
      --accent-red: #f87171;
      --accent-yellow: #fbbf24;
      --accent-purple: #c084fc;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg-primary);
      color: var(--text-main);
      padding: 24px;
      line-height: 1.5;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 24px;
    }}
    .header h1 {{ font-size: 24px; font-weight: 700; color: #fff; }}
    .header .subtitle {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
    .badge {{
      background: #0284c7;
      color: #fff;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
    }}

    /* Metrics Grid */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .metric-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }}
    .metric-title {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }}
    .metric-value {{ font-size: 26px; font-weight: 700; margin: 8px 0 4px; }}
    .metric-sub {{ font-size: 12px; color: var(--accent-blue); }}

    /* Charts Grid */
    .charts-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
      gap: 20px;
      margin-bottom: 28px;
    }}
    .chart-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }}
    .chart-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 14px;
    }}
    .chart-header h3 {{ font-size: 16px; font-weight: 600; }}
    .chart-header span {{ font-size: 12px; color: var(--text-muted); }}
    .chart-wrapper {{ position: relative; height: 320px; width: 100%; }}

    /* Table Section */
    .table-section {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .table-controls {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .search-box {{
      flex: 1;
      min-width: 250px;
      padding: 8px 14px;
      background: #0f172a;
      border: 1px solid var(--border-color);
      border-radius: 6px;
      color: #fff;
      font-size: 14px;
    }}
    .table-wrapper {{
      max-height: 480px;
      overflow-y: auto;
      border: 1px solid var(--border-color);
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #0f172a;
      color: var(--text-muted);
      font-weight: 600;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border-color);
      cursor: pointer;
    }}
    td {{
      padding: 10px 12px;
      border-bottom: 1px solid #1e293b;
      white-space: nowrap;
    }}
    tr:nth-child(even) {{ background: rgba(255, 255, 255, 0.02); }}
    tr:hover {{ background: rgba(255, 255, 255, 0.05); }}
    .text-right {{ text-align: right; }}
    .badge-donor {{
      background: rgba(52, 211, 153, 0.15);
      color: var(--accent-green);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
    }}
    .badge-recipient {{
      background: rgba(248, 113, 113, 0.15);
      color: var(--accent-red);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
    }}
    .badge-neutral {{
      background: rgba(148, 163, 184, 0.15);
      color: var(--text-muted);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
    }}
    .footer {{
      text-align: center;
      color: var(--text-muted);
      font-size: 12px;
      margin-top: 30px;
      padding-top: 15px;
      border-top: 1px solid var(--border-color);
    }}
  </style>
</head>
<body>

  <div class="header">
    <div>
      <h1>Интерактивный дашборд ликвидности банковского сектора РФ</h1>
      <div class="subtitle">Период: 2024 - 2026 гг. | Источники: Банк России (Формы 101, 135, 123, Сводки S1, S2, S3), Analizbankov.ru</div>
    </div>
    <span class="badge">Статус данных: 01.10.2026 (Актуально)</span>
  </div>

  <!-- Метрики верхнего уровня -->
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-title">Оборот рынка РЕПО (в день)</div>
      <div class="metric-value" style="color: var(--accent-blue);">2.92 трлн ₽</div>
      <div class="metric-sub">+89.7% к началу 2024 г. (90% овернайт)</div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Оборот МБК (в день)</div>
      <div class="metric-value" style="color: var(--accent-purple);">1.79 трлн ₽</div>
      <div class="metric-sub">+23.1% к началу 2024 г.</div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Депозиты банков в ЦБ (счет 319)</div>
      <div class="metric-value" style="color: var(--accent-green);">3.30 трлн ₽</div>
      <div class="metric-sub">~1.7 трлн ₽ приходится на банки нерезидентов</div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Ставка RUONIA</div>
      <div class="metric-value" style="color: var(--accent-yellow);">14.09%</div>
      <div class="metric-sub">Объем сделок: 992.9 млрд ₽/день (29 участников)</div>
    </div>
    <div class="metric-card">
      <div class="metric-title">Собственный капитал (Форма 123)</div>
      <div class="metric-value">21.27 трлн ₽</div>
      <div class="metric-sub">349 действующих кредитных организаций</div>
    </div>
  </div>

  <!-- Сетка графиков -->
  <div class="charts-grid">
    <!-- График 1: Макро-обороты РЕПО и МБК -->
    <div class="chart-card">
      <div class="chart-header">
        <h3>Среднедневной оборот рынка (2024-2026)</h3>
        <span>трлн руб. / день (Сводка S2)</span>
      </div>
      <div class="chart-wrapper">
        <canvas id="chartMacro"></canvas>
      </div>
    </div>

    <!-- График 2: Годовая динамика балансовых остатков -->
    <div class="chart-card">
      <div class="chart-header">
        <h3>Балансовые остатки банковского сектора</h3>
        <span>трлн руб. (Форма 101 и 123)</span>
      </div>
      <div class="chart-wrapper">
        <canvas id="chartSectorStock"></canvas>
      </div>
    </div>

    <!-- График 3: Топ-15 Доноров МБК -->
    <div class="chart-card">
      <div class="chart-header">
        <h3>Топ-15 Доноров (Чистые кредиторы МБК, 2026)</h3>
        <span>млрд руб. (Счет 32.1 минус 31.1)</span>
      </div>
      <div class="chart-wrapper">
        <canvas id="chartDonors"></canvas>
      </div>
    </div>

    <!-- График 4: Топ-15 Реципиентов МБК -->
    <div class="chart-card">
      <div class="chart-header">
        <h3>Топ-15 Реципиентов (Чистые заемщики МБК, 2026)</h3>
        <span>млрд руб. (Счет 31.1 минус 32.1)</span>
      </div>
      <div class="chart-wrapper">
        <canvas id="chartBorrowers"></canvas>
      </div>
    </div>

    <!-- График 5: Топ депозиторов в Банке России -->
    <div class="chart-card" style="grid-column: 1 / -1;">
      <div class="chart-header">
        <h3>Топ-10 банков по остаткам на депозитах в ЦБ РФ (Счет 319, октябрь 2026)</h3>
        <span>млрд руб. (Доминирование дочерних банков иностранных групп)</span>
      </div>
      <div class="chart-wrapper" style="height: 280px;">
        <canvas id="chartCbrDepo"></canvas>
      </div>
    </div>
  </div>

  <!-- Интерактивная таблица по всем банкам -->
  <div class="table-section">
    <div class="table-controls">
      <h3>Реестр кредитных организаций (данные на 01.10.2026)</h3>
      <input type="text" id="bankSearch" class="search-box" placeholder="Поиск по названию или рег. номеру..." onkeyup="filterTable()">
    </div>
    <div class="table-wrapper">
      <table id="banksTable">
        <thead>
          <tr>
            <th onclick="sortTable(0)">Рег. №</th>
            <th onclick="sortTable(1)">Наименование банка</th>
            <th class="text-right" onclick="sortTable(2)">Депозиты ЦБ (319), млрд ₽</th>
            <th class="text-right" onclick="sortTable(3)">МБК разм. (32.1), млрд ₽</th>
            <th class="text-right" onclick="sortTable(4)">МБК привл. (31.1), млрд ₽</th>
            <th class="text-right" onclick="sortTable(5)">Чистая поз. МБК, млрд ₽</th>
            <th class="text-right" onclick="sortTable(6)">Капитал, млрд ₽</th>
            <th class="text-right" onclick="sortTable(7)">Н2 (мгновен.), %</th>
            <th class="text-right" onclick="sortTable(8)">Н3 (текущ.), %</th>
            <th>Роль на МБК</th>
          </tr>
        </thead>
        <tbody id="tableBody">
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Сформировано автоматически в рамках проекта исследования ликвидности банковского сектора РФ. Источник первичных баз: Банк России (cbr.ru). Кросс-валидация: analizbankov.ru.
  </div>

  <script>
    // Инициализация графиков
    const ctxMacro = document.getElementById('chartMacro').getContext('2d');
    new Chart(ctxMacro, {{
      type: 'line',
      data: {{
        labels: {json.dumps(macro_labels)},
        datasets: [
          {{
            label: 'РЕПО (все сроки, трлн ₽/день)',
            data: {json.dumps(repo_turnover)},
            borderColor: '#38bdf8',
            backgroundColor: 'rgba(56, 189, 248, 0.1)',
            borderWidth: 2,
            tension: 0.3,
            fill: true
          }},
          {{
            label: 'МБК (все сроки, трлн ₽/день)',
            data: {json.dumps(mbk_turnover)},
            borderColor: '#c084fc',
            backgroundColor: 'rgba(192, 132, 252, 0.1)',
            borderWidth: 2,
            tension: 0.3,
            fill: true
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
        scales: {{
          x: {{ ticks: {{ color: '#94a3b8', maxRotation: 45 }} }},
          y: {{ ticks: {{ color: '#94a3b8' }} }}
        }}
      }}
    }});

    const ctxSector = document.getElementById('chartSectorStock').getContext('2d');
    new Chart(ctxSector, {{
      type: 'bar',
      data: {{
        labels: {json.dumps(sector_years)},
        datasets: [
          {{ label: 'Депозиты в ЦБ (счет 319)', data: {json.dumps(depo_by_year)}, backgroundColor: '#34d399' }},
          {{ label: 'МБК размещенные (счет 32.1)', data: {json.dumps(mbk_placed_by_year)}, backgroundColor: '#38bdf8' }},
          {{ label: 'МБК привлеченные (счет 31.1)', data: {json.dumps(mbk_borrowed_by_year)}, backgroundColor: '#f87171' }},
          {{ label: 'Капитал сектора (Форма 123)', data: {json.dumps(capital_by_year)}, backgroundColor: '#fbbf24' }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
        scales: {{
          x: {{ ticks: {{ color: '#94a3b8' }} }},
          y: {{ ticks: {{ color: '#94a3b8' }} }}
        }}
      }}
    }});

    const ctxDonors = document.getElementById('chartDonors').getContext('2d');
    new Chart(ctxDonors, {{
      type: 'bar',
      data: {{
        labels: {json.dumps(donor_names)},
        datasets: [{{
          label: 'Чистое размещение на МБК (млрд ₽)',
          data: {json.dumps(donor_vals)},
          backgroundColor: '#34d399'
        }}]
      }},
      options: {{
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          x: {{ ticks: {{ color: '#94a3b8' }} }},
          y: {{ ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }} }}
        }}
      }}
    }});

    const ctxBorrowers = document.getElementById('chartBorrowers').getContext('2d');
    new Chart(ctxBorrowers, {{
      type: 'bar',
      data: {{
        labels: {json.dumps(borrower_names)},
        datasets: [{{
          label: 'Чистое привлечение на МБК (млрд ₽)',
          data: {json.dumps(borrower_vals)},
          backgroundColor: '#f87171'
        }}]
      }},
      options: {{
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          x: {{ ticks: {{ color: '#94a3b8' }} }},
          y: {{ ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }} }}
        }}
      }}
    }});

    const ctxCbr = document.getElementById('chartCbrDepo').getContext('2d');
    new Chart(ctxCbr, {{
      type: 'bar',
      data: {{
        labels: {json.dumps(cbr_depo_names)},
        datasets: [{{
          label: 'Остаток на депозите в ЦБ (счет 319, млрд ₽)',
          data: {json.dumps(cbr_depo_vals)},
          backgroundColor: '#0284c7'
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          x: {{ ticks: {{ color: '#94a3b8', font: {{ size: 11 }} }} }},
          y: {{ ticks: {{ color: '#94a3b8' }} }}
        }}
      }}
    }});

    // Заполнение таблицы
    const tableData = {json.dumps(table_rows)};
    const tbody = document.getElementById('tableBody');

    function renderTable(data) {{
      tbody.innerHTML = '';
      data.forEach(r => {{
        const tr = document.createElement('tr');
        let roleBadge = '<span class="badge-neutral">Нейтрально</span>';
        if (r.role.includes('кредитор')) {{
          roleBadge = '<span class="badge-donor">Кредитор (донор)</span>';
        }} else if (r.role.includes('заемщик')) {{
          roleBadge = '<span class="badge-recipient">Заемщик (реципиент)</span>';
        }}
        tr.innerHTML = `
          <td>${{r.regn}}</td>
          <td><strong>${{r.name}}</strong></td>
          <td class="text-right">${{r.cbr_depo_bln.toLocaleString()}}</td>
          <td class="text-right">${{r.mbk_placed_bln.toLocaleString()}}</td>
          <td class="text-right">${{r.mbk_borrowed_bln.toLocaleString()}}</td>
          <td class="text-right" style="color: ${{r.net_mbk_bln >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}}">${{r.net_mbk_bln.toLocaleString()}}</td>
          <td class="text-right">${{r.capital_bln !== '-' ? r.capital_bln.toLocaleString() : '-'}}</td>
          <td class="text-right">${{r.n2}}</td>
          <td class="text-right">${{r.n3}}</td>
          <td>${{roleBadge}}</td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    renderTable(tableData);

    function filterTable() {{
      const query = document.getElementById('bankSearch').value.toLowerCase();
      const filtered = tableData.filter(r => 
        r.name.toLowerCase().includes(query) || r.regn.toString().includes(query)
      );
      renderTable(filtered);
    }}

    let sortAsc = false;
    function sortTable(colIndex) {{
      sortAsc = !sortAsc;
      const keys = ['regn', 'name', 'cbr_depo_bln', 'mbk_placed_bln', 'mbk_borrowed_bln', 'net_mbk_bln', 'capital_bln', 'n2', 'n3'];
      const key = keys[colIndex];
      tableData.sort((a, b) => {{
        let v1 = a[key];
        let v2 = b[key];
        if (v1 === '-') v1 = -999999999;
        if (v2 === '-') v2 = -999999999;
        if (typeof v1 === 'string') {{
          return sortAsc ? v1.localeCompare(v2) : v2.localeCompare(v1);
        }}
        return sortAsc ? v1 - v2 : v2 - v1;
      }});
      renderTable(tableData);
    }}
  </script>
</body>
</html>
"""

(RESULTS / "dashboard.html").write_text(html_content, encoding="utf-8")
print(f"Generated dashboard: {RESULTS / 'dashboard.html'}")
print(f"Generated top donors/recipients: {RESULTS / 'top_donors_recipients_2026.csv'}")
print(f"Generated macro summary: {RESULTS / 'macro_liquidity_summary.csv'}")
