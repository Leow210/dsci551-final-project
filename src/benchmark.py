"""
DuckDB vs pandas benchmark.

Runs same queries through both engines. pandas is the baseline; DuckDB is columnar storage and vectorized execution.
"""

from __future__ import annotations

import os
import statistics
import time

import pandas as pd

from .database import DATA_DIR, REAL_CSV, SYNTHETIC_CSV, DB_PATH, get_connection

REPS = 5


def _pick_csv() -> str:
    if os.path.exists(REAL_CSV):
        return REAL_CSV
    return SYNTHETIC_CSV


def _load_pandas_df(csv_path: str) -> pd.DataFrame:
    """Load the CSV into pandas with column names matching DuckDB's schema."""
    # column name override aligned w/ src.database.CSV_COLUMNS
    names = [
        "app_id", "name", "release_date_raw", "estimated_owners",
        "peak_ccu", "required_age", "price", "discount", "dlc_count",
        "about_the_game", "supported_languages", "full_audio_languages",
        "reviews_text", "header_image", "website", "support_url",
        "support_email", "windows", "mac", "linux",
        "metacritic_score", "metacritic_url", "user_score",
        "positive", "negative", "score_rank", "achievements",
        "recommendations", "notes",
        "average_playtime_forever", "average_playtime_two_weeks",
        "median_playtime_forever", "median_playtime_two_weeks",
        "developers", "publishers", "categories", "genres", "tags",
        "screenshots", "movies",
    ]
    df = pd.read_csv(csv_path, header=0, names=names,
                     low_memory=False, on_bad_lines="skip")
    # add derived columns + coerce types (equivalent to duckdb load step)
    for col in ("positive", "negative", "price", "discount", "dlc_count",
                "peak_ccu", "required_age", "metacritic_score",
                "achievements", "recommendations",
                "average_playtime_forever", "median_playtime_forever"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["positive"] = df["positive"].fillna(0).astype("int64")
    df["negative"] = df["negative"].fillna(0).astype("int64")
    df["total_reviews"] = df["positive"] + df["negative"]
    df["positive_ratio"] = df["positive"] / df["total_reviews"].replace(0, pd.NA)
    df["release_date"] = pd.to_datetime(
        df["release_date_raw"], format="%b %d, %Y", errors="coerce"
    )
    df["release_year"] = df["release_date"].dt.year
    return df


def time_fn(fn, reps=REPS):
    """Return (median_ms, min_ms, max_ms) over `reps` runs."""
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples), min(samples), max(samples)


# benchmark case factories
def bench_filtered_search(con, df):
    def duck():
        con.execute("""
            SELECT name, price, positive_ratio, total_reviews, release_year
            FROM games
            WHERE genres LIKE '%RPG%'
              AND price <= 15.0
              AND positive_ratio >= 0.8
              AND total_reviews >= 50
            ORDER BY positive_ratio DESC, total_reviews DESC
            LIMIT 20;
        """).fetchall()

    def pd_():
        m = (
            df["genres"].fillna("").str.contains("RPG")
            & (df["price"] <= 15.0)
            & (df["positive_ratio"] >= 0.8)
            & (df["total_reviews"] >= 50)
        )
        return (
            df.loc[m, ["name", "price", "positive_ratio",
                       "total_reviews", "release_year"]]
              .sort_values(["positive_ratio", "total_reviews"],
                           ascending=[False, False])
              .head(20)
        )

    return duck, pd_


def bench_genre_aggregation(con, df):
    def duck():
        con.execute("""
            WITH exploded AS (
                SELECT UNNEST(string_split(genres, ',')) AS genre,
                       positive_ratio, total_reviews, price
                FROM games
                WHERE total_reviews >= 100
                  AND genres IS NOT NULL AND genres <> ''
            )
            SELECT genre, COUNT(*), AVG(positive_ratio) * 100,
                   AVG(price), SUM(total_reviews)
            FROM exploded
            GROUP BY genre
            ORDER BY AVG(positive_ratio) DESC;
        """).fetchall()

    def pd_():
        sub = df[(df["total_reviews"] >= 100)
                 & df["genres"].notna()
                 & (df["genres"] != "")].copy()
        sub["genre"] = sub["genres"].str.split(",")
        exploded = sub.explode("genre")
        agg = exploded.groupby("genre").agg(
            game_count=("price", "size"),
            avg_score=("positive_ratio", "mean"),
            avg_price=("price", "mean"),
            total_reviews_sum=("total_reviews", "sum"),
        ).sort_values("avg_score", ascending=False)
        return agg

    return duck, pd_


