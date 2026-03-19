#!/usr/bin/env python3
"""
run_all.py
==========
Step 1: Run all three Scrapy spiders to populate csvFiles/
Step 2: Run the prediction model

Usage:
    python run_all.py

Environment variables (for KenPom login):
    KENPOM_USER=your@email.com
    KENPOM_PASS=yourpassword
"""

import subprocess
import sys
import os
from pathlib import Path


def run_spider(spider_name: str, spider_file: str):
    print(f"\n{'='*50}")
    print(f"  Running spider: {spider_name}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, "-m", "scrapy", "runspider", spider_file],
        capture_output=False
    )
    if result.returncode != 0:
        print(f"  ⚠️  Spider {spider_name} exited with code {result.returncode}")
    else:
        print(f"  ✅  {spider_name} complete")


def main():
    Path("csvFiles").mkdir(exist_ok=True)

    # Run spiders in order
    run_spider("Torvik",   "torvik_spider.py")
    run_spider("EvanMiya", "evanmiya_spider.py")

    # KenPom last — requires credentials
    if os.environ.get("KENPOM_USER"):
        run_spider("KenPom", "kenpom_spider.py")
    else:
        print("\n⚠️  Skipping KenPom — set KENPOM_USER and KENPOM_PASS env vars to enable")
        print("   The model will still run using Torvik + EvanMiya data.\n")

    # Run predictions
    print(f"\n{'='*50}")
    print("  Running bracket predictions")
    print(f"{'='*50}")
    import march_madness_predictor
    march_madness_predictor.main()


if __name__ == "__main__":
    main()
