"""Анализ: KPI, динамика, категории, каналы, когортное удержание, RFM-сегментация.
Результат — графики в reports/figures и отчёт reports/report.md."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN, REPORTS = ROOT / "data" / "clean", ROOT / "reports"
FIG = REPORTS / "figures"
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})


def money(x):
    return f"{x:,.0f} ₸".replace(",", " ")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name)
    plt.close(fig)
    return f"figures/{name}"


def md_table(df):
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.values]
    return "\n".join(lines)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CLEAN / "orders_enriched.csv", parse_dates=["order_date", "signup_date"])
    ok = df[df["status"] == "delivered"].copy()
    ok["month"] = ok["order_date"].dt.to_period("M")

    # --- KPI
    revenue = ok["revenue"].sum()
    n_orders = ok["order_id"].nunique()
    buyers = ok["customer_id"].nunique()
    aov = revenue / n_orders
    orders_per = ok.groupby("customer_id")["order_id"].nunique()
    repeat_rate = (orders_per > 1).mean()
    cancel_rate = (df["status"] != "delivered").mean()

    # --- Динамика по месяцам
    monthly = ok.groupby("month").agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(monthly.index.astype(str), monthly["revenue"] / 1e6, marker="o", color="#3b5bdb")
    ax.set_title("Выручка по месяцам, млн ₸")
    ax.tick_params(axis="x", rotation=45)
    f_monthly = save(fig, "monthly_revenue.png")
    peak = monthly["revenue"].idxmax()

    # --- Категории
    cat = ok.groupby("category")["revenue"].sum().sort_values()
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.barh(cat.index, cat / 1e6, color="#3b5bdb")
    ax.set_title("Выручка по категориям, млн ₸")
    f_cat = save(fig, "category_revenue.png")
    cat_share = (cat / cat.sum()).sort_values(ascending=False)

    # --- Каналы: выручка на клиента и повторные покупки
    ch = ok.groupby("channel").agg(customers=("customer_id", "nunique"), revenue=("revenue", "sum"))
    ch["revenue_per_customer"] = ch["revenue"] / ch["customers"]
    ch["repeat_rate"] = orders_per.groupby(ok.groupby("customer_id")["channel"].first()).apply(lambda s: (s > 1).mean())
    ch = ch.sort_values("revenue_per_customer", ascending=False)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.bar(ch.index, ch["revenue_per_customer"] / 1000, color="#3b5bdb")
    ax.set_title("Выручка на клиента по каналам, тыс. ₸")
    f_ch = save(fig, "channel_ltv.png")

    # --- Когортный анализ удержания
    first = ok.groupby("customer_id")["order_date"].min().dt.to_period("M").rename("cohort")
    c = ok.join(first, on="customer_id")
    c["age"] = (c["month"] - c["cohort"]).apply(lambda x: x.n)
    cohort = c.groupby(["cohort", "age"])["customer_id"].nunique().unstack(fill_value=0)
    retention = cohort.div(cohort[0], axis=0).iloc[:, :7]
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(retention.values, cmap="Blues", vmin=0, vmax=0.4, aspect="auto")
    ax.set_xticks(range(retention.shape[1]))
    ax.set_yticks(range(len(retention)))
    ax.set_yticklabels(retention.index.astype(str))
    ax.set_xlabel("Месяцев после первой покупки")
    ax.set_title("Когортное удержание")
    for i in range(retention.shape[0]):
        for j in range(1, retention.shape[1]):
            v = retention.iat[i, j]
            if pd.notna(v) and cohort.iat[i, j] > 0:
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, format=matplotlib.ticker.PercentFormatter(1.0))
    f_coh = save(fig, "cohort_retention.png")
    m1 = retention[1].mean() if 1 in retention else 0

    # --- RFM-сегментация
    snap = ok["order_date"].max() + pd.Timedelta(days=1)
    rfm = ok.groupby("customer_id").agg(
        R=("order_date", lambda s: (snap - s.max()).days),
        F=("order_id", "nunique"), M=("revenue", "sum"))
    rfm["r"] = pd.qcut(rfm["R"], 3, labels=[3, 2, 1]).astype(int)
    rfm["f"] = pd.cut(rfm["F"], [0, 1, 2, 1e9], labels=[1, 2, 3]).astype(int)
    rfm["m"] = pd.qcut(rfm["M"], 3, labels=[1, 2, 3]).astype(int)

    def segment(r):
        if r.r == 3 and r.f >= 2 and r.m >= 2:
            return "Чемпионы"
        if r.f >= 2 and r.r >= 2:
            return "Лояльные"
        if r.r == 3:
            return "Новые"
        if r.r == 1 and (r.f >= 2 or r.m == 3):
            return "Под угрозой ухода"
        return "Спящие"
    rfm["segment"] = rfm.apply(segment, axis=1)
    seg = rfm.groupby("segment").agg(clients=("F", "size"), revenue=("M", "sum"), avg_orders=("F", "mean"))
    seg["share_rev"] = seg["revenue"] / seg["revenue"].sum()
    seg = seg.sort_values("revenue", ascending=False)
    rfm.to_csv(REPORTS / "rfm_segments.csv")

    # --- Отчёт
    seg_tbl = seg.reset_index().assign(
        revenue=lambda d: d["revenue"].map(money),
        avg_orders=lambda d: d["avg_orders"].round(2),
        share_rev=lambda d: (d["share_rev"] * 100).round(1).astype(str) + "%")
    seg_tbl.columns = ["Сегмент", "Клиентов", "Выручка", "Заказов/клиент", "Доля выручки"]
    ch_tbl = ch.reset_index()[["channel", "customers", "revenue_per_customer", "repeat_rate"]].assign(
        revenue_per_customer=lambda d: d["revenue_per_customer"].map(money),
        repeat_rate=lambda d: (d["repeat_rate"] * 100).round(1).astype(str) + "%")
    ch_tbl.columns = ["Канал", "Клиентов", "Выручка на клиента", "Доля повторных"]
    known = ch.drop("unknown", errors="ignore")
    best_ch, worst_ch = known.index[0], known.index[-1]
    at_risk = seg.loc["Под угрозой ухода"] if "Под угрозой ухода" in seg.index else None
    log = (CLEAN / "cleaning_log.txt").read_text(encoding="utf-8")

    report = f"""# Анализ продаж интернет-магазина за 2025 год

