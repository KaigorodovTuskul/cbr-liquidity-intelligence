"""
Сбор данных ликвидности банков РФ из открытых источников ЦБ.
Источники: S1 (депозиты в ЦБ), S2 (обороты МБК/РЕПО), S3 (RUONIA),
           S4 (РЕПО ЦБ аукционы), S5 (РЕПО ЦБ пост. действия).
Выход: data/processed/*.csv  + data/raw/ (скачанные файлы).
Запуск: python scripts/fetch_cbr_liquidity.py
"""

import asyncio
import io
import os
import re
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
ARCH = ROOT / "data" / "archives"
RAW.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)
ARCH.mkdir(parents=True, exist_ok=True)

ACCESSED_AT = datetime.now(timezone.utc).isoformat()

# Реквизиты запросов: минимальный браузерный UA чтобы ЦБ не вернул 403
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; cbr-liquidity-fetcher/1.0)",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

TIMEOUT = aiohttp.ClientTimeout(total=120)


# ─────────────────────────── helpers ────────────────────────────────────────

async def get(session: aiohttp.ClientSession, url: str) -> bytes:
    async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as r:
        r.raise_for_status()
        return await r.read()


async def download_file(session: aiohttp.ClientSession, url: str, dest: Path) -> Path:
    """Качает url → dest, пропускает если файл уже есть."""
    if dest.exists():
        return dest
    content = await get(session, url)
    dest.write_bytes(content)
    return dest


# ─────────────────────────── S1: депозиты банков в ЦБ ───────────────────────

S1_URL = "https://www.cbr.ru/hd_base/ostat_depo_new/"
S1_DATA_URL = "https://www.cbr.ru/Queries/UniDbQuery/DownloadExcel/135393?Posted=True&so=1&oo=1&UniDbQuery.Posted=True&UniDbQuery.so=1&UniDbQuery.oo=1&UniDbQuery.From=01.01.2025&UniDbQuery.To=31.12.2026"


async def fetch_s1(session: aiohttp.ClientSession) -> pd.DataFrame:
    """Депозиты кредитных организаций в Банке России."""
    print("S1: fetching deposits in CBR...")
    # Сначала парсим страницу чтобы найти ссылку на скачивание
    html = (await get(session, S1_URL)).decode("utf-8", errors="replace")

    # Ищем Excel-ссылку на странице
    xlsx_match = re.search(r'href="([^"]*DownloadExcel[^"]*)"', html)
    if xlsx_match:
        xlsx_url = xlsx_match.group(1)
        if not xlsx_url.startswith("http"):
            xlsx_url = "https://www.cbr.ru" + xlsx_url
    else:
        xlsx_url = S1_DATA_URL  # fallback

    raw_path = RAW / "s1_deposits_cbr.xlsx"
    try:
        await download_file(session, xlsx_url, raw_path)
        df = pd.read_excel(raw_path, engine="openpyxl", header=None)
    except Exception as e:
        print(f"S1: Excel download failed ({e}), trying HTML table parse...")
        # Fallback: парсим HTML-таблицу
        tables = pd.read_html(io.StringIO(html), decimal=",", thousands=None)
        if not tables:
            raise RuntimeError("S1: no tables found in HTML")
        df = tables[0]
        df.to_csv(RAW / "s1_deposits_cbr_raw.csv", index=False, encoding="utf-8-sig")
        # Нормализуем
        return _normalize_s1_html(df)

    return _normalize_s1_excel(df)


