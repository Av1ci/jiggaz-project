"""Генерирует реалистичные «сырые» данные интернет-магазина (с типичными ошибками)."""
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

CITIES = {"Алматы": 0.40, "Астана": 0.30, "Шымкент": 0.15, "Караганда": 0.10, "Актобе": 0.05}
CHANNELS = {"organic": 0.35, "ads": 0.30, "social": 0.20, "email": 0.15}
PRODUCTS = [
    # product_id, name, category, price (KZT)
    (1, "Смартфон A1", "Электроника", 180000),
    (2, "Наушники Pro", "Электроника", 45000),
    (3, "Ноутбук X", "Электроника", 420000),
    (4, "Куртка зимняя", "Одежда", 38000),
    (5, "Кроссовки Run", "Одежда", 29000),
    (6, "Футболка Basic", "Одежда", 6000),
    (7, "Кофеварка", "Дом", 52000),
    (8, "Набор посуды", "Дом", 24000),
    (9, "Роман «Абай жолы»", "Книги", 5500),
    (10, "Учебник Python", "Книги", 9000),
]


def pick(d):
    return random.choices(list(d), weights=list(d.values()))[0]


def main(n_customers=2000):
    random.seed(SEED)
    np.random.seed(SEED)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 1)

    customers = []
    for cid in range(1, n_customers + 1):
        signup = start + timedelta(days=random.randint(0, 364))
        customers.append({
            "customer_id": cid,
            "signup_date": signup.isoformat(),
            "city": pick(CITIES),
            "channel": pick(CHANNELS),
        })
    cust = pd.DataFrame(customers)

    # Ошибки ввода: разный регистр/транслит городов, пропуски
    dirty = cust.sample(frac=0.05, random_state=SEED).index
    cust.loc[dirty, "city"] = cust.loc[dirty, "city"].map(
        lambda c: random.choice([c.lower(), c.upper(), " " + c + " ", {"Алматы": "Almaty", "Астана": "Astana"}.get(c, c)]))
    cust.loc[cust.sample(frac=0.02, random_state=1).index, "channel"] = None

    orders, oid = [], 1
    retention = {"organic": 0.55, "email": 0.65, "social": 0.40, "ads": 0.35}
    for c in customers:
        d = date.fromisoformat(c["signup_date"]) + timedelta(days=random.randint(0, 10))
        p_repeat = retention[c["channel"]]
        while d <= date(2025, 12, 31):
            product = random.choice(PRODUCTS)
            month = d.month
            season = 1.0 + (0.5 if month in (11, 12) else 0)  # Черная пятница / НГ
            qty = np.random.choice([1, 1, 1, 2, 3]) if product[3] < 50000 else 1
            discount = random.choice([0, 0, 0, 0.1, 0.2]) if season > 1 else random.choice([0, 0, 0, 0, 0.1])
            status = random.choices(["delivered", "cancelled", "returned"], [0.88, 0.08, 0.04])[0]
            orders.append({
                "order_id": oid, "customer_id": c["customer_id"], "order_date": d.isoformat(),
                "product_id": product[0], "quantity": qty, "unit_price": product[3],
                "discount": discount, "status": status,
            })
            oid += 1
            if random.random() > p_repeat * (1.1 if season > 1 else 1):
                break
            d += timedelta(days=int(np.random.exponential(45)) + 3)
    ords = pd.DataFrame(orders)

    # Ошибки: дубли, отрицательные количества, цены строкой, разные форматы дат
    ords = pd.concat([ords, ords.sample(frac=0.01, random_state=2)], ignore_index=True)
    ords.loc[ords.sample(frac=0.005, random_state=3).index, "quantity"] = -1
    ords["unit_price"] = ords["unit_price"].astype(object)
    idx = ords.sample(frac=0.03, random_state=4).index
    ords.loc[idx, "unit_price"] = ords.loc[idx, "unit_price"].map(lambda v: f"{v:,}".replace(",", " "))
    idx = ords.sample(frac=0.03, random_state=5).index
    ords.loc[idx, "order_date"] = pd.to_datetime(ords.loc[idx, "order_date"]).dt.strftime("%d.%m.%Y")

    prods = pd.DataFrame(PRODUCTS, columns=["product_id", "name", "category", "list_price"])

    cust.to_csv(RAW_DIR / "customers.csv", index=False)
    ords.to_csv(RAW_DIR / "orders.csv", index=False)
    prods.to_csv(RAW_DIR / "products.csv", index=False)
    print(f"raw: {len(cust)} customers, {len(ords)} orders, {len(prods)} products -> {RAW_DIR}")


if __name__ == "__main__":
    main()