def bench_top_n(con, df):
    def duck():
        con.execute("""
            SELECT name, release_year, total_reviews, positive_ratio, price
            FROM games
            WHERE (tags LIKE '%Indie%' OR genres LIKE '%Indie%')
              AND release_year >= 2020
              AND total_reviews > 0
            ORDER BY total_reviews DESC
            LIMIT 10;
        """).fetchall()

    def pd_():
        m = (
            (df["tags"].fillna("").str.contains("Indie")
             | df["genres"].fillna("").str.contains("Indie"))
            & (df["release_year"] >= 2020)
            & (df["total_reviews"] > 0)
        )
        return (
            df.loc[m, ["name", "release_year", "total_reviews",
                       "positive_ratio", "price"]]
              .nlargest(10, "total_reviews")
        )

    return duck, pd_


def bench_hidden_gems(con, df):
    def duck():
        con.execute("""
            SELECT name, positive_ratio, total_reviews, release_year, price
            FROM games
            WHERE positive_ratio >= 0.90
              AND total_reviews BETWEEN 30 AND 500
              AND price <= 30.0
            ORDER BY positive_ratio DESC, total_reviews ASC
            LIMIT 20;
        """).fetchall()

    def pd_():
        m = (
            (df["positive_ratio"] >= 0.90)
            & (df["total_reviews"] >= 30)
            & (df["total_reviews"] <= 500)
            & (df["price"] <= 30.0)
        )
        return (
            df.loc[m, ["name", "positive_ratio", "total_reviews",
                       "release_year", "price"]]
              .sort_values(["positive_ratio", "total_reviews"],
                           ascending=[False, True])
              .head(20)
        )

    return duck, pd_


def bench_studio_leaderboard(con, df):
    def duck():
        con.execute("""
            SELECT developers, COUNT(*) AS games_shipped,
                   AVG(positive_ratio) * 100, SUM(total_reviews),
                   AVG(price)
            FROM games
            WHERE total_reviews >= 100
              AND developers IS NOT NULL AND developers <> ''
            GROUP BY developers
            HAVING COUNT(*) >= 3
            ORDER BY AVG(positive_ratio) DESC
            LIMIT 25;
        """).fetchall()

    def pd_():
        sub = df[(df["total_reviews"] >= 100)
                 & df["developers"].notna()
                 & (df["developers"] != "")]
        agg = sub.groupby("developers").agg(
            games_shipped=("price", "size"),
            avg_score=("positive_ratio", "mean"),
            total_reviews_sum=("total_reviews", "sum"),
            avg_price=("price", "mean"),
        )
        agg = agg[agg["games_shipped"] >= 3]
        return agg.sort_values("avg_score", ascending=False).head(25)

    return duck, pd_


BENCHES = [
    ("Q1: Filtered Search",        bench_filtered_search),
    ("Q2: Genre Aggregation",      bench_genre_aggregation),
    ("Q3: Top-N by Tag",           bench_top_n),
    ("Q4: Hidden Gems",            bench_hidden_gems),
    ("Q5: Studio Leaderboard",     bench_studio_leaderboard),
]


def run():
    csv_path = _pick_csv()
    print(f"Using CSV:  {csv_path}")
    csv_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"CSV size:   {csv_size_mb:,.1f} MB")

    # warm duckdb: triggers CSV load on first run, but just reopens columnar file for following runs
    t0 = time.perf_counter()
    con = get_connection()
    con.execute("SELECT COUNT(*) FROM games").fetchone()
    duck_setup_s = time.perf_counter() - t0

    duck_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"DuckDB file: {duck_size_mb:,.1f} MB "
          f"({duck_size_mb / csv_size_mb * 100:.0f}% of CSV)")
    print(f"DuckDB warm open: {duck_setup_s * 1000:,.0f} ms")

    # pandas setup cost (always the full read_csv)
    t0 = time.perf_counter()
    df = _load_pandas_df(csv_path)
    pandas_setup_s = time.perf_counter() - t0
    print(f"pandas read_csv + derived cols: {pandas_setup_s * 1000:,.0f} ms  "
          f"({df.shape[0]:,} rows x {df.shape[1]} cols)")

    print(f"\nEach query runs {REPS}× on warm caches. Times are median ms.\n")
    print(f"{'Query':28s} {'DuckDB (ms)':>14s} {'pandas (ms)':>14s} "
          f"{'Speedup':>10s}")
    print("-" * 72)

    results = []
    for label, factory in BENCHES:
        duck_fn, pd_fn = factory(con, df)
        duck_fn(); pd_fn()  # warm-up pass not counted
        d, _, _ = time_fn(duck_fn)
        p, _, _ = time_fn(pd_fn)
        speedup = p / d if d > 0 else float("inf")
        print(f"{label:28s} {d:14.1f} {p:14.1f} {speedup:9.1f}x")
        results.append((label, d, p, speedup))

    geo = statistics.geometric_mean([r[3] for r in results])
    print("-" * 72)
    print(f"{'Geomean speedup':28s} {'':14s} {'':14s} {geo:9.1f}x")
    con.close()
    return results


if __name__ == "__main__":
    run()
