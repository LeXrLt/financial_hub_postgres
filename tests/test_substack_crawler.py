"""
Simulate a Substack crawler's full execution flow.

Steps:
1. Connect to the database.
2. Query crawl targets filtered by source_type='substack'.
3. For each enabled target, run a crawl cycle:
   a. notify_crawl_start  — hook before crawl
   b. Simulate crawl work (fetch articles)
   c. notify_crawl_end    — hook after crawl (with result)
4. Print final target state.

Database config (for local testing only):
    POSTGRES_HOST: 127.0.0.1
    POSTGRES_PORT: 5432
    POSTGRES_USER: hub_user
    POSTGRES_PASSWORD: hub_password
    POSTGRES_DB: financial_hub
"""

import random
import time

import psycopg2
from financial_hub_postgres import FinancialHubClient


COMPONENT_NAME = "substack_crawler"


def get_test_connection():
    """Create a test database connection using local dev config."""
    return psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        user="hub_user",
        password="hub_password",
        dbname="financial_hub",
    )


def fake_crawl_articles(target_name: str):
    """
    Simulate fetching articles from a Substack newsletter.
    Randomly returns results or raises an error.
    """
    time.sleep(random.uniform(0.3, 1.0))

    # 50% chance of failure
    if random.random() < 0.5:
        raise ConnectionError(f"Timeout while fetching {target_name}")

    found = random.randint(5, 20)
    new = random.randint(0, min(found, 5))
    failed = random.randint(0, 1)
    return found, new, failed


def run_crawl_for_target(client: FinancialHubClient, target):
    """Execute one full crawl cycle for a single target."""
    print(f"\n{'─' * 50}")
    print(f"Target: [{target.id}] {target.target_name} ({target.target_identifier})")
    print(f"{'─' * 50}")

    # ── Step 1: Before crawl ──
    print("[1/3] notify_crawl_start ...")
    run = client.notify_crawl_start(
        target_id=target.id,
        component_name=COMPONENT_NAME,
        metadata={"trigger": "manual_test"},
    )
    print(f"      crawl_run id={run.id}, status=running")

    # ── Step 2: Do crawl work ──
    print("[2/3] Crawling articles ...")
    start_time = time.time()
    try:
        items_found, items_new, items_failed = fake_crawl_articles(target.target_name)
        duration_ms = int((time.time() - start_time) * 1000)
        success = True
        error_message = None
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        items_found, items_new, items_failed = 0, 0, 0
        success = False
        error_message = str(e)

    # ── Step 3: After crawl ──
    status_label = "SUCCESS" if success else "FAILED"
    print(f"[3/3] notify_crawl_end ({status_label}) ...")
    client.notify_crawl_end(
        run_id=run.id,
        target_id=target.id,
        component_name=COMPONENT_NAME,
        success=success,
        items_found=items_found,
        items_new=items_new,
        items_failed=items_failed,
        error_message=error_message,
        duration_ms=duration_ms,
    )

    if success:
        print(f"      found={items_found}, new={items_new}, failed={items_failed}, duration={duration_ms}ms")
    else:
        print(f"      error: {error_message}, duration={duration_ms}ms")


def main():
    conn = get_test_connection()
    try:
        client = FinancialHubClient(conn)

        # ── Discover targets ──
        print("=== Discovering Substack Targets ===")
        targets = client.get_crawl_targets(source_type="substack", enabled=True)

        if not targets:
            print("No enabled substack targets found. Exiting.")
            return

        for t in targets:
            print(f"  [{t.id}] {t.target_name} ({t.target_identifier})")

        # ── Crawl each target ──
        for target in targets:
            run_crawl_for_target(client, target)

        # ── Final state ──
        print(f"\n{'=' * 50}")
        print("=== Final Target States ===")
        print(f"{'=' * 50}")
        for target in targets:
            t = client.get_crawl_target_by_id(target.id)
            if t:
                print(f"\n  [{t.id}] {t.target_name}")
                print(f"    last_crawl_status: {t.last_crawl_status}")
                print(f"    last_crawl_at:     {t.last_crawl_at}")
                print(f"    last_error:        {t.last_error}")
                print(f"    total_items:       {t.total_items}")

    finally:
        conn.close()
        print("\nDone.")


if __name__ == "__main__":
    main()
