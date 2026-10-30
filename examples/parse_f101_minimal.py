"""
Минимальный пример распаковки и фильтрации Формы 101 (DBF) по счетам 319 и 32.1.
"""
from dbfread import DBF

def inspect_dbf(dbf_path: str):
    targets = {"319", "32.1", "31.1", "301"}
    records = []
    for r in DBF(dbf_path, encoding="cp866", raw=True):
        sc = r.get("NUM_SC", b"").decode("cp866", errors="ignore").strip()
        if any(sc.startswith(t) for t in targets):
            regn = r.get("REGN", b"").decode("cp866", errors="ignore").strip()
            iitg = r.get("IITG", b"").decode("cp866", errors="ignore").strip()
            records.append((regn, sc, iitg))
    return records

if __name__ == "__main__":
    print("Используйте с распакованным b1.dbf из архива Формы 101 ЦБ РФ.")
