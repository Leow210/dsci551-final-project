from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueryResult:
    sql: str
    params: list
    columns: list[str]
    rows: list[tuple]


# query 1: filtered search  ->  column pruning
# reads 6 of 43 columns. heavy text columns (about_the_game, reviews_text, screenshots etc.) are never touched.
FILTERED_SEARCH_SQL = """
SELECT
    name,
    price,
    positive_ratio,
    total_reviews,
    release_year
FROM games
WHERE genres       LIKE '%' || ? || '%'
  AND price        <= ?
  AND positive_ratio >= ?
  AND total_reviews  >= ?
ORDER BY positive_ratio DESC, total_reviews DESC
LIMIT ?;
"""


def filtered_search(con, genre: str, max_price: float,
                    min_ratio: float = 0.8,
                    min_reviews: int = 50,
                    limit: int = 20) -> QueryResult:
    params = [genre, max_price, min_ratio, min_reviews, limit]
    rows = con.execute(FILTERED_SEARCH_SQL, params).fetchall()
    cols = ["name", "price", "positive_ratio", "total_reviews", "release_year"]
    return QueryResult(FILTERED_SEARCH_SQL, params, cols, rows)


# query 2: genre aggregation  ->  vectorized hash aggregate
GENRE_AGG_SQL = """
WITH exploded AS (
    SELECT
        UNNEST(string_split(genres, ',')) AS genre,
        positive_ratio,
        total_reviews,
        price
    FROM games
    WHERE total_reviews >= ?
      AND genres IS NOT NULL
      AND genres <> ''
)
SELECT
    genre,
    COUNT(*)                               AS game_count,
    ROUND(AVG(positive_ratio) * 100, 2)    AS avg_score_pct,
    ROUND(AVG(price), 2)                   AS avg_price,
    SUM(total_reviews)                     AS total_reviews_in_genre
FROM exploded
GROUP BY genre
ORDER BY avg_score_pct DESC;
"""


def genre_aggregation(con, min_reviews: int = 100) -> QueryResult:
    params = [min_reviews]
    rows = con.execute(GENRE_AGG_SQL, params).fetchall()
    cols = ["genre", "game_count", "avg_score_pct",
            "avg_price", "total_reviews_in_genre"]
    return QueryResult(GENRE_AGG_SQL, params, cols, rows)


# query 3: top-n by tag + year  ->  column pruning + top-n heap sort
TOP_N_SQL = """
SELECT
    name,
    release_year,
    total_reviews,
    positive_ratio,
    price
FROM games
WHERE (tags LIKE '%' || ? || '%' OR genres LIKE '%' || ? || '%')
  AND release_year >= ?
  AND total_reviews > 0
ORDER BY total_reviews DESC
LIMIT ?;
"""


def top_n_by_tag(con, tag: str, min_year: int = 2020,
                 limit: int = 10) -> QueryResult:
    params = [tag, tag, min_year, limit]
    rows = con.execute(TOP_N_SQL, params).fetchall()
    cols = ["name", "release_year", "total_reviews", "positive_ratio", "price"]
    return QueryResult(TOP_N_SQL, params, cols, rows)


# query 4: hidden gems  ->  zone-map filtering + column pruning
# selective filter on positive_ratio lets duckdb skip entire row groups
HIDDEN_GEMS_SQL = """
SELECT
    name,
    positive_ratio,
    total_reviews,
    release_year,
    price
FROM games
WHERE positive_ratio >= ?
  AND total_reviews BETWEEN ? AND ?
  AND price <= ?
ORDER BY positive_ratio DESC, total_reviews ASC
LIMIT ?;
"""


def hidden_gems(con,
                min_ratio: float = 0.90,
                min_reviews: int = 30,
                max_reviews: int = 500,
                max_price: float = 30.0,
                limit: int = 20) -> QueryResult:
    params = [min_ratio, min_reviews, max_reviews, max_price, limit]
    rows = con.execute(HIDDEN_GEMS_SQL, params).fetchall()
    cols = ["name", "positive_ratio", "total_reviews", "release_year", "price"]
    return QueryResult(HIDDEN_GEMS_SQL, params, cols, rows)


# query 5: studio leaderboard  ->  hash aggregate + HAVING + sort
STUDIO_LEADERBOARD_SQL = """
SELECT
    developers                             AS developer,
    COUNT(*)                               AS games_shipped,
    ROUND(AVG(positive_ratio) * 100, 2)    AS avg_score_pct,
    SUM(total_reviews)                     AS total_player_reviews,
    ROUND(AVG(price), 2)                   AS avg_price
FROM games
WHERE total_reviews >= ?
  AND developers IS NOT NULL
  AND developers <> ''
GROUP BY developers
HAVING COUNT(*) >= ?
ORDER BY avg_score_pct DESC, games_shipped DESC
LIMIT ?;
"""


def studio_leaderboard(con,
                       min_reviews_per_game: int = 100,
                       min_games: int = 3,
                       limit: int = 25) -> QueryResult:
    params = [min_reviews_per_game, min_games, limit]
    rows = con.execute(STUDIO_LEADERBOARD_SQL, params).fetchall()
    cols = ["developer", "games_shipped", "avg_score_pct",
            "total_player_reviews", "avg_price"]
    return QueryResult(STUDIO_LEADERBOARD_SQL, params, cols, rows)


# helper: enumerate queries for CLI + demo
QUERY_REGISTRY = {
    "1": {
        "name": "Filtered Search (by genre, price, rating)",
        "internal": "Column Pruning — reads 6 of 43 columns; zone-map "
                    "pushdown on price + total_reviews",
        "fn": filtered_search,
    },
    "2": {
        "name": "Genre Aggregation (average score by genre)",
        "internal": "Vectorized Hash Aggregate over 2,048-row DataChunks; "
                    "UNNEST of comma-split genres stays in-engine",
        "fn": genre_aggregation,
    },
    "3": {
        "name": "Top-N by Tag (e.g. top 10 Indie games since 2020)",
        "internal": "Column pruning + Top-N heap sort — O(n log k) not "
                    "O(n log n)",
        "fn": top_n_by_tag,
    },
    "4": {
        "name": "Hidden Gems (high rating, low visibility)",
        "internal": "Zone-map filtering on positive_ratio min/max; whole "
                    "row groups skipped without a disk read",
        "fn": hidden_gems,
    },
    "5": {
        "name": "Studio Leaderboard (developers ranked by score)",
        "internal": "Hash Aggregate keyed by developer with HAVING "
                    "pushed into the aggregation step",
        "fn": studio_leaderboard,
    },
}
