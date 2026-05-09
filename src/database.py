"""
DuckDB connection + schema setup for the real kaggle steam games dataset

expected input CSV columns (order-sensitive):

AppID, Name, Release date, Estimated owners, Peak CCU, Required age,
Price, Discount, DLC count, About the game, Supported languages,
Full audio languages, Reviews, Header image, Website, Support url,
Support email, Windows, Mac, Linux, Metacritic score, Metacritic url,
User score, Positive, Negative, Score rank, Achievements,
Recommendations, Notes, Average playtime forever,
Average playtime two weeks, Median playtime forever,
Median playtime two weeks, Developers, Publishers, Categories,
Genres, Tags, Screenshots, Movies

two derived columns computed on load:
    total_reviews  = positive + negative
    positive_ratio = positive / NULLIF(positive + negative, 0)
"""

from __future__ import annotations

import os
import time
import duckdb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "steam.duckdb")

REAL_CSV = os.path.join(DATA_DIR, "games.csv")
SYNTHETIC_CSV = os.path.join(DATA_DIR, "steam_games_synthetic.csv")


# column names used internally. order must match the csv column order.

CSV_COLUMNS = [
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

CREATE_GAMES_SQL = """
CREATE TABLE IF NOT EXISTS games (
    app_id                     BIGINT,
    name                       VARCHAR,
    release_date               DATE,
    release_year               INTEGER,
    estimated_owners           VARCHAR,
    peak_ccu                   INTEGER,
    required_age               INTEGER,
    price                      DOUBLE,
    discount                   INTEGER,
    dlc_count                  INTEGER,
    about_the_game             VARCHAR,
    supported_languages        VARCHAR,
    full_audio_languages       VARCHAR,
    reviews_text               VARCHAR,
    header_image               VARCHAR,
    website                    VARCHAR,
    support_url                VARCHAR,
    support_email              VARCHAR,
    windows                    BOOLEAN,
    mac                        BOOLEAN,
    linux                      BOOLEAN,
    metacritic_score           INTEGER,
    metacritic_url             VARCHAR,
    user_score                 INTEGER,
    positive                   INTEGER,
    negative                   INTEGER,
    score_rank                 VARCHAR,
    achievements               INTEGER,
    recommendations            INTEGER,
    notes                      VARCHAR,
    average_playtime_forever   INTEGER,
    average_playtime_two_weeks INTEGER,
    median_playtime_forever    INTEGER,
    median_playtime_two_weeks  INTEGER,
    developers                 VARCHAR,
    publishers                 VARCHAR,
    categories                 VARCHAR,
    genres                     VARCHAR,
    tags                       VARCHAR,
    screenshots                VARCHAR,
    movies                     VARCHAR,
    total_reviews              INTEGER,
    positive_ratio             DOUBLE
);
"""


def _pick_csv_path(explicit: str | None) -> str:
    """Choose which CSV to load. Preference: explicit > real > synthetic."""
    if explicit:
        if not os.path.exists(explicit):
            raise FileNotFoundError(f"CSV not found: {explicit}")
        return explicit
    if os.path.exists(REAL_CSV):
        return REAL_CSV
    if os.path.exists(SYNTHETIC_CSV):
        return SYNTHETIC_CSV
    raise FileNotFoundError(
        "No CSV found. Either place the Kaggle Steam Games dataset at\n"
        f"  {REAL_CSV}\n"
        "or run `python data/generate_data.py` to produce a synthetic one."
    )


def _load_csv_to_games(con, csv_path: str) -> int:
    """Read the CSV and INSERT into `games` in one SQL statement."""
    # passing `columns=` specifies both name and type, overriding the header row
    types_sql = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in CSV_COLUMNS) + "}"

    sql = f"""
    INSERT INTO games
    SELECT
        TRY_CAST(app_id AS BIGINT)                                AS app_id,
        name,
        TRY_STRPTIME(release_date_raw, '%b %d, %Y')               AS release_date,
        EXTRACT(YEAR FROM TRY_STRPTIME(release_date_raw, '%b %d, %Y'))::INT
                                                                  AS release_year,
        estimated_owners,
        TRY_CAST(peak_ccu AS INTEGER)                             AS peak_ccu,
        TRY_CAST(required_age AS INTEGER)                         AS required_age,
        TRY_CAST(price AS DOUBLE)                                 AS price,
        TRY_CAST(discount AS INTEGER)                             AS discount,
        TRY_CAST(dlc_count AS INTEGER)                            AS dlc_count,
        about_the_game,
        supported_languages,
        full_audio_languages,
        reviews_text,
        header_image,
        website,
        support_url,
        support_email,
        lower(windows) = 'true'                                   AS windows,
        lower(mac)     = 'true'                                   AS mac,
        lower(linux)   = 'true'                                   AS linux,
        TRY_CAST(metacritic_score AS INTEGER)                     AS metacritic_score,
        metacritic_url,
        TRY_CAST(user_score AS INTEGER)                           AS user_score,
        COALESCE(TRY_CAST(positive AS INTEGER), 0)                AS positive,
        COALESCE(TRY_CAST(negative AS INTEGER), 0)                AS negative,
        score_rank,
        TRY_CAST(achievements AS INTEGER)                         AS achievements,
        TRY_CAST(recommendations AS INTEGER)                      AS recommendations,
        notes,
        TRY_CAST(average_playtime_forever AS INTEGER)             AS average_playtime_forever,
        TRY_CAST(average_playtime_two_weeks AS INTEGER)           AS average_playtime_two_weeks,
        TRY_CAST(median_playtime_forever AS INTEGER)              AS median_playtime_forever,
        TRY_CAST(median_playtime_two_weeks AS INTEGER)            AS median_playtime_two_weeks,
        developers,
        publishers,
        categories,
        genres,
        tags,
        screenshots,
        movies,
        COALESCE(TRY_CAST(positive AS INTEGER), 0)
          + COALESCE(TRY_CAST(negative AS INTEGER), 0)            AS total_reviews,
        CASE
          WHEN COALESCE(TRY_CAST(positive AS INTEGER), 0)
             + COALESCE(TRY_CAST(negative AS INTEGER), 0) = 0
          THEN NULL
          ELSE COALESCE(TRY_CAST(positive AS INTEGER), 0)::DOUBLE
               / (COALESCE(TRY_CAST(positive AS INTEGER), 0)
                  + COALESCE(TRY_CAST(negative AS INTEGER), 0))
        END                                                       AS positive_ratio
    FROM read_csv(
        '{csv_path}',
        header=True,
        columns={types_sql},
        sample_size=-1,
        ignore_errors=True,
        quote='"',
        escape='"'
    );
    """
    con.execute(sql)
    return con.execute("SELECT COUNT(*) FROM games").fetchone()[0]


