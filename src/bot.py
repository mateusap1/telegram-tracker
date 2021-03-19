from scraping import Scraper
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import telegram
import mysql.connector
import datetime
import configparser
import builtins
import sys
import os
import re
import time

config = configparser.ConfigParser()
config.read("./config.ini")

CHANNEL_ID = config.get("DEFAULT", "channel_id")
API_KEY = config.get("DEFAULT", "bot_key")

DELAY = config.getfloat("TIME", "cycle_delay")
OLDER_PRODUCTS_RANGE = config.getfloat("TIME", "older_products_range")
MAIN_URL = 'http://www.hepsiburada.com/'

if CHANNEL_ID.strip() == "":
    print("[Error] You must enter a channel ID")
    sys.exit(1)
elif API_KEY.strip() == "":
    print("[Error] You must enter an API key")
    sys.exit(1)

if CHANNEL_ID[0] == "$":
    CHANNEL_ID = os.getenv(CHANNEL_ID[1:])
if API_KEY[0] == "$":
    API_KEY = os.getenv(API_KEY[1:])

DB_HOST = config.get("DATABASE", "host")
DB_USER = config.get("DATABASE", "user")
DB_PASSWORD = config.get("DATABASE", "password")
DB_NAME = "telegram_tracker"


class Bot(object):

    def __init__(self):
        self.scraper = Scraper()
        self.jobs_running = []
        self.percentage = 0
        self.delay = DELAY
        self.mode = None

    def connect_db(self) -> None:
        """Starts a connection to the database""""

        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

    def save_db(self, db) -> None:
        """Commits and save everything from the database"""

        db.commit()
        db.close()

    def compare_prices(self, context: CallbackContext) -> None:
        """Check the database to see if any product is with a low price"""

        db = self.connect_db()
        c = db.cursor()

        try:
            job = context.job

            c.execute("SELECT * FROM urls;")
            self.scraper.url_rows = c.fetchall()

            new_products = self.scraper.new_products.copy()
            self.scraper.new_products = []

            if self.mode == "warn" or self.mode == "warn-track":
                print("[Bot] Searching for new products...")

                # For each product added to the `new_products` list, verify if they are from
                # seller "Hepsiburada". If they are, warn the user.
                for product in new_products:
                    rowid, date, product_id, listing_id, product_name, \
                        product_price, product_url, url_id = product

                    seller = re.match(r"\?magaza=(.*)$", product_url)

                    if not seller:
                        info = self.scraper.get_product_info(product_url)
                        seller = info["seller"]
                        product_url += "\n\n"

                    else:
                        seller = seller[0]
                        product_url += "?magaza=Hepsiburada\n\n"

                    if seller.lower() != "hepsiburada":
                        continue

                    message = product_name + "\n\n" + \
                        str(product_price) + " TL\n\n" + \
                        product_url

                    context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=message
                    )

                print("[Bot] Products were searched successfully")

            if self.mode == "track" or self.mode == "warn-track":
                print("[Bot] Comparing prices...")
                c.execute("""SELECT DISTINCT p.product_id  
                             FROM products p 
                             WHERE EXISTS (SELECT 1 
                                           FROM products l 
                                           WHERE p.product_id = l.product_id AND p.price <> l.price
                                           );
                """)
                prod_rows = c.fetchall()

                deleted = self.scraper.deleted.copy()
                marks = ", ".join(["%s" for _ in range(len(deleted))])
                for row in prod_rows:
                    if len(self.jobs_running) == 0:
                        return

                    product_id = row[0]

                    # Get all products from this id that weren't deleted yet
                    if len(deleted) > 0:
                        c.execute(
                            f"SELECT * FROM products WHERE product_id = %s AND rowid NOT IN ({marks}) ORDER BY date DESC;",
                            (product_id, *deleted)
                        )
                    else:
                        c.execute(
                            f"SELECT * FROM products WHERE product_id = %s ORDER BY date DESC;",
                            (product_id, *deleted)
                        )
                    products = c.fetchall()

                    old_products = products.copy()
                    new_products = []

                    # The max_date a product can have in order to be considered "old"
                    limit = datetime.datetime.strptime(products[-1][1], "%Y-%m-%d %H:%M:%S.%f") + \
                        datetime.timedelta(minutes=OLDER_PRODUCTS_RANGE)

                    # Separate "old" from "new" products
                    for i, product in enumerate(products[::-1]):
                        date = datetime.datetime.strptime(
                            product[1], "%Y-%m-%d %H:%M:%S.%f")

                        index = len(products) - i - 1
                        if date > limit:
                            old_products = products[index+1:]
                            new_products = products[:index+1]
                            break

                    # If we have only one or even none of the lists, return
                    if len(new_products) == 0:
                        continue
                    if len(old_products) == 0:
                        continue

                    older_product = min(old_products, key=lambda x: x[5])
                    current_product = min(new_products, key=lambda x: x[5])

                    first_price = older_product[5]
                    current_price = current_product[5]
                    current_date = current_product[1]

                    url = current_product[6]

                    price_difference = first_price - current_price
                    percentage = price_difference / first_price
                    percentage_str = str("%.2f" % (percentage * 100))

                    # If the drop in the price was greater then the expected percentage, warn the user
                    if percentage >= self.percentage:
                        rowid = current_product[0]
                        product_name = current_product[4]
                        product_id = current_product[3]

                        print(
                            f"[Bot] Price of \"{product_name}\" is {percentage_str}% off")

                        # If we can get the sellers name in the URL, store it
                        seller = re.match(r"\?magaza=(.*)$", url)

                        # If the seller isn't in the URL, get it from the product page
                        if not seller:
                            info = self.scraper.get_product_info(url)
                            seller = info["seller"]
                        else:
                            seller = seller[0]

                        message = product_name + "\n\n" + \
                            "Satıcı: " + seller + "\n\n" + \
                            str(first_price) + " TL >>>> " + \
                            str(current_price) + f" TL - {percentage_str}%" + "\n\n" + \
                            url + "\n\n" + \
                            MAIN_URL + "ara?q=" + product_id

                        context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=message
                        )

                        c.execute(
                            "SELECT rowid FROM products WHERE product_id = %s AND rowid != %s;",
                            (product_id, rowid)
                        )

                        # Delete every product with this id with the exception of the last one
                        rowids = [row[0] for row in c.fetchall()]
                        self.scraper.deleted += rowids

                print("[Bot] Prices compared successfuly")

            c.close()
            self.save_db(db)

        except Exception as e:
            c.close()
            self.save_db(db)

            print(f"[Debugging] Error while comparing prices -> {e}")

    def start_bot(self, update: Update, context: CallbackContext) -> None:
        """Message the user when the price is low"""

        if len(context.args) < 1:
            update.message.reply_text(
                "Sorry, you need to pass the bot mode as an argument.\n" +
                "e.g. /start warn/track/warn-track (20%)"
            )
            return

        mode = context.args[0].lower()

        if mode == "warn":
            self.mode = "warn"
            self.scraper.mode = "warn"

            update.message.reply_text("Starting products tracking...")
            print("[Bot] Starting products tracking...")

        elif mode == "track" or mode == "warn-track":
            if len(context.args) != 2:
                update.message.reply_text(
                    "Sorry, you need to pass the percentage as an argument.\n" +
                    "e.g. /start track/warn-track 20%"
                )
                return

            percentage = context.args[1].replace("%", "")

            try:
                percentage = float(percentage)
            except ValueError:
                update.message.reply_text(
                    "Sorry, your argument must be a percentage number")
                return

            if percentage < 0 or percentage > 100:
                update.message.reply_text(
                    "Sorry, the percentage must be between 0 and 100 percent")
                return

            self.mode = mode
            self.scraper.mode = mode

            self.percentage = percentage / 100

            update.message.reply_text("Starting price tracking...")
            print("[Bot] Starting price tracking...")

        else:
            update.message.reply_text(
                "Sorry, you need to passa valid argument.\n" +
                "Valid arguments: \"track\", \"warn\", \"warn-track\""
            )
            return

        self.jobs_running.append(
            self.job.run_repeating(
                self.compare_prices,
                interval=self.delay,
                first=5,
                context=update.message.chat_id
            )
        )

        self.jobs_running.append(
            self.job.run_repeating(
                self.scraper.get_products,
                interval=self.delay,
                first=5
            )
        )

    def stop_bot(self, update: Update, context: CallbackContext) -> None:
        """Stops tracking price loop"""
        if len(self.jobs_running) == 0:
            update.message.reply_text("Bot is already stopped")
        else:
            for job in self.jobs_running:
                job.schedule_removal()

            self.jobs_running = []
            update.message.reply_text("Stoping bot...")
            print("[Bot] Bot stoping when current cycle ends")

    def add_urls(self, update: Update, context: CallbackContext) -> None:
        """Adds an url to the database"""

        if len(context.args) < 1:
            update.message.reply_text(
                "Sorry, you must pass the URLs as arguments\n" +
                "e.g. /addurls <URL1> <URL2> <...>"
            )
            return

        urls = context.args

        db = self.connect_db()
        c = db.cursor()

        c.execute("SELECT COUNT(rowid) FROM urls;")
        size = int(c.fetchone()[0])

        for i, url in enumerate(urls):
            c.execute("INSERT INTO urls VALUES (%s, %s, %s);",
                      (i+size, url, 1))

        c.close()
        self.save_db(db)

        print(f"[Bot] URL(s) successfuly added to the database")
        update.message.reply_text("URL(s) added successfuly")

    def remove_urls(self, update: Update, context: CallbackContext) -> None:
        """Removes an url from the database"""

        if len(context.args) < 1:
            update.message.reply_text(
                "Sorry, you must pass the URLs as arguments\n" +
                "e.g. /removeurls <URL1> <URL2> <...>"
            )
            return

        urls = context.args

        self.scraper.delete_urls(urls)

        print(f"[Bot] URL(s) successfuly removed from the database")
        update.message.reply_text(f"URL(s) successfuly removed")

    def get_status(self, update: Update, context: CallbackContext) -> None:
        db = self.connect_db()
        c = db.cursor()

        if len(self.jobs_running) == 0:
            status = "Stopped"
        else:
            status = "Running"

        percentage = str(self.percentage * 100) + "%"

        c.execute("SELECT * from urls;")

        urls = [row[1] for row in c.fetchall()]
        if len(urls) == 0:
            urls_str = " Empty\n"
        else:
            urls_str = "\n - " + "\n - ".join(urls) + "\n"

        update.message.reply_text(
            f"Tracker Status: {status}\n" +
            f"Current Percentage: {percentage}\n" +
            "URLs:" + urls_str
        )

        c.close()

    def change_percentage(self, update: Update, context: CallbackContext) -> None:
        if len(self.jobs_running) == 0:
            update.message.reply_text(
                "Sorry, you need to start the tracker in order to change the price")
            return

        if len(context.args) != 1:
            update.message.reply_text(
                "Sorry, you must pass the percentage as an argument\n" +
                "e.g. /changepercentage 30%"
            )
            return

        percentage = context.args[0].replace("%", "")

        try:
            percentage = float(percentage)
        except ValueError:
            update.message.reply_text(
                "Sorry, your argument must be a percentage number")
            return

        if percentage < 0 or percentage > 100:
            update.message.reply_text(
                "Sorry, the percentage must be between 0 and 100%")
            return

        percentage = percentage / 100

        old_percentage = self.percentage
        self.percentage = percentage

        update.message.reply_text(
            f"Successfuly changed percentage from {str(old_percentage * 100)}% to {str(percentage * 100)}%"
        )

    def help_command(self, update: Update, context: CallbackContext) -> None:
        """Send a message when the command /help is issued."""
        update.message.reply_text(
            "/start <mode> <percentage (if needed)>: if the mode is \"warn\"," +
            "it will warn the user whenever a new product is added. If the mode is \"track\"," +
            "it will warn the use whenever a price drops.\n"
            "/stop: stops tracking price loop\n" +
            "/addurls <URL1> <URL2> <...>: add URL(s) to the list\n" +
            "/removeurls <URL1> <URL2> <...>: remove URL(s) from the list\n" +
            "/changepercentage <new percentage>: changes the percentage to a new value\n" +
            "/status: messages the bot status"
        )

    def start(self):
        print("[Bot] Starting bot...")

        updater = Updater(API_KEY)
        self.job = updater.job_queue

        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", self.start_bot))
        dispatcher.add_handler(CommandHandler("stop", self.stop_bot))

        dispatcher.add_handler(CommandHandler("addurls", self.add_urls))
        dispatcher.add_handler(CommandHandler("removeurls", self.remove_urls))

        dispatcher.add_handler(CommandHandler(
            "changepercentage", self.change_percentage))

        dispatcher.add_handler(CommandHandler("status", self.get_status))
        dispatcher.add_handler(CommandHandler("help", self.help_command))

        updater.start_polling()
        updater.idle()
