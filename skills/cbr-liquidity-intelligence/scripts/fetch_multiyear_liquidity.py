"""
Сбор и сведение многолетней банковской статистики ликвидности (2024-2026 гг.):
- Форма 101: остатки по счетам 319 (депозиты в ЦБ), 32.1 (МБК размещенные), 31.1 (МБК привлеченные), 301 (корсчета в ЦБ)
- Форма 135: нормативы мгновенной (Н2), текущей (Н3) и долгосрочной (Н4) ликвидности
- Форма 123: капитал банка (код 000)

Запуск: python scripts/fetch_multiyear_liquidity.py
"""

import asyncio
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import pandas as pd
from dbfread import DBF
import rarfile

rarfile.UNRAR_TOOL = r"C:\Program Files\WinRAR\UnRAR.exe"

ROOT = Path(__file__).resolve().parent.parent
ARCH = ROOT / "data" / "archives"
PROC = ROOT / "data" / "processed"
RESULTS = ROOT.parent / "results"

ARCH.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)

YEARS_DATES = ["20241001", "20251001", "20261001"]
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = aiohttp.ClientTimeout(total=120)


def _decode(val, enc="cp866") -> str:
    if isinstance(val, bytes):
        return val.decode(enc, errors="replace").strip().rstrip("\x00")
    return str(val or "").strip()


async def download_archive(session: aiohttp.ClientSession, form: str, date: str) -> Path:
    dest = ARCH / f"{form}-{date}.rar"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    url = f"https://www.cbr.ru/vfs/credit/forms/{form}-{date}.rar"
    async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as r:
        if r.status != 200:
            print(f"Warning: {form}-{date} returned {r.status}")
            return None
        content = await r.read()
        dest.write_bytes(content)
        print(f"Downloaded {dest.name} ({len(content)} bytes)")
        return dest


def parse_f101(rar_path: Path, date_str: str) -> dict[int, dict]:
    """Парсит 101 форму: счета 319, 32.1 (320+321), 31.1 (313+314), 301."""
    ACCOUNTS = {"319", "32.1", "320", "321", "31.1", "313", "314", "301"}
    banks_data = {}

    with tempfile.TemporaryDirectory() as td:
        with rarfile.RarFile(rar_path) as rf:
            rf.extractall(td)
        files = {f.lower(): os.path.join(td, f) for f in os.listdir(td)}
        b1_path = next(v for k, v in files.items() if k.endswith("b1.dbf"))
        n1_path = next((v for k, v in files.items() if k.endswith("n1.dbf")), None)

        names = {}
        if n1_path:
            for r in DBF(n1_path, encoding="cp866", raw=True):
                try:
                    regn = int(_decode(r.get("REGN")))
                    names[regn] = _decode(r.get("NAME_B"))
                except (ValueError, TypeError):
                    pass

        for r in DBF(b1_path, encoding="cp866", raw=True):
            sc = _decode(r.get("NUM_SC"))
            if not any(sc.startswith(a) for a in ACCOUNTS):
                continue
            try:
                regn = int(_decode(r.get("REGN")))
                iitg = float(_decode(r.get("IITG", b"")).replace(",", ".") or 0)
                ap = _decode(r.get("A_P"))
            except (ValueError, TypeError):
                continue

            if regn not in banks_data:
                banks_data[regn] = {
                    "regn": regn,
                    "bank_name": names.get(regn, str(regn)),
                    "cbr_deposits_319_thou": 0.0,
                    "mbk_placed_321_thou": 0.0,
                    "mbk_borrowed_311_thou": 0.0,
                    "cbr_corresp_301_thou": 0.0,
                }

            # Активные остатки (размещение)
            if sc.startswith("319") and ap == "1":
                banks_data[regn]["cbr_deposits_319_thou"] += iitg
            elif (sc.startswith("32.1") or sc.startswith("320") or sc.startswith("321")) and ap == "1":
                banks_data[regn]["mbk_placed_321_thou"] += iitg
            elif sc.startswith("301") and ap == "1":
                banks_data[regn]["cbr_corresp_301_thou"] += iitg
            # Пассивные остатки (привлечение)
            elif (sc.startswith("31.1") or sc.startswith("313") or sc.startswith("314")) and ap == "2":
                banks_data[regn]["mbk_borrowed_311_thou"] += iitg

    return banks_data


