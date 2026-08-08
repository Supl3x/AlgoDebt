"""
Fetches a batch of small-to-medium public ML repos from GitHub for the study.
Uses GitHub's search API (unauthenticated, rate-limited to 10 req/min) to find
repos, then shallow-clones each into ./repos/.

Usage: python fetch_repos.py [--n 30]
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

REPOS_DIR = os.path.join(os.path.dirname(__file__), "..", "repos")

# Search queries designed to surface small/medium ML training-pipeline repos
# (notebooks-to-script tutorials, course projects, small Kaggle-style repos)
# rather than huge frameworks — those are more likely to show real anti-patterns
# and are fast to clone.
SEARCH_QUERIES = [
    "sklearn train_test_split language:Python stars:5..200",
    "pytorch training loop language:Python stars:5..200",
    "machine learning pipeline language:Python stars:5..200",
    "kaggle competition solution language:Python stars:5..200",
    "ML model training script language:Python stars:5..200",
]


def github_search(query, per_page=10):
    url = (
        "https://api.github.com/search/repositories"
        f"?q={urllib.parse.quote(query)}&per_page={per_page}&sort=updated"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "algo-debt-research"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("items", [])
    except Exception as e:
        print(f"  [search error] {query[:40]}...: {e}")
        return []


def clone_repo(clone_url, dest_dir, depth=1):
    if os.path.exists(dest_dir):
        print(f"  already exists, skipping: {dest_dir}")
        return True
    try:
        subprocess.run(
            ["git", "clone", "--depth", str(depth), clone_url, dest_dir],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        return True
    except Exception as e:
        print(f"  [clone error] {clone_url}: {e}")
        return False


def main():
    import urllib.parse
    globals()["urllib"].parse = urllib.parse  # ensure accessible

    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30, help="target number of repos")
    args = parser.parse_args()

    os.makedirs(REPOS_DIR, exist_ok=True)

    collected = []
    seen_names = set()

    for query in SEARCH_QUERIES:
        if len(collected) >= args.n:
            break
        print(f"Searching: {query}")
        items = github_search(query, per_page=10)
        for item in items:
            full_name = item["full_name"]
            if full_name in seen_names:
                continue
            seen_names.add(full_name)
            collected.append({
                "full_name": full_name,
                "clone_url": item["clone_url"],
                "stars": item["stargazers_count"],
                "description": item.get("description"),
            })
            if len(collected) >= args.n:
                break
        time.sleep(6)  # stay under unauthenticated rate limit (10 req/min)

    print(f"\nFound {len(collected)} candidate repos. Cloning...\n")

    manifest = []
    for repo in collected:
        safe_name = repo["full_name"].replace("/", "__")
        dest = os.path.join(REPOS_DIR, safe_name)
        print(f"Cloning {repo['full_name']} ({repo['stars']} stars)...")
        ok = clone_repo(repo["clone_url"], dest)
        manifest.append({**repo, "local_dir": safe_name, "cloned": ok})

    manifest_path = os.path.join(REPOS_DIR, "..", "results", "repo_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    n_ok = sum(1 for m in manifest if m["cloned"])
    print(f"\nDone. {n_ok}/{len(manifest)} repos cloned successfully.")
    print(f"Manifest saved to {manifest_path}")


if __name__ == "__main__":
    main()
