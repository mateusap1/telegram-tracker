import logging
from bot import Bot


logging.basicConfig(level=logging.CRITICAL)
def main():
    bot = Bot()
    bot.start()

if __name__ == "__main__":
    main()