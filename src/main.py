import gevent.monkey
gevent.monkey.patch_all(thread=True)

from bot import Bot


def main():
    bot = Bot()
    bot.start()

if __name__ == "__main__":
    main()