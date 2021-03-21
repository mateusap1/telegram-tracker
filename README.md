## config.ini

An explanation of each of the "config.ini" attributes and in what they affect

* DEFAULT
    * channel_id: The telegram ID of the channel the messages will be sent to when there is a price drop.
    * bot_key: The API key of the telegram bot.
    * threads: The number of process that will be executed at the same time. If the mode is "scrape" (see next topic), it will scrape "threads" number of pages at the same time. If the mode is "compare", it will compare "threads" simultaneously. Finally, if the mode is "scrape-compare", it will scrape 3/4 of "threads" pages and compare 1/4 of products also at the same time.
    * mode: If the bot must only compare prices, scrape products or do both.

* TIME
    * timeout_requests: The time limit in seconds of a request.
    * timeout_thread: The time limit in seconds of the scraping of one page.
    * cycle_delay: The time in seconds it takes to call a new cycle. If the old cycle is still running it will wait until the next time.
    * expire_products: How old, in minutes, a product must be in order for it to be deleted.
    * older_products_range: When comparing prices, the program will get the cheapest product between the oldest product and those who are "older_products_range" minutes "younger". Then it will compare to the cheapest reamining product. If there's a significant difference in the price, it will warn the user.

* PROXY
    * address: The proxys address.
    * port: The proxys port.
    * username: The proxys username.
    * password: The proxys password.

* DATABASE
    * host: The database IP address
    * user: The database username.
    * password: The database password.