def get_connection(csv_path: str | None = None,
                   read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Return a connection to the persistent .duckdb file, creating the
    schema and loading the CSV on first run."""
    first_time = not os.path.exists(DB_PATH)
    con = duckdb.connect(DB_PATH, read_only=False)

    if first_time:
        chosen = _pick_csv_path(csv_path)
        size_mb = os.path.getsize(chosen) / 1024 / 1024
        print(f"[setup] First run — loading CSV: {chosen}")
        print(f"[setup] Source size: {size_mb:.1f} MB")
        con.execute(CREATE_GAMES_SQL)

        t0 = time.perf_counter()
        n = _load_csv_to_games(con, chosen)
        elapsed = time.perf_counter() - t0
        print(f"[setup] Loaded {n:,} rows in {elapsed:.1f}s")
        db_mb = os.path.getsize(DB_PATH) / 1024 / 1024
        print(f"[setup] DuckDB file: {db_mb:.1f} MB "
              f"({db_mb / size_mb * 100:.0f}% of CSV — columnar compression)")

    if read_only:
        con.close()
        con = duckdb.connect(DB_PATH, read_only=True)

    return con


def reset_database():
    """Delete the persistent .duckdb file so the next run rebuilds it."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[reset] Removed {DB_PATH}")


def explain(con, sql: str, analyze: bool = False) -> str:
    """Return DuckDB's physical plan for a query."""
    prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN"
    rows = con.execute(f"{prefix} {sql}").fetchall()
    return "\n".join(r[1] for r in rows)


def db_info(con) -> dict:
    """Quick snapshot of DB state — useful for the demo."""
    row_count = con.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    columns = [c[0] for c in con.execute("DESCRIBE games").fetchall()]
    return {
        "rows": row_count,
        "db_path": DB_PATH,
        "db_size_mb": size_bytes / (1024 * 1024),
        "column_count": len(columns),
        "columns": columns,
    }


if __name__ == "__main__":
    con = get_connection()
    info = db_info(con)
    print(f"\nRows:     {info['rows']:,}")
    print(f"Columns:  {info['column_count']}")
    print(f"DB size:  {info['db_size_mb']:.1f} MB")
    print(f"DB path:  {info['db_path']}")
    con.close()
