import sqlite3


with sqlite3.connect("./data/database.db") as conn:
    c = conn.cursor()

    c.execute("""CREATE TABLE products (
        product_id TEXT,
        product_name TEXT,
        last_price REAL,
        current_price REAL,
        merchant TEXT,
        url TEXT,
        url_id INTEGER
    )
    """)

    c.execute("""CREATE TABLE urls (
        url TEXT,
        first_cycle INTEGER
    )
    """)

    c.execute("""CREATE TABLE proxies (
        url TEXT
    )
    """)