def _normalize_s1_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Ищет строку с датой и числами, нормализует колонки."""
    # Пропускаем заголовочные строки (ищем первую строку где первый элемент — дата)
    header_row = 0
    for i, row in df.iterrows():
        val = str(row.iloc[0]).strip()
        if re.match(r"\d{2}\.\d{2}\.\d{4}", val):
            header_row = i
            break
    data = df.iloc[header_row:].copy()
    data.columns = range(len(data.columns))
    data = data.rename(columns={
        0: "date_raw",
        1: "total_mn",
        2: "weekly_auction_mn",
        3: "fine_tuning_mn",
        4: "overnight_mn",
    })
    data = data.dropna(subset=["date_raw"])
    data["reference_date"] = pd.to_datetime(data["date_raw"], dayfirst=True, errors="coerce")
    data = data.dropna(subset=["reference_date"])

    for col in ["total_mn", "weekly_auction_mn", "fine_tuning_mn", "overnight_mn"]:
        data[col] = pd.to_numeric(
            data[col].astype(str).str.replace(r"[^\d,.\-]", "", regex=True).str.replace(",", "."),
            errors="coerce"
        )

    data["source_id"] = "S1"
    data["unit"] = "млн руб."
    data["observation_type"] = "stock"
    data["money_direction"] = "bank_places_in_cbr"
    data["source_url"] = S1_URL
    data["accessed_at"] = ACCESSED_AT

    return data[["reference_date", "total_mn", "weekly_auction_mn", "fine_tuning_mn",
                 "overnight_mn", "source_id", "unit", "observation_type",
                 "money_direction", "source_url", "accessed_at"]]


def _normalize_s1_html(df: pd.DataFrame) -> pd.DataFrame:
    """HTML-таблица S1 имеет MultiIndex — сразу задаём плоские имена."""
    df = df.copy()
    df.columns = ["date_raw", "total_mn", "weekly_auction_mn", "fine_tuning_mn", "overnight_mn"]
    # Оставляем только строки с датой
    df = df[df["date_raw"].astype(str).str.match(r"\d{2}\.\d{2}\.\d{4}", na=False)].copy()
    df["reference_date"] = pd.to_datetime(df["date_raw"].astype(str), dayfirst=True, errors="coerce")
    df = df.dropna(subset=["reference_date"])
    # Прочерки и пробелы-разделители тысяч
    for col in ["total_mn", "weekly_auction_mn", "fine_tuning_mn", "overnight_mn"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r"\s", "", regex=True).str.replace(",", "."),
            errors="coerce"
        )
    df["source_id"] = "S1"
    df["unit"] = "млн руб."
    df["observation_type"] = "stock"
    df["money_direction"] = "bank_places_in_cbr"
    df["source_url"] = S1_URL
    df["accessed_at"] = ACCESSED_AT
    return df[["reference_date", "total_mn", "weekly_auction_mn", "fine_tuning_mn",
               "overnight_mn", "source_id", "unit", "observation_type",
               "money_direction", "source_url", "accessed_at"]]


# ─────────────────────────── S2: обороты МБК и РЕПО ─────────────────────────

S2_BASE = "https://www.cbr.ru/vfs/statistics/credit_statistics/turnover-d/"

async def fetch_s2(session: aiohttp.ClientSession) -> pd.DataFrame:
    """Среднедневные обороты рынка МБК и РЕПО (годовые XLSX)."""
    import openpyxl
    print("S2: fetching MBK/REPO turnover...")
    rows_out = []
    RUS_MONTHS = {"январь", "февраль", "март", "апрель", "май", "июнь",
                  "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"}
    for year in [2024, 2025, 2026]:
        url = f"{S2_BASE}TURNOVER_DEPO_{year}.xlsx"
        dest = RAW / f"s2_turnover_{year}.xlsx"
        try:
            await download_file(session, url, dest)
            wb = openpyxl.load_workbook(dest, data_only=True)
            # Sheet 0: Общий оборот
            if len(wb.sheetnames) > 0:
                s0 = wb[wb.sheetnames[0]]
                for r in range(8, 25):
                    m = s0.cell(r, 1).value
                    if not m or not isinstance(m, str) or m.strip().lower() not in RUS_MONTHS:
                        continue
                    month_clean = m.strip().lower()
                    mbk_rub = s0.cell(r, 2).value
                    repo_rub = s0.cell(r, 3).value
                    if mbk_rub is not None:
                        rows_out.append({
                            "year": year, "period_label": month_clean,
                            "instrument": "MBK", "term": "all",
                            "avg_daily_value": float(mbk_rub),
                            "unit": "млн руб.", "source_id": "S2",
                            "observation_type": "flow_avg_daily",
                            "money_direction": "market_turnover",
                            "source_url": url, "accessed_at": ACCESSED_AT
                        })
                    if repo_rub is not None:
                        rows_out.append({
                            "year": year, "period_label": month_clean,
                            "instrument": "REPO", "term": "all",
                            "avg_daily_value": float(repo_rub),
                            "unit": "млн руб.", "source_id": "S2",
                            "observation_type": "flow_avg_daily",
                            "money_direction": "market_turnover",
                            "source_url": url, "accessed_at": ACCESSED_AT
                        })
            # Sheet 1: Оборот в разбивке по срокам (Овернайт)
            if len(wb.sheetnames) > 1:
                s1 = wb[wb.sheetnames[1]]
                for r in range(8, 25):
                    m = s1.cell(r, 1).value
                    if not m or not isinstance(m, str):
                        continue
                    if m.strip().lower() not in RUS_MONTHS:
                        break  # переход к следующему блоку сроков
                    month_clean = m.strip().lower()
                    mbk_ovn = s1.cell(r, 2).value
                    repo_ovn = s1.cell(r, 3).value
                    if mbk_ovn is not None:
                        rows_out.append({
                            "year": year, "period_label": month_clean,
                            "instrument": "MBK", "term": "overnight",
                            "avg_daily_value": float(mbk_ovn),
                            "unit": "млн руб.", "source_id": "S2",
                            "observation_type": "flow_avg_daily",
                            "money_direction": "market_turnover",
                            "source_url": url, "accessed_at": ACCESSED_AT
                        })
                    if repo_ovn is not None:
                        rows_out.append({
                            "year": year, "period_label": month_clean,
                            "instrument": "REPO", "term": "overnight",
                            "avg_daily_value": float(repo_ovn),
                            "unit": "млн руб.", "source_id": "S2",
                            "observation_type": "flow_avg_daily",
                            "money_direction": "market_turnover",
                            "source_url": url, "accessed_at": ACCESSED_AT
                        })
            print(f"  S2 {year}: ok")
        except Exception as e:
            print(f"  S2 {year}: failed - {e}")
    if not rows_out:
        raise RuntimeError("S2: all years failed")
    return pd.DataFrame(rows_out)


def _find_unit(text: str) -> str:
    for kw in ["млрд руб.", "млн руб.", "трлн руб."]:
        if kw in text.lower():
            return kw
    return ""


# ─────────────────────────── S3: RUONIA ──────────────────────────────────────

S3_URL_PAGE = "https://www.cbr.ru/hd_base/ruonia/dynamics/"
S3_EXCEL_URL = "https://www.cbr.ru/Queries/UniDbQuery/DownloadExcel/135802?Posted=True&so=1&oo=1&UniDbQuery.Posted=True&UniDbQuery.so=1&UniDbQuery.oo=1&UniDbQuery.From=01.01.2025&UniDbQuery.To=31.12.2026"


async def fetch_s3(session: aiohttp.ClientSession) -> pd.DataFrame:
    """RUONIA: ставка и объём сделок overnight МБК."""
    print("S3: fetching RUONIA...")
    html = (await get(session, S3_URL_PAGE)).decode("utf-8", errors="replace")

    xlsx_match = re.search(r'href="([^"]*DownloadExcel[^"]*)"', html)
    if xlsx_match:
        xlsx_url = xlsx_match.group(1)
        if not xlsx_url.startswith("http"):
            xlsx_url = "https://www.cbr.ru" + xlsx_url
    else:
        xlsx_url = S3_EXCEL_URL

    dest = RAW / "s3_ruonia.xlsx"
    try:
        await download_file(session, xlsx_url, dest)
        df = pd.read_excel(dest, engine="openpyxl", header=None)
        return _normalize_s3(df)
    except Exception as e:
        print(f"S3: Excel failed ({e}), parsing HTML table...")
        tables = pd.read_html(io.StringIO(html), decimal=",", thousands=None)
        if not tables:
            raise RuntimeError("S3: no tables in HTML")
        df = tables[0]
        df.to_csv(RAW / "s3_ruonia_raw.csv", index=False, encoding="utf-8-sig")
        return _normalize_s3_html(df)


def _normalize_s3(df: pd.DataFrame) -> pd.DataFrame:
    # Ищем строку с датой
    header_row = 0
    for i, row in df.iterrows():
        val = str(row.iloc[0]).strip()
        if re.match(r"\d{2}\.\d{2}\.\d{4}", val):
            header_row = i
            break
    data = df.iloc[header_row:].copy()
    ncols = len(data.columns)
    col_map = {0: "date_raw"}
    if ncols > 1: col_map[1] = "ruonia_rate_pct"
    if ncols > 2: col_map[2] = "volume_bln"
    if ncols > 3: col_map[3] = "trade_count"
    if ncols > 4: col_map[4] = "participant_count"
    if ncols > 5: col_map[5] = "publication_date_raw"
    data = data.rename(columns=col_map)
    data["reference_date"] = pd.to_datetime(data["date_raw"], dayfirst=True, errors="coerce")
    data = data.dropna(subset=["reference_date"])
    for col in ["ruonia_rate_pct", "volume_bln", "trade_count", "participant_count"]:
        if col in data.columns:
            data[col] = pd.to_numeric(
                data[col].astype(str).str.replace(",", ".").str.replace(r"\s", "", regex=True),
                errors="coerce"
            )
    data["source_id"] = "S3"
    data["unit"] = "rate=% годовых; volume=млрд руб."
    data["observation_type"] = "flow"
    data["money_direction"] = "ruonia_sample_only"
    data["source_url"] = S3_URL_PAGE
    data["accessed_at"] = ACCESSED_AT
    keep = ["reference_date", "ruonia_rate_pct", "volume_bln", "trade_count",
            "participant_count", "source_id", "unit", "observation_type",
            "money_direction", "source_url", "accessed_at"]
    return data[[c for c in keep if c in data.columns]]


def _normalize_s3_html(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {}
    for i, col in enumerate(df.columns):
        if i == 0: rename[col] = "date_raw"
        elif i == 1: rename[col] = "ruonia_rate_pct"
        elif i == 2: rename[col] = "volume_bln"
        elif i == 3: rename[col] = "trade_count"
        elif i == 4: rename[col] = "participant_count"
    df = df.rename(columns=rename)
    df["reference_date"] = pd.to_datetime(df["date_raw"].astype(str), dayfirst=True, errors="coerce")
    df = df.dropna(subset=["reference_date"])
    for col in ["ruonia_rate_pct", "volume_bln", "trade_count", "participant_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")
    df["source_id"] = "S3"
    df["unit"] = "rate=% годовых; volume=млрд руб."
    df["observation_type"] = "flow"
    df["money_direction"] = "ruonia_sample_only"
    df["source_url"] = S3_URL_PAGE
    df["accessed_at"] = ACCESSED_AT
    keep = ["reference_date", "ruonia_rate_pct", "volume_bln", "trade_count",
            "participant_count", "source_id", "unit", "observation_type",
            "money_direction", "source_url", "accessed_at"]
    return df[[c for c in keep if c in df.columns]]


# ─────────────────────────── S4: РЕПО ЦБ аукционы ───────────────────────────

S4_URL = "https://www.cbr.ru/hd_base/repo/"
S4_EXCEL = "https://www.cbr.ru/Queries/UniDbQuery/DownloadExcel/125028?Posted=True&so=1&oo=1&UniDbQuery.Posted=True&UniDbQuery.From=01.01.2025&UniDbQuery.To=31.12.2026"


async def fetch_s4(session: aiohttp.ClientSession) -> pd.DataFrame:
    """РЕПО Банка России: аукционы (предоставление ликвидности ЦБ)."""
    print("S4: fetching CBR REPO auctions (context)...")
    html = (await get(session, S4_URL)).decode("utf-8", errors="replace")
    xlsx_match = re.search(r'href="([^"]*DownloadExcel[^"]*)"', html)
    xlsx_url = ("https://www.cbr.ru" + xlsx_match.group(1)) if xlsx_match and not xlsx_match.group(1).startswith("http") else (xlsx_match.group(1) if xlsx_match else S4_EXCEL)

    dest = RAW / "s4_repo_auctions.xlsx"
    try:
        await download_file(session, xlsx_url, dest)
        df = pd.read_excel(dest, engine="openpyxl", header=None)
    except Exception as e:
        print(f"S4: Excel failed ({e}), using HTML...")
        tables = pd.read_html(io.StringIO(html), decimal=",", thousands=None)
        if not tables:
            return pd.DataFrame()
        df = tables[0]
        df.to_csv(RAW / "s4_repo_auctions_raw.csv", index=False, encoding="utf-8-sig")
        df["source_id"] = "S4"
        df["observation_type"] = "flow_auction_result"
        df["money_direction"] = "cbr_provides_to_banks_CONTEXT_ONLY"
        df["source_url"] = S4_URL
        df["accessed_at"] = ACCESSED_AT
        return df

    return _normalize_s4(df)


def _normalize_s4(df: pd.DataFrame) -> pd.DataFrame:
    header_row = 0
    for i, row in df.iterrows():
        val = str(row.iloc[0]).strip()
        if re.match(r"\d{2}\.\d{2}\.\d{4}", val):
            header_row = i
            break
    data = df.iloc[header_row:].copy()
    ncols = len(data.columns)
    col_map = {0: "date_raw"}
    if ncols > 1: col_map[1] = "auction_time"
    if ncols > 2: col_map[2] = "demand_mn"
    if ncols > 3: col_map[3] = "concluded_mn"
    if ncols > 4: col_map[4] = "rate_pct"
    if ncols > 5: col_map[5] = "term_days"
    data = data.rename(columns=col_map)
    data["reference_date"] = pd.to_datetime(data["date_raw"], dayfirst=True, errors="coerce")
    data = data.dropna(subset=["reference_date"])
    for col in ["demand_mn", "concluded_mn", "rate_pct", "term_days"]:
        if col in data.columns:
            data[col] = pd.to_numeric(
                data[col].astype(str).str.replace(",", ".").str.replace(r"\s", "", regex=True),
                errors="coerce"
            )
    data["source_id"] = "S4"
    data["unit"] = "млн руб."
    data["observation_type"] = "flow_auction_result"
    data["money_direction"] = "cbr_provides_to_banks_CONTEXT_ONLY"
    data["source_url"] = S4_URL
    data["accessed_at"] = ACCESSED_AT
    keep = ["reference_date", "demand_mn", "concluded_mn", "rate_pct", "term_days",
            "source_id", "unit", "observation_type", "money_direction", "source_url", "accessed_at"]
    return data[[c for c in keep if c in data.columns]]


# ─────────────────────────── S7: Форма 101 ───────────────────────────────────

S7_PAGE = "https://www.cbr.ru/banking_sector/otchetnost-kreditnykh-organizaciy/"
S7_URL_TEMPLATE = "https://www.cbr.ru/vfs/credit/forms/101-{date}.rar"

LIQUIDITY_ACCOUNTS = ["319", "32021", "32022"]  # 319=депозиты в ЦБ, 320+321=МБК агрегат

try:
    import rarfile as _rarfile
    _rarfile.UNRAR_TOOL = r"C:\Program Files\WinRAR\UnRAR.exe"
    _HAS_RARFILE = True
except ImportError:
    _HAS_RARFILE = False

try:
    from dbfread import DBF as _DBF
    _HAS_DBF = True
except ImportError:
    _HAS_DBF = False


async def _get_latest_101_dates(session: aiohttp.ClientSession, n: int = 3) -> list[str]:
    """Возвращает N последних дат архивов 101-YYYYMMDD.rar."""
    html = (await get(session, S7_PAGE)).decode("utf-8", errors="replace")
    pattern = re.compile(r"101-(\d{8})\.rar")
    dates = sorted(set(pattern.findall(html)), reverse=True)
    return dates[:n]


async def fetch_s7(session: aiohttp.ClientSession) -> pd.DataFrame:
    """Форма 101: остатки по счетам 319, 320+321 по банкам."""
    if not (_HAS_RARFILE and _HAS_DBF):
        print("S7: rarfile or dbfread not available, skipping")
        return pd.DataFrame()

    print("S7: fetching Form 101 (F-101)...")
    dates = await _get_latest_101_dates(session, n=3)
    if not dates:
        print("S7: no dates found on CBR page")
        return pd.DataFrame()

    frames = []
    for date in dates:
        url = S7_URL_TEMPLATE.format(date=date)
        dest = ARCH / f"101-{date}.rar"
        try:
            await download_file(session, url, dest)
            df = _parse_101_archive(str(dest), date)
            frames.append(df)
            print(f"  F-101 {date}: {len(df)} rows")
        except Exception as e:
            print(f"  F-101 {date}: failed — {e}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _decode(val, enc="cp866") -> str:
    if isinstance(val, bytes):
        return val.decode(enc, errors="replace").strip().rstrip("\x00")
    return str(val or "").strip()


def _parse_101_archive(rar_path: str, date_str: str) -> pd.DataFrame:
    """Извлекает счета ликвидности из архива Ф-101."""
    # В 2026 г. ЦБ кодирует агрегат 320+321 как '32.1', 313+314 как '31.1'
    ACCOUNTS = {"319", "320", "321", "32.1", "32.2", "31.1", "31.2"}
    ACCOUNT_NAMES = {
        "319": "Депозиты в Банке России",
        "32.1": "МБК размещенные (агрегат 320+321)",
        "32.2": "Прочие размещенные средства (агрегат 322+323)",
        "31.1": "МБК привлеченные (агрегат 313+314)",
        "31.2": "Прочие привлеченные средства (агрегат 315+316)",
        "320": "МБК размещенные в банках-резидентах",
        "321": "МБК размещенные в банках-нерезидентах",
    }

    with tempfile.TemporaryDirectory() as tmp:
        with _rarfile.RarFile(rar_path) as rf:
            rf.extractall(tmp)

        # Найдём файлы
        files = {f.lower(): os.path.join(tmp, f) for f in os.listdir(tmp)}
        banks_path = next((v for k, v in files.items() if k.endswith("n1.dbf")), None)
        values_path = next((v for k, v in files.items() if k.endswith("b1.dbf")), None)
        if not values_path:
            raise FileNotFoundError(f"b1.dbf not found in {rar_path}")

        banks: dict[int, str] = {}
        if banks_path:
            for r in _DBF(banks_path, encoding="cp866", raw=True):
                regn_s = _decode(r.get("REGN"))
                name = _decode(r.get("NAME_B"))
                try:
                    banks[int(regn_s)] = name
                except ValueError:
                    pass

        rows = []
        for r in _DBF(values_path, encoding="cp866", raw=True):
            num_sc = _decode(r.get("NUM_SC"))
            # Фильтруем только нужные счета (по префиксу)
            if not any(num_sc.startswith(a) for a in ACCOUNTS):
                continue
            regn_s = _decode(r.get("REGN"))
            try:
                regn = int(regn_s)
            except ValueError:
                continue

            iitg_s = _decode(r.get("IITG", b"")).replace(",", ".")
            try:
                iitg = float(iitg_s) if iitg_s else 0.0
            except ValueError:
                iitg = 0.0

            rows.append({
                "reference_date": pd.to_datetime(date_str, format="%Y%m%d"),
                "regn": regn,
                "bank_name": banks.get(regn, str(regn)),
                "num_sc": num_sc,
                "account_name": ACCOUNT_NAMES.get(num_sc, num_sc),
                "a_p": _decode(r.get("A_P")),
                "iitg_thou": iitg,  # тыс. руб. в Ф-101
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # 2026: 320 и 321 раскрываются только как агрегат 320+321
    # Агрегируем — для счёта 319 берём активный остаток (a_p='1')
    df["source_id"] = "S7"
    df["unit"] = "тыс. руб."
    df["observation_type"] = "stock"
    df["money_direction"] = "bank_places_in_cbr_or_banks"
    df["source_url"] = f"https://www.cbr.ru/vfs/credit/forms/101-{date_str}.rar"
    df["accessed_at"] = ACCESSED_AT
    df["note_2026"] = (
        "В 2026 г. счета 320+321 раскрываются только агрегатом (решение ЦБ 19.12.2025). "
        "Разрез резидент/нерезидент недоступен в публичном Ф-101."
    )
    return df


# ─────────────────────────── Валидация контрольных точек ────────────────────

CHECKPOINTS = [
    # (source_id, field, date, expected_value, tolerance_pct)
    ("S1", "overnight_mn",  "2026-10-29", 3_876_954.47, 0.01),
    ("S3", "ruonia_rate_pct", "2026-10-28", 14.09, 0.5),
    ("S3", "volume_bln",     "2026-10-28", 992.86, 1.0),
]


def validate(dfs: dict[str, pd.DataFrame]) -> list[str]:
    issues = []
    for src, field, date_str, expected, tol_pct in CHECKPOINTS:
        df = dfs.get(src)
        if df is None or df.empty:
            issues.append(f"WARN {src}: no data to validate")
            continue
        if field not in df.columns:
            issues.append(f"WARN {src}: field {field!r} missing")
            continue
        ref = pd.Timestamp(date_str)
        row = df[df["reference_date"] == ref]
        if row.empty:
            issues.append(f"WARN {src}: date {date_str} not found")
            continue
        actual = row[field].iloc[0]
        if pd.isna(actual):
            issues.append(f"WARN {src}/{field}/{date_str}: value is NaN")
            continue
        diff_pct = abs(actual - expected) / max(abs(expected), 1e-9) * 100
        if diff_pct > tol_pct:
            issues.append(
                f"FAIL {src}/{field}/{date_str}: expected {expected}, got {actual:.4f} (diff {diff_pct:.2f}%)"
            )
        else:
            print(f"  OK  {src}/{field}/{date_str}: {actual:.4f} [OK]")
    return issues


# ─────────────────────────── main ────────────────────────────────────────────

async def main() -> None:
    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Параллельно качаем S1, S3, S4; S2 и S7 отдельно из-за размера
        s1_task = asyncio.create_task(fetch_s1(session))
        s3_task = asyncio.create_task(fetch_s3(session))
        s4_task = asyncio.create_task(fetch_s4(session))
        s2_task = asyncio.create_task(fetch_s2(session))
        s7_task = asyncio.create_task(fetch_s7(session))

        s1 = await s1_task
        s3 = await s3_task
        s4 = await s4_task
        s2 = await s2_task
        s7 = await s7_task

    dfs = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S7": s7}

    # Сохраняем
    for name, df in dfs.items():
        if df is not None and not df.empty:
            path = PROC / f"{name.lower()}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"Saved {name} -> {path} ({len(df)} rows)")
        else:
            print(f"Skip {name}: empty")

    # Валидация
    print("\n-- Validation ----------------------")
    issues = validate(dfs)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  All checkpoints passed [OK]")

    print(f"\nDone. Raw: {RAW}  Processed: {PROC}")


if __name__ == "__main__":
    asyncio.run(main())
