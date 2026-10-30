"""
Минимальный пример получения остатков депозитов банков в ЦБ РФ за 10 строк кода.
"""
import pandas as pd

url = "https://www.cbr.ru/hd_base/ostat_depo_new/"
tables = pd.read_html(url, attrs={"class": "data"})
df = tables[0]
df.columns = ["date", "total_depo", "overnight", "one_week", "fine_tuning"]
print("Последние 5 записей остатков депозитов банков в Банке России:")
print(df.head(5).to_string(index=False))
