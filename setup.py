from setuptools import setup, find_packages

setup(
    name="financial_hub_postgres",
    version="0.1.0",
    description="PostgreSQL database operations library for Financial Hub crawlers",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "psycopg2-binary>=2.9.0",
    ],
)
