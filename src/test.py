from requests_html import AsyncHTMLSession
asession = AsyncHTMLSession()

async def get_pythonorg():
    r = await asession.get('https://python.org/')
    print(r.html)

async def get_reddit():
    r = await asession.get('https://reddit.com/')
    print(r.html)

async def get_google():
    r = await asession.get('https://google.com/')
    print(r.html)

result = asession.run(*[lambda: get_pythonorg(), get_reddit, get_google])