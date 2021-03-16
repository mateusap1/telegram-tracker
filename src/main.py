import logging
import mysql.connector
import sys
import configparser

from bot import Bot


config = configparser.ConfigParser()
config.read("./config.ini")

DB_HOST = config.get("DATABASE", "host")
DB_USER = config.get("DATABASE", "user")
DB_PASSWORD = config.get("DATABASE", "password")

if any([ i.strip() == "" for i in (DB_HOST, DB_USER)]):
    print("[Error] You must fill the database blank spaces")
    sys.exit(1)

logging.basicConfig(level=logging.CRITICAL)

db = mysql.connector.connect(
    host = DB_HOST,
    user = DB_USER,
    password = DB_PASSWORD,
    database = "telegram_tracker"
)

def main():
	try:
	    bot = Bot()
	    bot.start()
	except KeyboardInterrupt:
		print("Closing...")
		db.close()
		sys.exit(0)

if __name__ == "__main__":
    main()