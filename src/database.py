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
        subcategory_id INTEGER
    )
    """)

    c.execute("""CREATE TABLE categories (
        name TEXT,
        url TEXT
    )
    """)

    c.execute("""CREATE TABLE subcategories (
        name TEXT,
        url TEXT,
        category_id INTEGER,
        added INTEGER
    )
    """)

    c.execute("""CREATE TABLE brands (
        name TEXT
    )
    """)