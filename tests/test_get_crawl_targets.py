"""
Test script for querying crawl targets.

Database config (for local testing only):
    POSTGRES_HOST: 127.0.0.1
    POSTGRES_PORT: 5432
    POSTGRES_USER: hub_user
    POSTGRES_PASSWORD: hub_password
    POSTGRES_DB: financial_hub
"""

import psycopg2
from financial_hub_postgres import FinancialHubClient


def get_test_connection():
    """Create a test database connection using local dev config."""
    return psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        user="hub_user",
        password="hub_password",
        dbname="financial_hub",
    )


def main():
    conn = get_test_connection()
    try:
        client = FinancialHubClient(conn)

        # Query all crawl targets
        print("=== All Crawl Targets ===")
        targets = client.get_crawl_targets()
        for t in targets:
            print(f"  [{t.id}] {t.source_type} | {t.target_name} | enabled={t.enabled}")

        # Query only enabled targets
        print("\n=== Enabled Targets ===")
        enabled_targets = client.get_crawl_targets(enabled=True)
        for t in enabled_targets:
            print(f"  [{t.id}] {t.source_type} | {t.target_name}")

        # Query by source type
        print("\n=== WeChat Targets ===")
        wechat_targets = client.get_crawl_targets(source_type="wechat")
        for t in wechat_targets:
            print(f"  [{t.id}] {t.target_name} ({t.target_identifier})")

        # Query single target by ID
        if targets:
            print(f"\n=== Target ID={targets[0].id} ===")
            single = client.get_crawl_target_by_id(targets[0].id)
            if single:
                print(f"  name: {single.target_name}")
                print(f"  identifier: {single.target_identifier}")
                print(f"  cron: {single.cron_expression}")
                print(f"  last_crawl_status: {single.last_crawl_status}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
