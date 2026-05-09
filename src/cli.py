"""
Interactive CLI for the Steam Game Discovery Engine
"""

from __future__ import annotations

import sys
import textwrap

from .database import get_connection, db_info, explain, reset_database
from . import queries


# input helpers

def _prompt(label: str, default):
    raw = input(f"  {label} [{default}]: ").strip()
    if raw == "":
        return default
    return raw


def _prompt_str(label, default):   return str(_prompt(label, default))
def _prompt_float(label, default): return float(_prompt(label, default))
def _prompt_int(label, default):   return int(_prompt(label, default))


def _yes_no(label, default="n") -> bool:
    raw = input(f"  {label} [{default}]: ").strip().lower()
    if raw == "":
        raw = default
    return raw.startswith("y")


# output helpers

def _fmt_value(v, col_name: str):
    if v is None:
        return "—"
    if col_name == "positive_ratio" and isinstance(v, float):
        return f"{v * 100:5.1f}%"
    if col_name in ("avg_score_pct",) and isinstance(v, float):
        return f"{v:5.1f}%"
    if col_name == "price" and isinstance(v, float):
        return f"${v:.2f}" if v > 0 else "Free"
    if col_name == "avg_price" and isinstance(v, float):
        return f"${v:.2f}"
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    s = str(v)
    if len(s) > 45:
        s = s[:42] + "..."
    return s


def _print_table(cols: list[str], rows: list[tuple]):
    if not rows:
        print("  (no results)")
        return
    fmt_rows = [[_fmt_value(v, c) for v, c in zip(r, cols)] for r in rows]
    widths = [max(len(c), max(len(r[i]) for r in fmt_rows))
              for i, c in enumerate(cols)]
    header = "  " + "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    print(header)
    print("  " + "  ".join("-" * w for w in widths))
    for r in fmt_rows:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, widths)))


def _show_sql_and_params(sql: str, params: list):
    print("\n  SQL:")
    print(textwrap.indent(sql.strip(), "    "))
    print(f"\n  Parameters: {params}")


def _show_plan(con, sql: str, params: list, analyze: bool = False):
    bound = sql
    for p in params:
        lit = "'" + p.replace("'", "''") + "'" if isinstance(p, str) else str(p)
        bound = bound.replace("?", lit, 1)
    label = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
    print(f"\n  {label}:")
    print(textwrap.indent(explain(con, bound, analyze=analyze), "    "))


# query dispatchers

def run_filtered_search(con):
    print("\n  Filtered Search  (genre, price, rating)")
    print("  Internal: " + queries.QUERY_REGISTRY["1"]["internal"])
    genre       = _prompt_str("Genre (e.g. RPG, Indie, Action)", "RPG")
    max_price   = _prompt_float("Max price (USD)", 15.0)
    min_ratio   = _prompt_float("Min positive ratio (0-1)", 0.80)
    min_reviews = _prompt_int("Min total reviews", 50)
    limit       = _prompt_int("Limit", 20)

    r = queries.filtered_search(con, genre, max_price, min_ratio,
                                min_reviews, limit)
    _show_sql_and_params(r.sql, r.params)
    print(f"\n  Results ({len(r.rows)} rows):")
    _print_table(r.columns, r.rows)
    if _yes_no("  Show EXPLAIN plan?", "n"):
        _show_plan(con, r.sql, r.params)


def run_genre_aggregation(con):
    print("\n  Genre Aggregation")
    print("  Internal: " + queries.QUERY_REGISTRY["2"]["internal"])
    min_reviews = _prompt_int("Min reviews per game to include", 100)

    r = queries.genre_aggregation(con, min_reviews)
    _show_sql_and_params(r.sql, r.params)
    print(f"\n  Results ({len(r.rows)} rows):")
    _print_table(r.columns, r.rows)
    if _yes_no("  Show EXPLAIN ANALYZE plan?", "n"):
        _show_plan(con, r.sql, r.params, analyze=True)


