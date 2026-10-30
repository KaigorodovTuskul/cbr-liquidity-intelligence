"""
Минимальный пример сбора сводки S1 (депозиты кредитных организаций в Банке России).
"""
import pandas as pd

def fetch_s1():
    url = "https://www.cbr.ru/hd_base/ostat_depo_new/"
    dfs = pd.read_html(url, attrs={"class": "data"})
    df = dfs[0]
    df.columns = ["date", "total_depo", "overnight", "one_week", "fine_tuning"]
    return df

if __name__ == "__main__":
    df = fetch_s1()
    print("S1 shape:", df.shape)
    print(df.head())
