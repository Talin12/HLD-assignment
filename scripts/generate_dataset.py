#!/usr/bin/env python3
"""
Generate ~100k synthetic search queries and print them as CSV lines to stdout:
    query,frequency,last_searched_at,recency_score

The dataset intentionally follows a power-law (Zipf) distribution so that a
small number of high-frequency terms dominate, mirroring real search logs.
"""

import sys
import math
import random
import time

# ── Seed corpora ─────────────────────────────────────────────────────────────

TECH_PRODUCTS = [
    "iphone", "macbook", "ipad", "apple watch", "airpods", "samsung galaxy",
    "pixel phone", "surface laptop", "kindle", "echo dot", "fire tv", "roku",
    "nvidia rtx", "amd radeon", "intel core", "ryzen processor", "raspberry pi",
    "arduino", "jetson nano", "oculus quest", "playstation", "xbox series",
    "nintendo switch", "steam deck", "gopro", "drone", "smart tv",
    "mechanical keyboard", "gaming mouse", "ultrawide monitor", "usb hub",
    "ssd drive", "nvme storage", "external hard drive", "webcam", "microphone",
]

PROGRAMMING_TERMS = [
    "python tutorial", "javascript async await", "react hooks", "vue.js guide",
    "fastapi example", "django rest framework", "flask authentication",
    "typescript generics", "golang goroutines", "rust ownership",
    "kubernetes deployment", "docker compose", "terraform aws", "ansible playbook",
    "sql join types", "postgresql indexing", "redis caching", "mongodb aggregation",
    "elasticsearch query", "kafka consumer", "rabbitmq tutorial",
    "git rebase vs merge", "github actions ci", "linux shell scripting",
    "regex patterns", "algorithm complexity", "binary search tree",
    "dynamic programming", "graph traversal", "sorting algorithms",
    "design patterns", "solid principles", "microservices architecture",
    "rest api design", "graphql schema", "websocket python",
    "machine learning basics", "neural network tutorial", "pandas dataframe",
    "numpy array operations", "scikit-learn classification",
]

COMMON_QUERIES = [
    "how to", "what is", "best way to", "difference between", "tutorial for",
    "example of", "install guide", "error fix", "not working", "vs comparison",
    "review", "alternatives to", "open source", "free tool", "download",
    "latest version", "documentation", "github repo", "stack overflow",
    "youtube tutorial", "course", "book recommendation", "cheat sheet",
    "roadmap", "career path", "salary", "interview questions", "project ideas",
]

MODIFIERS = [
    "2024", "2025", "online", "free", "best", "top 10", "for beginners",
    "advanced", "complete guide", "quick start", "step by step", "example",
    "in python", "in javascript", "on linux", "on mac", "on windows",
]


def zipf_weight(rank: int, s: float = 1.1) -> float:
    """Zipf law: weight ∝ 1/rank^s"""
    return 1.0 / (rank ** s)


def generate_queries(target: int = 120_000) -> list:
    rng = random.Random(42)
    base_terms = []

    # Build base terms from corpora
    for prod in TECH_PRODUCTS:
        base_terms.append(prod)
        for mod in rng.sample(MODIFIERS, k=3):
            base_terms.append(f"{prod} {mod}")

    for prog in PROGRAMMING_TERMS:
        base_terms.append(prog)
        for mod in rng.sample(MODIFIERS, k=2):
            base_terms.append(f"{prog} {mod}")

    for common in COMMON_QUERIES:
        for prod in rng.sample(TECH_PRODUCTS + PROGRAMMING_TERMS, k=5):
            base_terms.append(f"{common} {prod}")

    # Deduplicate
    base_terms = list(dict.fromkeys(base_terms))

    # Expand with prefix variants to fill the target
    expanded = list(base_terms)
    while len(expanded) < target:
        term = rng.choice(base_terms)
        words = term.split()
        if len(words) > 1:
            # partial prefix variant
            n = rng.randint(1, len(words) - 1)
            expanded.append(" ".join(words[:n]))
        else:
            # single-char prefix variant
            for i in range(1, min(len(term), 5)):
                expanded.append(term[:i])

    expanded = list(dict.fromkeys(expanded))[:target]
    rng.shuffle(expanded)

    now = time.time()
    rows = []
    for rank, query in enumerate(expanded, start=1):
        # Zipf-distributed frequency: top queries get millions of hits
        freq = max(1, int(zipf_weight(rank) * 5_000_000))
        # last_searched_at: random within the past 30 days
        last_ts = now - rng.uniform(0, 30 * 86400)
        # Recency score: simulate a plausible accumulator
        recency = rng.uniform(0, freq / 1000.0)
        rows.append((query.lower().strip(), freq, last_ts, recency))

    return rows


if __name__ == "__main__":
    rows = generate_queries()
    sys.stdout.write("query,frequency,last_searched_at,recency_score\n")
    for query, freq, last_ts, recency in rows:
        # Escape commas inside queries
        safe_query = query.replace('"', '""')
        sys.stdout.write(f'"{safe_query}",{freq},{last_ts:.3f},{recency:.6f}\n')
    sys.stderr.write(f"Generated {len(rows)} rows\n")
