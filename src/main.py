import logging
import mysql.connector
import sys
import os
import configparser
import time

from bot import Bot
from scraping import Scraper


config = configparser.ConfigParser()
config.read("./config.ini")

BOT_MODE = config.get("DEFAULT", "mode").lower()

if not BOT_MODE in ("scrape", "compare", "scrape-compare"):
    print("[Error] You must provide a valid mode.")
    print("Valid modes: \"scrape\", \"compare\" and \"scrape-compare\"")
    sys.exit(1)

DB_HOST = config.get("DATABASE", "host")
DB_USER = config.get("DATABASE", "user")
DB_PASSWORD = config.get("DATABASE", "password")
DB_NAME = config.get("DATABASE", "name")

if DB_PASSWORD[0] == "$":
    DB_PASSWORD = os.getenv(DB_PASSWORD[1:])

if any([i.strip() == "" for i in (DB_HOST, DB_USER)]):
    print("[Error] You must fill the database blank spaces")
    sys.exit(1)

logging.basicConfig(level=logging.CRITICAL)

db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)


def main():
    try:
        if BOT_MODE == "scrape":
            scraper = Scraper()

            duration = 31
            while True:
                start = time.time()

                if duration > 30:
                    duration = 0
                    scraper.get_products()

                duration += time.time() - start
        else:
            bot = Bot()
            bot.start()
    except KeyboardInterrupt:
        print("Closing...")
        db.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
