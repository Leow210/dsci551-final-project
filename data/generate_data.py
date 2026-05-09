"""
generate a synthetic Steam Games CSV that matches the real Kaggle dataset's schema (40 columns) for reproducibility when the real 389 MB file is unavailable.

writes to: data/steam_games_synthetic.csv
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(551)

OUT_PATH = os.path.join(os.path.dirname(__file__), "steam_games_synthetic.csv")
N_ROWS = 60_000  # smaller than real (~100k)

GENRES = [
    "Action", "Adventure", "RPG", "Strategy", "Simulation", "Sports",
    "Racing", "Indie", "Casual", "Massively Multiplayer", "Free to Play",
    "Early Access",
]
TAGS_POOL = [
    "Singleplayer", "Multiplayer", "Co-op", "Open World", "Story Rich",
    "Atmospheric", "Pixel Graphics", "2D", "3D", "Difficult", "Relaxing",
    "Funny", "Cute", "Dark", "Retro", "Cyberpunk", "Fantasy", "Sci-fi",
    "Zombies", "Post-apocalyptic", "Building", "Crafting", "Exploration",
    "Turn-Based", "Real-Time", "Roguelike", "VR", "Anime",
]
CATEGORIES_POOL = [
    "Single-player", "Multi-player", "PvP", "Co-op",
    "Steam Achievements", "Steam Cloud", "Steam Trading Cards",
    "Family Sharing", "Full controller support", "Partial controller support",
]
LANGS = ["English", "French", "German", "Spanish - Spain", "Russian",
         "Japanese", "Korean", "Simplified Chinese", "Portuguese - Brazil",
         "Italian", "Polish"]

WORDS_A = ["Dark", "Lost", "Ancient", "Eternal", "Broken", "Silent",
           "Crimson", "Shadow", "Frozen", "Golden", "Iron", "Mystic",
           "Sacred", "Savage", "Forgotten", "Hidden", "Rising", "Fallen",
           "Starlight", "Moonlit", "Neon", "Cyber", "Pixel", "Retro",
           "Last", "First"]
WORDS_B = ["Kingdom", "Quest", "Empire", "Legends", "Chronicles", "Saga",
           "Odyssey", "Tales", "Realms", "Lands", "World", "Nexus",
           "Paradox", "Echoes", "Shadows", "Hunter", "Warrior", "Mage",
           "Rogue", "Knight", "Runner", "Rider", "Builder", "Crafter"]
WORDS_C = ["", "", "", "", ": Origins", ": Reloaded", " 2", " Reborn",
           " Uprising", " Untold", " Unleashed"]

DEV_PREFIXES = ["Pixel", "Byte", "Indie", "Hyper", "Nova", "Blue", "Red",
                "Sharp", "Quantum", "Ember", "Echo", "Orbit", "Paper",
                "Midnight", "Crimson", "Stellar", "Iron", "Storm"]
DEV_SUFFIXES = ["Games", "Studios", "Interactive", "Labs", "Works",
                "Entertainment", "Digital", "Forge", "Collective",
                "Softworks"]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
          "Oct", "Nov", "Dec"]

# Kaggle-style "Estimated owners" buckets
OWNER_BUCKETS = [
    "0 - 0", "0 - 20000", "20000 - 50000", "50000 - 100000",
    "100000 - 200000", "200000 - 500000", "500000 - 1000000",
    "1000000 - 2000000", "2000000 - 5000000", "5000000 - 10000000",
    "10000000 - 20000000", "20000000 - 50000000",
]
OWNER_WEIGHTS = [5, 40, 20, 12, 8, 6, 4, 2, 1.5, 1, 0.4, 0.1]


def rand_name():
    return f"{random.choice(WORDS_A)} {random.choice(WORDS_B)}{random.choice(WORDS_C)}".strip()


def rand_studio():
    return f"{random.choice(DEV_PREFIXES)} {random.choice(DEV_SUFFIXES)}"


def rand_date():
    start = datetime(2003, 9, 12)
    end = datetime(2025, 12, 31)
    delta_days = (end - start).days
    r = random.random() ** 0.5  # skew toward recent
    d = start + timedelta(days=int(delta_days * r))
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def rand_price():
    bucket = random.choices(
        ["free", "cheap", "mid", "full", "premium"],
        weights=[15, 35, 30, 15, 5],
    )[0]
    if bucket == "free":
        return 0.00
    if bucket == "cheap":
        return round(random.uniform(0.99, 9.99), 2)
    if bucket == "mid":
        return round(random.uniform(9.99, 19.99), 2)
    if bucket == "full":
        return round(random.uniform(19.99, 39.99), 2)
    return round(random.uniform(39.99, 69.99), 2)


def rand_reviews():
    bucket = random.choices(
        ["none", "tiny", "small", "medium", "large", "mega"],
        weights=[10, 40, 25, 15, 8, 2],
    )[0]
    if bucket == "none":
        return 0, 0
    if bucket == "tiny":
        total = random.randint(1, 50)
    elif bucket == "small":
        total = random.randint(50, 500)
    elif bucket == "medium":
        total = random.randint(500, 5_000)
    elif bucket == "large":
        total = random.randint(5_000, 50_000)
    else:
        total = random.randint(50_000, 1_000_000)
    ratio = max(0.1, min(0.99, random.gauss(0.78, 0.15)))
    pos = int(total * ratio)
    neg = total - pos
    return pos, neg


def rand_genres():
    k = random.choices([1, 2, 3, 4], weights=[1, 4, 4, 2])[0]
    return ",".join(random.sample(GENRES, k))


def rand_tags():
    k = random.randint(3, 10)
    return ",".join(random.sample(TAGS_POOL, k))


def rand_categories():
    k = random.randint(2, 6)
    return ",".join(random.sample(CATEGORIES_POOL, k))


def rand_langs():
    k = random.randint(1, 6)
    chosen = random.sample(LANGS, k)
    # Match Kaggle format: Python-list-ish "['English', 'French']"
    inner = ", ".join(f"'{l}'" for l in chosen)
    return f"[{inner}]"


def rand_about():
    # Keep it short-ish but representative — the real "About the game"
    # column often has hundreds or thousands of characters. A rough
    # 200-400 char synthetic blob lets column-pruning still matter.
    adjectives = ["epic", "thrilling", "mysterious", "hilarious", "brutal",
                  "cozy", "challenging", "atmospheric", "fast-paced"]
    nouns = ["adventure", "journey", "quest", "challenge", "mystery",
            "war", "story", "puzzle"]
    verbs = ["explore", "fight", "survive", "build", "craft", "escape",
            "discover"]
    sentences = []
    for _ in range(random.randint(2, 5)):
        sentences.append(
            f"An {random.choice(adjectives)} {random.choice(nouns)} where "
            f"you must {random.choice(verbs)} "
            f"{random.choice(['alone', 'with friends', 'against the world', 'through time'])}."
        )
    return " ".join(sentences)


HEADER = [
    "AppID", "Name", "Release date", "Estimated owners", "Peak CCU",
    "Required age", "Price", "Discount", "DLC count", "About the game",
    "Supported languages", "Full audio languages", "Reviews",
    "Header image", "Website", "Support url", "Support email",
    "Windows", "Mac", "Linux", "Metacritic score", "Metacritic url",
    "User score", "Positive", "Negative", "Score rank", "Achievements",
    "Recommendations", "Notes", "Average playtime forever",
    "Average playtime two weeks", "Median playtime forever",
    "Median playtime two weeks", "Developers", "Publishers",
    "Categories", "Genres", "Tags", "Screenshots", "Movies",
]


def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    print(f"Generating {N_ROWS:,} rows of synthetic Steam data -> {OUT_PATH}")

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for i in range(N_ROWS):
            app_id = 10 + i
            name = rand_name()
            release_date = rand_date()
            est_owners = random.choices(OWNER_BUCKETS, weights=OWNER_WEIGHTS)[0]
            peak_ccu = 0
            pos, neg = rand_reviews()
            total = pos + neg
            if total > 1000:
                peak_ccu = random.randint(10, int(total / 20))
            required_age = random.choices([0, 13, 16, 18], weights=[80, 8, 7, 5])[0]
            price = rand_price()
            discount = random.choices([0, 10, 25, 50, 75], weights=[80, 6, 6, 6, 2])[0]
            dlc_count = random.choices([0, 1, 2, 5, 10], weights=[70, 15, 8, 5, 2])[0]
            about = rand_about()
            langs = rand_langs()
            audio_langs = rand_langs() if random.random() < 0.4 else "[]"
            reviews = ""  # often left empty
            header_img = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{app_id}/header.jpg"
            website = f"https://example.com/{app_id}" if random.random() < 0.4 else ""
            support_url = f"https://support.example.com/{app_id}" if random.random() < 0.3 else ""
            support_email = f"support{app_id}@example.com" if random.random() < 0.35 else ""
            windows = "True"
            mac = "True" if random.random() < 0.35 else "False"
            linux = "True" if random.random() < 0.25 else "False"
            meta_score = random.choices(
                [0, random.randint(50, 95)], weights=[85, 15],
            )[0]
            meta_url = (f"https://www.metacritic.com/game/{app_id}"
                        if meta_score > 0 else "")
            user_score = 0  # often 0
            score_rank = ""
            achievements = random.choices(
                [0, random.randint(1, 15), random.randint(15, 50),
                 random.randint(50, 200)],
                weights=[30, 35, 25, 10],
            )[0]
            recs = int(total * random.uniform(0.2, 0.7)) if total else 0
            notes = ""
            avg_forever = random.randint(0, 8000) if total else 0
            avg_two_weeks = int(avg_forever * random.uniform(0.02, 0.1))
            med_forever = int(avg_forever * random.uniform(0.3, 0.9))
            med_two_weeks = int(avg_two_weeks * random.uniform(0.3, 0.9))
            developer = rand_studio()
            publisher = developer if random.random() < 0.6 else rand_studio()
            categories = rand_categories()
            genres = rand_genres()
            tags = rand_tags()
            screenshots = (
                f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/"
                f"{app_id}/ss_001.jpg,"
                f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/"
                f"{app_id}/ss_002.jpg"
            )
            movies = ""

            w.writerow([
                app_id, name, release_date, est_owners, peak_ccu,
                required_age, f"{price:.2f}", discount, dlc_count, about,
                langs, audio_langs, reviews, header_img, website,
                support_url, support_email, windows, mac, linux,
                meta_score, meta_url, user_score, pos, neg, score_rank,
                achievements, recs, notes, avg_forever, avg_two_weeks,
                med_forever, med_two_weeks, developer, publisher,
                categories, genres, tags, screenshots, movies,
            ])
            if (i + 1) % 10_000 == 0:
                print(f"  ... {i + 1:,} rows")

    size_mb = os.path.getsize(OUT_PATH) / (1024 * 1024)
    print(f"Done. Wrote {N_ROWS:,} rows ({size_mb:.1f} MB)")
    

if __name__ == "__main__":
    main()
