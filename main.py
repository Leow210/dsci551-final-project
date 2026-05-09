#!/usr/bin/env python3
"""
Entry point for the Steam Game Discovery Engine.

Usage:
    python main.py              # launch interactive CLI (default)
    python main.py cli          # same
    python main.py benchmark    # DuckDB vs pandas benchmark
    python main.py info         # database snapshot
    python main.py reset        # delete .duckdb file (forces CSV reload)
"""

import sys


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "cli"

    if cmd in ("cli", "interactive"):
        from src.cli import main as cli_main
        cli_main()
    elif cmd in ("benchmark", "bench"):
        from src.benchmark import run
        run()
    elif cmd == "info":
        from src.database import get_connection, db_info
        con = get_connection()
        info = db_info(con)
        print(f"Rows:     {info['rows']:,}")
        print(f"Columns:  {info['column_count']}")
        print(f"DB size:  {info['db_size_mb']:.1f} MB")
        print(f"DB path:  {info['db_path']}")
        con.close()
    elif cmd == "reset":
        from src.database import reset_database
        reset_database()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