def parse_f135(rar_path: Path) -> dict[int, dict]:
    """Парсит нормативы ликвидности Н2, Н3, Н4 из 135 формы."""
    norms = {}
    with tempfile.TemporaryDirectory() as td:
        with rarfile.RarFile(rar_path) as rf:
            rf.extractall(td)
        data_path = next(os.path.join(td, f) for f in os.listdir(td) if f.lower().endswith("3.dbf"))
        for r in DBF(data_path, encoding="cp866", raw=True):
            code = _decode(r.get("C1_3")).replace("Í", "Н")
            if code not in {"Н2", "Н3", "Н4"}:
                continue
            try:
                regn = int(_decode(r.get("REGN")))
                val = float(_decode(r.get("C2_3")).replace(",", ".") or 0)
            except (ValueError, TypeError):
                continue
            if regn not in norms:
                norms[regn] = {}
            norms[regn][code] = val
    return norms


def parse_f123(rar_path: Path) -> dict[int, float]:
    """Парсит капитал банка (код 000, тыс. руб.) из 123 формы."""
    capitals = {}
    with tempfile.TemporaryDirectory() as td:
        with rarfile.RarFile(rar_path) as rf:
            rf.extractall(td)
        data_path = next(os.path.join(td, f) for f in os.listdir(td) if f.lower().endswith("d.dbf"))
        for r in DBF(data_path, encoding="cp866", raw=True):
            code = _decode(r.get("C1"))
            if code != "000":
                continue
            try:
                regn = int(_decode(r.get("REGN")))
                val = float(_decode(r.get("C3")).replace(",", ".") or 0)
                capitals[regn] = val
            except (ValueError, TypeError):
                continue
    return capitals


async def build_multiyear_dataset() -> pd.DataFrame:
    rows = []
    async with aiohttp.ClientSession() as session:
        for dt in YEARS_DATES:
            print(f"\nProcessing date {dt}...")
            p101 = await download_archive(session, "101", dt)
            p135 = await download_archive(session, "135", dt)
            p123 = await download_archive(session, "123", dt)

            b101 = parse_f101(p101, dt) if p101 else {}
            b135 = parse_f135(p135) if p135 else {}
            b123 = parse_f123(p123) if p123 else {}

            date_obj = pd.to_datetime(dt, format="%Y%m%d")
            year = date_obj.year

            for regn, data in b101.items():
                norm_dict = b135.get(regn, {})
                capital = b123.get(regn, None)

                placed = data["mbk_placed_321_thou"]
                borrowed = data["mbk_borrowed_311_thou"]
                net_mbk = placed - borrowed

                rows.append({
                    "reference_date": date_obj.strftime("%Y-%m-%d"),
                    "year": year,
                    "regn": regn,
                    "bank_name": data["bank_name"],
                    "cbr_deposits_319_thou": data["cbr_deposits_319_thou"],
                    "mbk_placed_321_thou": placed,
                    "mbk_borrowed_311_thou": borrowed,
                    "net_mbk_position_thou": net_mbk,
                    "cbr_corresp_301_thou": data["cbr_corresp_301_thou"],
                    "norm_n2_instant_pct": norm_dict.get("Н2"),
                    "norm_n3_current_pct": norm_dict.get("Н3"),
                    "norm_n4_longterm_pct": norm_dict.get("Н4"),
                    "capital_thou": capital,
                    "role_in_mbk": "кредитор (донор)" if net_mbk > 0 else "заемщик (реципиент)" if net_mbk < 0 else "нейтрально",
                })

    df = pd.DataFrame(rows)
    return df


def main():
    df = asyncio.run(build_multiyear_dataset())
    print(f"\nTotal rows collected: {len(df)}")
    
    # Сохраняем обработанные данные
    out_proc = PROC / "banks_multiyear_liquidity.csv"
    out_res = RESULTS / "banks_multiyear_liquidity.csv"
    df.to_csv(out_proc, index=False, encoding="utf-8-sig")
    df.to_csv(out_res, index=False, encoding="utf-8-sig")
    print(f"Saved: {out_proc}")
    print(f"Saved: {out_res}")

    # Краткая статистика
    print("\nSummary by year:")
    grouped = df.groupby("year").agg({
        "regn": "count",
        "cbr_deposits_319_thou": lambda x: x.sum() / 1e9,
        "mbk_placed_321_thou": lambda x: x.sum() / 1e9,
        "mbk_borrowed_311_thou": lambda x: x.sum() / 1e9,
        "capital_thou": lambda x: x.sum() / 1e9,
    }).rename(columns={
        "regn": "banks_count",
        "cbr_deposits_319_thou": "cbr_depo_trln",
        "mbk_placed_321_thou": "mbk_placed_trln",
        "mbk_borrowed_311_thou": "mbk_borrowed_trln",
        "capital_thou": "capital_trln",
    })
    print(grouped.to_string())


if __name__ == "__main__":
    main()
