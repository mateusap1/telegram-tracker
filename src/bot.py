from scraping import Scraper
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import telegram
import sqlite3


MAIN_URL = 'https://www.hepsiburada.com/'
DATABASE = "./data/database.db"


class Bot(object):

    def __init__(self):
        self.scraper = Scraper(DATABASE)
        self.jobs_running = []
        self.percentage = 0
        self.delay = 30
    
    def get_subcategories_str(self) -> None:
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            c.execute("SELECT rowid, * FROM categories;")
            c_rows = c.fetchall()

            possible_categories = []
            for c_row in c_rows:
                current_str = ""
                c.execute("SELECT * FROM subcategories WHERE category_id = ?;", (c_row[0],))
                subc_rows = c.fetchall()

                if len(subc_rows) > 0:
                    current_str += "[Category] - " + c_row[1] + "\n"

                for subc_row in subc_rows:
                    current_str += "[Subcategory] - " + subc_row[0] + "\n"
                
                if len(current_str) > 0:
                    possible_categories.append(current_str)
            
            if len(possible_categories) == 0:
                possible_categories = ["Empty"]
                
        return possible_categories
    
    def my_subcategories_str(self) -> None:
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            c.execute("SELECT rowid, * FROM categories;")
            c_rows = c.fetchall()

            possible_categories = []
            for c_row in c_rows:
                current_str = ""
                c.execute("SELECT * FROM subcategories WHERE category_id = ? AND added = 1;", (c_row[0],))
                subc_rows = c.fetchall()

                if len(subc_rows) > 0:
                    current_str += "[Category] - " + c_row[1] + "\n"

                for subc_row in subc_rows:
                    current_str += "[Subcategory] - " + subc_row[0] + "\n"
                
                if len(current_str) > 0:
                    possible_categories.append(current_str)
            
            if len(possible_categories) == 0:
                possible_categories = ["\tEmpty"]
                
        return possible_categories

    def compare_prices(self, context: CallbackContext) -> None:
        """Check the database to see if any product is with a low price"""

        if len(self.scraper.products) > 0:
            self.scraper.add_products()
            print("[Scraper] Products added successfuly")

        job = context.job

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            c.execute("SELECT rowid, * FROM products")
            prod_rows = c.fetchall()

            for row in prod_rows:
                row_id, product_id, listing_id, product_name, last_price, \
                    current_price, merchant, url, subcategory_id = row
                
                if len(self.jobs_running) == 0:
                    return
                
                price_difference = last_price - current_price
                percentage = price_difference / last_price
                percentage_str = str("%.2f" % (percentage * 100))

                if percentage >= self.percentage:
                    info = self.scraper.get_product_info(url)
                    real_price = info["price"]
                    seller = info["seller"]

                    # TODO: See why it's not working properly

                    if current_price != real_price:
                        c.execute(
                            "UPDATE products SET current_price = ? WHERE listing_id = ?",
                            (real_price, listing_id)
                        )
                    
                    price_difference = last_price - real_price

                    real_percentage = price_difference / last_price
                    if percentage < self.percentage:
                        return

                    percentage_str = str("%.2f" % (percentage * 100))
                    
                    print(f"[Bot] Price of \"{product_name}\" is {percentage_str}% off")

                    message = product_name + "\n\n" + \
                        "Satıcı: " + seller + "\n\n" + \
                        str(last_price) + " TL >>>> " + \
                        str(current_price) + f" TL - {percentage_str}%" + "\n\n" + \
                        url + "\n\n" + \
                        MAIN_URL + "ara?q=" + product_id

                    context.bot.send_message(
                        chat_id = job.context, 
                        text = message
                    )

                    c.execute(
                        "UPDATE products SET last_price = ? WHERE listing_id = ?",
                        (current_price, listing_id)
                    )
            
            conn.commit()
    
    def start_bot(self, update: Update, context: CallbackContext) -> None:
        """Message the user when the price is low"""
        if len(self.jobs_running) == 2:
            update.message.reply_text('Sorry, the price tracker is already running')
            return

        if len(context.args) != 1:
            update.message.reply_text(
                'Sorry, you need to pass the percentage as an argument.\n' +
                'e.g. /start 20%'
            )
            return
        
        percentage = context.args[0].replace("%", "")

        try:
            percentage = float(percentage)
        except ValueError:
            update.message.reply_text('Sorry, your argument must be a percentage number')
            return

        if percentage < 0 or percentage > 100:
            update.message.reply_text('Sorry, the percentage must be between 0 and 100 percent')
            return
        
        self.percentage = percentage / 100
        
        update.message.reply_text('Starting price tracker...')
        print("[Bot] Starting price tracker...")

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
            update.message.reply_text('Bot is already stopped')
        else:
            for job in self.jobs_running:
                job.schedule_removal()

            self.jobs_running = []
            update.message.reply_text('Stoping bot...')
            print("[Bot] Bot stoping when current cycle ends")

    def add_subcategory(self, update: Update, context: CallbackContext) -> None:
        """Adds a subcategory to the list"""

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            if len(context.args) < 1:
                update.message.reply_text(
                    "Sorry, you must pass the subcategory as an argument\n" + 
                    "e.g. /addsubcategory <subcategory>"
                )
                return

            subcategory = " ".join(context.args)

            c.execute("SELECT rowid, * FROM subcategories WHERE name = ?;", (subcategory,))
            row = c.fetchone()

            if row is None:
                update.message.reply_text(
                    "Sorry, this subcategory wasn't in the list\n" + 
                    "Possible subcategories:\n"
                )

                categories = self.get_subcategories_str()
                for category in categories:
                    update.message.reply_text(category)
                    
                return

            c.execute("UPDATE subcategories SET added = 1 WHERE name = ?;", (subcategory, ))
            conn.commit()

            print(f"[Bot] Subcategory \"{subcategory}\" added to the database")
            update.message.reply_text("Subcategory added successfuly")
    
    def remove_subcategory(self, update: Update, context: CallbackContext) -> None:
        """Removes a subcategory from the list"""

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            if len(context.args) < 1:
                update.message.reply_text(
                    "Sorry, you must pass the subcategory as an argument\n" + 
                    "e.g. /removesubcategory <subcategory>"
                )
                return

            subcategory = " ".join(context.args)

            c.execute("SELECT rowid, * FROM subcategories WHERE name = ?;", (subcategory,))
            row = c.fetchone()

            if row is None:
                update.message.reply_text(
                    "Sorry, this subcategory wasn't in the list\n" + 
                    "Your subcategories:\n"
                )

                categories = self.my_subcategories_str()
                for category in categories:
                    update.message.reply_text(category)
                return

            c.execute("UPDATE subcategories SET added = 0 WHERE name = ?;", (subcategory, ))
            conn.commit()

        self.scraper.delete_subcategories([row[0]])
        print(f"[Bot] Subcategory \"{subcategory}\" removed from the database")
        update.message.reply_text(f"The subcategory \"{subcategory}\" was successfuly removed")

    def add_brand(self, update: Update, context: CallbackContext) -> None:
        """Add brand to the db"""

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            if len(context.args) < 1:
                update.message.reply_text(
                    "Sorry, you must pass the brand name as an argument\n" + 
                    "e.g. /addbrand <brand>"
                )
                return

            brand = " ".join(context.args)

            c.execute("INSERT INTO brands VALUES (?)", (brand, ))
            conn.commit()

            update.message.reply_text(f"Brand successfuly added")
    
    def remove_brand(self, update: Update, context: CallbackContext) -> None:
        """Remove brand from the db"""

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            if len(context.args) < 1:
                update.message.reply_text(
                    "Sorry, you must pass the brand name as an argument\n" + 
                    "e.g. /removebrand <brand>"
                )
                return

            brand = " ".join(context.args)

            c.execute("DELETE FROM brands WHERE name = ?;", (brand, ))
            conn.commit()

            update.message.reply_text(f"The brand \"{brand}\" was successfuly removed")

    def get_status(self, update: Update, context: CallbackContext) -> None:
        if len(self.jobs_running) == 0:
            status = "Stopped"
        else:
            status = "Running"

        percentage = str(self.percentage * 100) + "%"

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()

            c.execute("SELECT * from brands;")
            brands = [row[0] for row in c.fetchall()]
            if len(brands) == 0:
                brands_str = " Empty\n"
            else:
                brands_str = "\n - " + "\n - ".join(brands) + "\n"
        
        categories = self.my_subcategories_str()
        
        if categories == ["\tEmpty"]:
            update.message.reply_text(
                f"Tracker Status: {status}\n" +
                f"Current Percentage: {percentage}\n" +
                "Brands:" + brands_str +
                "Subcategories: Empty"
            )
        else:
            update.message.reply_text(
                f"Tracker Status: {status}\n" +
                f"Current Percentage: {percentage}\n" +
                "Brands:" + brands_str +
                "Subcategories:\n"
            )

            categories = self.my_subcategories_str()
            for category in categories:
                update.message.reply_text(category)
        
    def change_percentage(self, update: Update, context: CallbackContext) -> None:
        if len(self.jobs_running) == 0:
            update.message.reply_text('Sorry, you need to start the tracker in order to change the price')
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
            update.message.reply_text('Sorry, your argument must be a percentage number')
            return

        if percentage < 0 or percentage > 100:
            update.message.reply_text('Sorry, the percentage must be between 0 and 100%')
            return
        
        percentage = percentage / 100
        
        old_percentage = self.percentage
        self.percentage = percentage

        update.message.reply_text(
            f'Successfuly changed percentage from {str(old_percentage * 100)}% to {str(percentage * 100)}%'
        )
    
    def help_command(self, update: Update, context: CallbackContext) -> None:
        """Send a message when the command /help is issued."""
        update.message.reply_text(
            "/start <percentage>: messages the user when the price is lower than " +
            "the original price by a given percentage\n" +
            "/stop: stops tracking price loop\n" +
            "/addsubcategory <subcategory>: adds a subcategory to the list\n" +
            "/removesubcategory <subcategory>: removes a subcategory from the list\n" +
            "/addbrand <brand>: adds a brand to the list\n" +
            "/removebrand <brand>: removes a brand from the list\n" +
            "/changepercentage <new percentage>: changes the percentage to a new value\n" +
            "/status: messages the product status"
        )
    
    def start(self):
        print("[Bot] Starting bot...")

        updater = Updater("1549588597:AAHsFKTLD6glkm1EWPL_qWPkLgXnwEx01r8", use_context=True)
        self.job = updater.job_queue

        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", self.start_bot))
        dispatcher.add_handler(CommandHandler("stop", self.stop_bot))

        dispatcher.add_handler(CommandHandler("addsubcategory", self.add_subcategory))
        dispatcher.add_handler(CommandHandler("removesubcategory", self.remove_subcategory))

        dispatcher.add_handler(CommandHandler("addbrand", self.add_brand))
        dispatcher.add_handler(CommandHandler("removebrand", self.remove_brand))

        dispatcher.add_handler(CommandHandler("changepercentage", self.change_percentage))

        dispatcher.add_handler(CommandHandler("status", self.get_status))
        dispatcher.add_handler(CommandHandler("help", self.help_command))

        updater.start_polling()
        updater.idle()