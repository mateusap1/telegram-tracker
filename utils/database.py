import sqlite3
import sys


def main():
    with sqlite3.connect("./data/database.db") as conn:
        c = conn.cursor()

        c.execute("""CREATE TABLE products (
            date TEXT,
            product_id TEXT,
            product_name TEXT,
            price REAL,
            url TEXT,
            url_id INTEGER
        )
        """)

        c.execute("""CREATE TABLE urls (
            url TEXT,
            first_cycle INTEGER
        )
        """)

        print("Tables created successfuly")


def execute(query):
    with sqlite3.connect("./data/database.db") as conn:
        c = conn.cursor()

        c.execute(query)

        print("Query executed successfuly")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        main()
    else:
        execute(sys.argv[1])