## Бизнес-вопрос
Откуда приходит выручка, какие клиенты возвращаются и куда направить маркетинговый бюджет в 2026 году?

## Ключевые метрики (только доставленные заказы)
| Метрика | Значение |
|---|---|
| Выручка | {money(revenue)} |
| Заказов | {n_orders:,} |
| Покупателей | {buyers:,} |
| Средний чек (AOV) | {money(aov)} |
| Доля повторных покупателей | {repeat_rate:.1%} |
| Доля отмен и возвратов | {cancel_rate:.1%} |

## 1. Динамика
![]({f_monthly})

Пик выручки — **{peak}**. Рост в ноябре–декабре связан с сезоном распродаж: на этот период нужно заранее закупать товар и планировать бюджет.

## 2. Категории
![]({f_cat})

**{cat_share.index[0]}** дает {cat_share.iloc[0]:.0%} выручки. Высокая зависимость от одной категории — риск, стоит развивать кросс-продажи (аксессуары к электронике).

## 3. Каналы привлечения
{md_table(ch_tbl)}

![]({f_ch})

Лучший канал по выручке на клиента — **{best_ch}**, худший — **{worst_ch}**. Нужно сравнить с затратами на привлечение (CAC) и перераспределить бюджет в пользу каналов с максимальным LTV/CAC.

## 4. Удержание (когорты)
![]({f_coh})

В среднем только **{m1:.0%}** клиентов возвращаются в следующем месяце после первой покупки. Главная точка роста — второй заказ.

## 5. RFM-сегментация
{md_table(seg_tbl)}

{f"Сегмент «Под угрозой ухода»: **{int(at_risk.clients)}** клиентов, которые принесли {money(at_risk.revenue)}. Им стоит отправить реактивационную кампанию." if at_risk is not None else ""}
Список клиентов с сегментами: `reports/rfm_segments.csv`.

## Рекомендации
1. Запустить welcome-цепочку писем с промокодом на второй заказ в течение 30 дней — это напрямую повышает удержание.
2. Перераспределить бюджет из **{worst_ch}** в **{best_ch}** и organic после расчета CAC.
3. Реактивационная кампания для сегмента «Под угрозой ухода».
4. Подготовить склад и рекламу к ноябрю–декабрю.

## Качество данных
```
{log}
```

## Ограничения
- Нет данных о затратах на маркетинг — нельзя посчитать CAC и ROMI.
- Один год данных — годовая сезонность оценена по одному циклу.
"""
    (REPORTS / "report.md").write_text(report, encoding="utf-8")
    print(f"Выручка {money(revenue)}, AOV {money(aov)}, repeat {repeat_rate:.1%}")
    print(f"report -> {REPORTS / 'report.md'}")


if __name__ == "__main__":
    main()
