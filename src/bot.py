from scraping import Scraper
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import telegram
import sqlite3
import datetime
import configparser
import builtins


config = configparser.ConfigParser()
config.read("./config.ini")

CHANNEL_ID = config.get("DEFAULT", "channel_id")
API_KEY = config.get("DEFAULT", "bot_key")
DELAY = config.getfloat("DEFAULT", "cycle_delay")
MAIN_URL = 'http://www.hepsiburada.com/'
DATABASE = "./data/database.db"


class Bot(object):

    def __init__(self):
        self.scraper = Scraper(DATABASE)
        self.jobs_running = []
        self.percentage = 0
        self.delay = DELAY
        self.mode = None

    def compare_prices(self, context: CallbackContext) -> None:
        """Check the database to see if any product is with a low price"""

        job = context.job
        
        if len(self.scraper.products) > 0:
            self.scraper.add_products()
            print("[Bot] Products added successfuly")
        
        if len(self.scraper.queries) > 0:
            self.scraper.execute_queries()
        
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            c.execute("SELECT rowid, * FROM urls;")
            self.scraper.url_rows = c.fetchall()
        
            if self.mode == "warn" or self.mode == "warn-track":
                new_products = self.scraper.new_products.copy()
                self.scraper.new_products = []

                for product in new_products:
                    date, product_id, product_name, product_price, product_url, url_id = product

                    message = product_name + "\n\n" + \
                        str(product_price) + " TL\n\n" + \
                        product_url + "?magaza=Hepsiburada\n\n"

                    context.bot.send_message(
                        chat_id = CHANNEL_ID, 
                        text = message
                    )

            if self.mode == "track" or self.mode == "warn-track":
                c.execute("SELECT DISTINCT product_id FROM products")
                prod_rows = c.fetchall()

                for row in prod_rows:
                    product_id = row[0]
                    
                    if len(self.jobs_running) == 0:
                        return

                    c.execute("SELECT * FROM products WHERE product_id = ?", (product_id, ))
                    products = c.fetchall()

                    key = lambda x : datetime.datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S.%f")
                    older_product = min(products, key = key)
                    current_product = max(products, key = key)

                    first_price = older_product[3]
                    current_price = current_product[3]
                    current_date = current_product[0]

                    url = current_product[4]

                    if current_price == 0:
                        print(f"[Debugging] Price of URL {url} is equal to zero")
                        continue

                    price_difference = first_price - current_price
                    percentage = price_difference / first_price
                    percentage_str = str("%.2f" % (percentage * 100))

                    if percentage >= self.percentage:
                        product_name = current_product[2]

                        print(f"[Bot] Price of \"{product_name}\" is {percentage_str}% off")

                        seller = self.scraper.get_product_info(url)["seller"]

                        message = product_name + "\n\n" + \
                            "Satıcı: " + seller + "\n\n" + \
                            str(first_price) + " TL >>>> " + \
                            str(current_price) + f" TL - {percentage_str}%" + "\n\n" + \
                            url + "\n\n" + \
                            MAIN_URL + "ara?q=" + product_id

                        context.bot.send_message(
                            chat_id = CHANNEL_ID, 
                            text = message
                        )

                        c.execute(
                            "DELETE FROM products WHERE product_id = ? AND date != ?",
                            (product_id, current_date)
                        )
            
            conn.commit()
    
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
                update.message.reply_text("Sorry, your argument must be a percentage number")
                return

            if percentage < 0 or percentage > 100:
                update.message.reply_text("Sorry, the percentage must be between 0 and 100 percent")
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
                self.scraper.get_products,
                interval = self.delay,
                first = 5
            )
        )

        self.jobs_running.append(
            self.job.run_repeating(
                self.compare_prices,
                interval = self.delay,
                first = 5,
                context = update.message.chat_id
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

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            if len(context.args) < 1:
                update.message.reply_text(
                    "Sorry, you must pass the URLs as arguments\n" + 
                    "e.g. /addurls <URL1> <URL2> <...>"
                )
                return

            urls = context.args

            for url in urls:
                c.execute("INSERT INTO urls VALUES (?, ?);", (url, 1))

            conn.commit()

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
        if len(self.jobs_running) == 0:
            status = "Stopped"
        else:
            status = "Running"

        percentage = str(self.percentage * 100) + "%"

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            
            c.execute("SELECT * from urls;")
            urls = [row[0] for row in c.fetchall()]
            if len(urls) == 0:
                urls_str = " Empty\n"
            else:
                urls_str = "\n - " + "\n - ".join(urls) + "\n"
        
        update.message.reply_text(
            f"Tracker Status: {status}\n" +
            f"Current Percentage: {percentage}\n" +
            "URLs:" + urls_str
        )
        
    def change_percentage(self, update: Update, context: CallbackContext) -> None:
        if len(self.jobs_running) == 0:
            update.message.reply_text("Sorry, you need to start the tracker in order to change the price")
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
            update.message.reply_text("Sorry, your argument must be a percentage number")
            return

        if percentage < 0 or percentage > 100:
            update.message.reply_text("Sorry, the percentage must be between 0 and 100%")
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

        dispatcher.add_handler(CommandHandler("changepercentage", self.change_percentage))

        dispatcher.add_handler(CommandHandler("status", self.get_status))
        dispatcher.add_handler(CommandHandler("help", self.help_command))

        updater.start_polling()
        updater.idle()