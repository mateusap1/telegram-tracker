from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from scraper import Scraper

import json


MAIN_URL = 'https://www.hepsiburada.com/'


class Bot(object):

    def __init__(self):
        self.scraper = Scraper()
        self.possible_categories = self.scraper.get_categories()
        self.categories = {}
        self.initial_products = {}
        self.products_with_discount = []
        self.percentage = 0

        self.load_initial_products()

        self.job_running = None
        self.delay = 30
    
    def save_initial_products(self):
        data = {
            "categories": self.categories,
            "initial_products": self.initial_products
        }

        with open('data.json', 'w') as json_file:
            json.dump(data, json_file)
    
    def load_initial_products(self):
        with open('data.json', 'r') as json_file:
            json_read = json.load(json_file)
            self.categories = dict(json_read["categories"])
            self.initial_products = dict(json_read["initial_products"])

    def price_tracking(self, context: CallbackContext):
        job = context.job

        current_products = {}
        categories = self.categories.items()
        for category, url in categories:
            category_products = self.scraper.get_products(url)
            for product_id, product_data in category_products.items():
                current_products[product_id] = product_data
        
        for product_id, current_product_data in current_products.items():
            if self.job_running is None:
                return

            if not product_id in self.initial_products:
                self.initial_products[product_id] = current_product_data
                continue

            initial_product_data = self.initial_products[product_id]
            
            initial_price = float(initial_product_data["price"])
            current_price = float(current_product_data["price"])
            
            price_difference = initial_price - current_price
            percentage = price_difference / initial_price
            percentage_str = str("%.2f" % (percentage * 100))

            if percentage >= self.percentage:
                message = current_product_data["product_name"] + "\n\n" + \
                          "Satıcı: " + current_product_data["merchant"] + "\n\n" + \
                          initial_product_data["price"] + " TL >>>> " + \
                          current_product_data["price"] + f" TL - {percentage_str}%" + "\n\n" + \
                          current_product_data["url"] + "\n\n" + \
                          MAIN_URL + "ara?q=" + product_id

                context.bot.send_message(
                    chat_id = job.context, 
                    text = message
                )

                self.initial_products[product_id] = current_product_data

        self.save_initial_products()
    
    def start_bot(self, update: Update, context: CallbackContext) -> None:
        """Message the user when the price is low"""
        if not self.job_running is None:
            update.message.reply_text('Sorry, the price tracker is already running')
            return

        if len(context.args) != 1:
            update.message.reply_text(
                'Sorry, you need to pass the percentage as an argument.\n' +
                'Example: /start 20%'
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
        
        self.percentage = percentage
        
        update.message.reply_text('Starting price tracker...')
        self.job_running = self.job.run_repeating(
            self.price_tracking, 
            interval = self.delay, 
            first = 0,
            context = update.message.chat_id
        )
    
    def stop_bot(self, update: Update, context: CallbackContext) -> None:
        """Stops tracking price loop"""
        if self.job_running is None:
            update.message.reply_text('Bot is already stopped')
        else:
            self.job_running.schedule_removal()
            self.job_running = None
            update.message.reply_text('Stoping bot...')
        
    def add_category(self, update: Update, context: CallbackContext) -> None:
        """Adds a category to the list"""

        # TODO: Make it asynchronously
        if len(context.args) < 1:
            update.message.reply_text(
                "Sorry, you must pass the category as an argument\n" + 
                "Example: /addcategory Elektronik"
            )
            return

        category = " ".join(context.args)
        if not category in self.possible_categories:
            update.message.reply_text(
                "Sorry, category not found\n" + 
                "Possible categories:\n" +
                "\n".join([category for category, url in self.possible_categories.items()])
            )
            return
        
        self.categories[category] = self.possible_categories[category]
        self.save_initial_products()

        update.message.reply_text("Category added successfuly")

    def remove_category(self, update: Update, context: CallbackContext) -> None:
        """Removes a category from the list"""

        if len(context.args) < 1:
            update.message.reply_text(
                "Sorry, you must pass the category as an argument\n" + 
                "Example: /removecategory Elektronik"
            )
            return

        category = " ".join(context.args)

        if not category in self.categories:
            update.message.reply_text(
                "Sorry, this category wasn't in the list\n" + 
                "Your categories:\n" +
                "\n".join([category for category, url in self.categories.items()])
            )
            return
        
        new_categories = {}

        for cat, url in self.categories.items():
            if cat != category:
                new_categories[cat] = url

        self.categories = new_categories # remove category

        category_products = self.scraper.get_products(self.possible_categories[category])

        self.initial_products =  [product for product in self.initial_products \
                                  if not product in category_products]
        self.save_initial_products()
        
        update.message.reply_text(f"The category \"{category}\" was successfuly removed")
    
    def get_status(self, update: Update, context: CallbackContext) -> None:
        if self.job_running is None:
            update.message.reply_text(
                "Tracker Status: Stopped\n" +
                f"Current Percentage: {self.percentage * 100}%\n" +
                "Categories: " + 
                (", ".join(self.categories.keys()) if self.categories.keys() else "Empty")
            )
        else:
            update.message.reply_text(
                "Tracker Status: Running\n" +
                f"Current Percentage: {self.percentage * 100}%\n" +
                "Categories: " + 
                (", ".join(self.categories.keys()) if self.categories.keys() else "Empty")
            )
        
    def change_percentage(self, update: Update, context: CallbackContext) -> None:
        if self.job_running is None:
            update.message.reply_text('Sorry,, you need to start the tracker in order to change the price')
            return

        if len(context.args) != 1:
            update.message.reply_text(
                "Sorry, you must pass the percentage as an argument\n" + 
                "Example: /changepercentage 30%"
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
            "/addcategory <category>: adds a category to the list\n" +
            "/removecategory <category>: removes a category from the list\n" +
            "/changepercentage <new percentage>: changes the percentage to a new value\n" +
            "/status: messages the product status"
        )
    
    def start(self):
        updater = Updater("1549588597:AAHsFKTLD6glkm1EWPL_qWPkLgXnwEx01r8", use_context=True)
        self.job = updater.job_queue

        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher

        # on different commands - answer in Telegram
        dispatcher.add_handler(CommandHandler("start", self.start_bot))
        dispatcher.add_handler(CommandHandler("stop", self.stop_bot))

        dispatcher.add_handler(CommandHandler("addcategory", self.add_category))
        dispatcher.add_handler(CommandHandler("removecategory", self.remove_category))

        dispatcher.add_handler(CommandHandler("changepercentage", self.change_percentage))

        dispatcher.add_handler(CommandHandler("status", self.get_status))
        dispatcher.add_handler(CommandHandler("help", self.help_command))

        updater.start_polling()
        updater.idle()