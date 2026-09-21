"""Очистка сырых данных. Каждое правило логируется — это часть отчёта о качестве данных."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"

CITY_MAP = {"almaty": "Алматы", "astana": "Астана"}


def normalize_city(s):
    s = str(s).strip()
    return CITY_MAP.get(s.lower(), s[:1].upper() + s[1:].lower())


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    log = []

    cust = pd.read_csv(RAW / "customers.csv")
    before = cust["city"].nunique()
    cust["city"] = cust["city"].map(normalize_city)
    log.append(f"Города: {before} вариантов написания -> {cust['city'].nunique()}")
    n_na = cust["channel"].isna().sum()
    cust["channel"] = cust["channel"].fillna("unknown")
    log.append(f"Канал привлечения: {n_na} пропусков заполнено значением 'unknown'")
    cust["signup_date"] = pd.to_datetime(cust["signup_date"])

    ords = pd.read_csv(RAW / "orders.csv")
    n = len(ords)
    ords = ords.drop_duplicates()
    log.append(f"Заказы: удалено {n - len(ords)} полных дубликатов")

    ords["order_date"] = pd.to_datetime(ords["order_date"], format="mixed", dayfirst=True)
    log.append("Даты: приведены форматы YYYY-MM-DD и DD.MM.YYYY к единому")

    n_str = ords["unit_price"].astype(str).str.contains(" ").sum()
    ords["unit_price"] = ords["unit_price"].astype(str).str.replace(" ", "").astype(float)
    log.append(f"Цены: {n_str} значений-строк с пробелами преобразованы в числа")

    bad = ords["quantity"] <= 0
    ords = ords[~bad]
    log.append(f"Количество: удалено {bad.sum()} строк с quantity <= 0")

    ords["revenue"] = ords["quantity"] * ords["unit_price"] * (1 - ords["discount"])

    prods = pd.read_csv(RAW / "products.csv")
    df = ords.merge(prods[["product_id", "name", "category"]], on="product_id", how="left") \
             .merge(cust, on="customer_id", how="left")
    assert df["category"].notna().all(), "Есть заказы с неизвестным товаром"

    df.to_csv(CLEAN / "orders_enriched.csv", index=False)
    cust.to_csv(CLEAN / "customers.csv", index=False)
    (CLEAN / "cleaning_log.txt").write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))
    print(f"clean: {len(df)} rows -> {CLEAN}")


if __name__ == "__main__":
    main()