def run_top_n(con):
    print("\n  Top-N by Tag")
    print("  Internal: " + queries.QUERY_REGISTRY["3"]["internal"])
    tag      = _prompt_str("Tag or genre (e.g. Indie, Atmospheric)", "Indie")
    min_year = _prompt_int("Released on or after year", 2020)
    limit    = _prompt_int("Top N", 10)

    r = queries.top_n_by_tag(con, tag, min_year, limit)
    _show_sql_and_params(r.sql, r.params)
    print(f"\n  Results ({len(r.rows)} rows):")
    _print_table(r.columns, r.rows)
    if _yes_no("  Show EXPLAIN plan?", "n"):
        _show_plan(con, r.sql, r.params)


def run_hidden_gems(con):
    print("\n  Hidden Gems")
    print("  Internal: " + queries.QUERY_REGISTRY["4"]["internal"])
    min_ratio   = _prompt_float("Min positive ratio (0-1)", 0.90)
    min_reviews = _prompt_int("Min total reviews", 30)
    max_reviews = _prompt_int("Max total reviews", 500)
    max_price   = _prompt_float("Max price (USD)", 30.0)
    limit       = _prompt_int("Limit", 20)

    r = queries.hidden_gems(con, min_ratio, min_reviews, max_reviews,
                            max_price, limit)
    _show_sql_and_params(r.sql, r.params)
    print(f"\n  Results ({len(r.rows)} rows):")
    _print_table(r.columns, r.rows)
    if _yes_no("  Show EXPLAIN plan?", "n"):
        _show_plan(con, r.sql, r.params)


def run_studio_leaderboard(con):
    print("\n  Studio Leaderboard")
    print("  Internal: " + queries.QUERY_REGISTRY["5"]["internal"])
    min_reviews = _prompt_int("Min reviews per game", 100)
    min_games   = _prompt_int("Min games shipped per studio", 3)
    limit       = _prompt_int("Limit", 25)

    r = queries.studio_leaderboard(con, min_reviews, min_games, limit)
    _show_sql_and_params(r.sql, r.params)
    print(f"\n  Results ({len(r.rows)} rows):")
    _print_table(r.columns, r.rows)
    if _yes_no("  Show EXPLAIN ANALYZE plan?", "n"):
        _show_plan(con, r.sql, r.params, analyze=True)


def show_db_info(con):
    info = db_info(con)
    print("\n  Database snapshot")
    print(f"    Rows:         {info['rows']:,}")
    print(f"    Columns:      {info['column_count']}")
    print(f"    DB file size: {info['db_size_mb']:.1f} MB")
    print(f"    Path:         {info['db_path']}")
    print(f"    Columns list: {', '.join(info['columns'])}")


def run_benchmark_action():
    # deferred import, so pandas is optional for people who only want to run queries
    from .benchmark import run as run_bench
    run_bench()


# menu loop

MENU = """
  Steam Game Discovery Engine  (DuckDB-powered):
  1) Filtered Search        (Column Pruning)
  2) Genre Aggregation      (Vectorized Hash Aggregate)
  3) Top-N by Tag           (Top-N Heap Sort)
  4) Hidden Gems            (Zone-Map Filtering)
  5) Studio Leaderboard     (Hash Aggregate + HAVING)
  ----
  i) Database info
  b) Run DuckDB vs pandas benchmark
  r) Reset database (rebuild from CSV on next run)
  q) Quit
"""


def main():
    con = get_connection()
    while True:
        print(MENU)
        choice = input("  Choice: ").strip().lower()
        if choice == "q":
            break
        try:
            if choice == "1": run_filtered_search(con)
            elif choice == "2": run_genre_aggregation(con)
            elif choice == "3": run_top_n(con)
            elif choice == "4": run_hidden_gems(con)
            elif choice == "5": run_studio_leaderboard(con)
            elif choice == "i": show_db_info(con)
            elif choice == "b":
                con.close()
                run_benchmark_action()
                con = get_connection()
            elif choice == "r":
                con.close()
                reset_database()
                print("  [reset] Will rebuild on next start.")
                con = get_connection()
            else:
                print(f"  Unknown choice: {choice!r}")
        except (ValueError, TypeError) as e:
            print(f"  Input error: {e}")
        except KeyboardInterrupt:
            print("\n  (interrupted)")
        except Exception as e:
            print(f"  Error: {type(e).__name__}: {e}")

    con.close()
    print("  Goodbye.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Goodbye.")
        sys.exit(0)
