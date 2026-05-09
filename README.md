# Steam Game Discovery Engine

**DSCI 551 Course Project Spring 2026**
**Author:** Leo Rosales (solo project)
**Database:** [DuckDB](https://duckdb.org/) (embedded columnar OLAP)
**Dataset:** Steam Games dataset (Kaggle) ~100k rows, 40 columns

An interactive CLI that runs five discovery queries over the Steam catalog,
each one mapped to a specific DuckDB internal (columnar storage,
vectorized execution, zone-map filtering). Press `y` at the EXPLAIN prompt
after any query to see the physical plan and confirm the mapping live.

## Setup

Requirements: Python 3.10+ and pip. No API keys, no environment variables,
no external services.

```bash
git clone git@github.com:Leow210/dsci551-final-project.git
cd dsci551-final-project
pip install -r requirements.txt
```

## Data

Pick **one** of the two options. The loader auto-detects which CSV is
present and uses it; you do not need to configure anything.

**Option A: Real Kaggle dataset (~389 MB).**
Download from
[kaggle.com/datasets/fronkongames/steam-games-dataset](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset)
and save the CSV as `data/games.csv`.

**Option B: Synthetic dataset (no download needed).**
```bash
python data/generate_data.py
```
Produces `data/steam_games_synthetic.csv` (~49 MB, 60k rows) with the
same schema and distribution shape as the real CSV.

## Run

```bash
python main.py              # interactive CLI (default)
python main.py info         # database snapshot (rows, cols, file size)
python main.py benchmark    # DuckDB vs pandas timing comparison
python main.py reset        # delete .duckdb (forces CSV reload)
```

The first run loads the CSV into a persistent DuckDB file
(`data/steam.duckdb`, ~2 s for synthetic, ~20 s for the real file).
Subsequent runs reuse it.

## What the CLI does

Five canned discovery queries with parameters:

| # | Query | DuckDB internal |
|---|-------|----------------|
| 1 | Filtered Search (genre + price + rating) | Column pruning, zone-map pushdown |
| 2 | Genre Aggregation (avg score per genre) | Vectorized hash aggregate |
| 3 | Top-N by Tag (most-reviewed since year X) | Top-N heap sort |
| 4 | Hidden Gems (high rating, low visibility) | Zone-map filtering |
| 5 | Studio Leaderboard (devs ranked, with HAVING) | Hash aggregate + HAVING |

Each query prints its SQL, parameters, a result table, and (optionally)
the DuckDB physical plan.

## Reproducing results
 
`python main.py benchmark` runs each query 5 times on warm caches and
reports the median. Sample output from a run on the real 371 MB Kaggle
CSV (122,611 rows, M4 MacBook Pro):
 
```
Using CSV:   data/games.csv
CSV size:    371.1 MB
DuckDB file: 567.3 MB (153% of CSV)
DuckDB warm open:  11 ms
pandas read_csv + derived cols: 4,605 ms (122,611 rows x 44 cols)
 
Query                       DuckDB (ms)   pandas (ms)   Speedup
---------------------------------------------------------------
Q1: Filtered Search                7.8          27.3       3.5x
Q2: Genre Aggregation              8.1         134.0      16.6x
Q3: Top-N by Tag                  13.0          53.6       4.1x
Q4: Hidden Gems                    4.3           6.8       1.6x
Q5: Studio Leaderboard             7.4         333.9      45.3x
---------------------------------------------------------------
Geomean speedup                                            7.0x
```
 
DuckDB wins on every query. The largest gaps are on the aggregations
(Q2, Q5); the smallest is on the most selective filter (Q4) where
there's less data for the vectorized engine to amortize over. Absolute
numbers vary, but relative shape is reproducible.

## Project structure

```
steam_discovery/
├── main.py                # entry point (cli / explain / benchmark / info / reset)
├── requirements.txt
├── README.md
├── data/
│   ├── generate_data.py   # synthetic CSV generator
│   ├── games.csv          # real Kaggle file (you provide; not checked in)
│   └── steam.duckdb       # persistent DB (created on first run)
└── src/
    ├── database.py        # DuckDB connection, schema, CSV loader, EXPLAIN helper
    ├── queries.py         # parameterized SQL for all 5 queries
    ├── cli.py             # interactive menu UI
    └── benchmark.py       # DuckDB vs pandas timing
```

## References

- DuckDB docs: https://duckdb.org/docs/
- Raasveldt & Mühleisen, *DuckDB: an Embeddable Analytical Database*, SIGMOD 2019.
- Fronkon Games, Steam Games Dataset (Kaggle).
