from scraping import Scraper
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import telegram
import mysql.connector
import concurrent.futures
import datetime
import configparser
import builtins
import sys
import os
import re
import time
import requests

config = configparser.ConfigParser()
config.read("./config.ini")

CHANNEL_ID = config.get("DEFAULT", "channel_id")
API_KEY = config.get("DEFAULT", "bot_key")
MAX_THREADS = config.getint("DEFAULT", "threads")
BOT_MODE = config.get("DEFAULT", "mode").lower()

if not BOT_MODE in ("scrape", "compare", "scrape-compare"):
    print("[Error] You must provide a valid mode.")
    print("Valid modes: \"scrape\", \"compare\" and \"scrape-compare\"")
    sys.exit(1)

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
DB_NAME = config.get("DATABASE", "name")

MIN_CYCLE_TIME = 60
MIN_CYCLES = 3

if DB_PASSWORD[0] == "$":
    DB_PASSWORD = os.getenv(DB_PASSWORD[1:])


class Bot(object):

    def __init__(self):
        self.scraper = Scraper()
        self.jobs_running = []
        self.percentage = 0
        self.delay = DELAY
        self.mode = None

    def connect_db(self) -> None:
        """Starts a connection to the database"""

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

    def compare_price(self, args: tuple) -> bool:
        """Verify if a specific product had a price drop"""

        context = args[0]
        products = args[1]
        urls = args[2]

        product_id = products[0][3]

        try:
            print("Bip")

            temp_products = list(
                filter(lambda x: x[-1] == "temp_products", products))
            products = list(filter(lambda x: x[-1] == "products", products))

            temp_products = [i[:-1] for i in temp_products]
            products = [i[:-1] for i in products]

            if len(temp_products) == 0:
                return True

            cycles = 0  # The number of cycles the url of the first product had
            for row in urls:
                if row[0] == temp_products[0][7]:
                    cycles = int(row[2])
                    break

            # The newest temp_product
            max_time = max(temp_products, key=lambda x: x[1])
            max_time = datetime.datetime.strptime(
                max_time[1], "%Y-%m-%d %H:%M:%S.%f"
            )

            # The oldest temp_product
            min_time = min(temp_products, key=lambda x: x[1])
            min_time = datetime.datetime.strptime(
                min_time[1], "%Y-%m-%d %H:%M:%S.%f"
            )

            cycle_time = max_time - min_time  # The time it took to get all those products

            if len(products) == 0:  # If this is a new product
                # If this is not our first cycle and the bot is in the warn mode
                if (self.mode == "warn" or self.mode == "warn-track") and cycles > 1:
                    # Verify if new product is from seller "Hepsiburada".
                    # If it is, warn the user.

                    rowid, date, listing_id, product_id, product_name, \
                        product_price, product_url, url_id = temp_products[0]

                    # Try to get the seller name by looking on the URL
                    seller = re.match(r"\?magaza=(.*)$", product_url)

                    # If we couldn't get the name, scrape the product page and get it
                    if not seller:
                        info = self.scraper.get_product_info(product_url)
                        seller = info["seller"]
                        product_url += "\n\n"
                    else:
                        seller = seller[0]

                    # If our seller is Hepsiburada, warn the user
                    if seller.lower() == "hepsiburada":
                        message = product_name + "\n\n" + \
                            str(product_price) + " TL\n\n" + \
                            product_url

                        context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=message
                        )

                db = self.connect_db()
                c = db.cursor()

                c.execute(f"""
                    INSERT INTO products (
                        rowid,
                        date,
                        listing_id,
                        product_id,
                        product_name,
                        price,
                        url,
                        url_id
                    ) VALUES {", ".join([str(i) for i in temp_products])};
                """)

                c.execute("""
                    DELETE FROM temp_products 
                    WHERE product_id = %s;
                """, (product_id, ))

                c.close()
                self.save_db(db)

                return True

            if self.mode == "warn":
                db = self.connect_db()
                c = db.cursor()

                c.execute(f"""
                    INSERT INTO products (
                        rowid,
                        date,
                        listing_id,
                        product_id,
                        product_name,
                        price,
                        url,
                        url_id
                    ) VALUES {", ".join([str(i) for i in temp_products])};
                """)

                c.execute("""
                    DELETE FROM temp_products 
                    WHERE product_id = %s;
                """, (product_id, ))

                c.close()
                self.save_db(db)

                return True

            matchs = {}  # A dictionary with every match between old and new listing_ids

            for product in products:
                listing_id = product[3]

                if listing_id in matchs:
                    if matchs[listing_id]["old_product"] is not None:
                        matchs[listing_id]["old_product"] = min(
                            [product, matchs[listing_id]["old_product"]],
                            key=lambda x: x[5]
                        )
                    else:
                        matchs[listing_id]["old_product"] = product
                else:
                    matchs[listing_id] = {
                        "old_product": product,
                        "new_product": None
                    }

            for product in temp_products:
                listing_id = product[3]

                if listing_id in matchs:
                    if matchs[listing_id]["new_product"] is not None:
                        matchs[listing_id]["new_product"] = min(
                            [product, matchs[listing_id]["new_product"]],
                            key=lambda x: x[5]
                        )
                    else:
                        matchs[listing_id]["new_product"] = product
                else:
                    matchs[listing_id] = {
                        "old_product": None,
                        "new_product": product
                    }

            for listing_id, (old_product, new_product) in matchs.items():
                # If we don't have an old product that matches this listing_id
                # and not enough cycles with this url happened, disconsider this
                # new product in the price comparison
                if old_product is None:
                    url_id = new_product[7]

                    cycles = 0
                    for row in urls:
                        if row[0] == url_id:
                            cycles = int(row[2])
                            break

                    if cycles < MIN_CYCLES:
                        temp_products.remove(new_product)

                # If we don't have a new product that matches this listing_id
                # and we didn't spent enough time in this cycle, return and wait
                # for a new call
                if new_product is None:
                    if cycle_time < MIN_CYCLE_TIME:
                        return True

            db = self.connect_db()
            c = db.cursor()

            # Insert the temp_products into the products table
            c.execute(f"""
                INSERT INTO products (
                    rowid,
                    date,
                    listing_id,
                    product_id,
                    product_name,
                    price,
                    url,
                    url_id
                ) VALUES {", ".join([str(i) for i in temp_products])};
            """)

            # Delete the temp_products
            c.execute("""
                DELETE FROM temp_products 
                WHERE product_id = %s;
            """, (product_id, ))

            c.close()
            self.save_db(db)

            # Get the cheapest product from `temp_products`
            current_product = min(temp_products, key=lambda x: x[5])
            # Get the cheapest product from `products`
            older_product = min(products, key=lambda x: x[5])

            first_price = older_product[5]  # Cheaper price of `temp_products`
            current_price = current_product[5]  # Cheaper price of `products`
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

            return True

        except Exception as e:
            print(
                f"[Debugging] Error {e.__class__} while comparing price of product_id \"{product_id}\" -> {e}")

            return False

    def compare_prices(self, context: CallbackContext) -> None:
        """Check the database to see if any product is with a low price"""

        try:
            job = context.job

            print("[Bot] Comparing prices...")

            start = time.time()

            db = self.connect_db()
            c = db.cursor()

            # TODO: Get all elements from both tables ordered by product_id and separate them
            # TODO: Make the connections, the shortest possible

            c.execute("""
                SELECT *, 'products' 
                FROM products 
                UNION
                SELECT *, 'temp_products'
                FROM temp_products
                ORDER BY product_id;
            """)
            products = c.fetchall()

            c.execute("SELECT * FROM urls;")
            urls = c.fetchall()

            c.close()
            self.save_db(db)

            if len(products) > 0:
                if BOT_MODE == "compare":
                    threads = MAX_THREADS
                else:
                    threads = max(int(MAX_THREADS / 4), 1)

                ps = []
                last_product_id = None
                for product in products:
                    if product[3] != last_product_id:
                        ps.append([product])
                    else:
                        ps[-1].append(product)

                    last_product_id = product[3]

                args = zip(
                    [context for _ in range(len(ps))],
                    ps,
                    [urls for _ in range(len(ps))]
                )

                with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                    executor.map(self.compare_price, args)

            duration = time.time() - start
            print(
                f"[Bot] Prices compared successfuly in {duration} seconds")

        except Exception as e:
            print(
                f"[Debugging] Error {e.__class__} while comparing prices -> {e}")

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

        if BOT_MODE == "compare" or BOT_MODE == "scrape-compare":
            self.jobs_running.append(
                self.job.run_repeating(
                    self.compare_prices,
                    interval=self.delay,
                    first=5,
                    context=update.message.chat_id
                )
            )

        if BOT_MODE == "scrape" or BOT_MODE == "scrape-compare":
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
                      (i+size, url, 0))

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
        try:
            db = self.connect_db()
            c = db.cursor()

            if len(self.jobs_running) == 0:
                status = "Stopped"
            else:
                status = f"Running with mode {self.mode}"

            percentage = str(self.percentage * 100) + "%"

            c.execute("SELECT url from urls;")

            urls = [row[0] for row in c.fetchall()]
            if len(urls) == 0:
                urls_str = " Empty\n"
            else:
                urls_str = "\n - " + "\n - ".join(urls) + "\n"

            update.message.reply_text(
                f"Tracker Status: {status}\n" +
                f"Current Percentage: {percentage}\n" +
                f"URLs: {str(len(urls))}"
            )

            c.close()
        except Exception as e:
            print(e)

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
