import configparser
import requests
import json
import logging

logging.captureWarnings(True)

config = configparser.ConfigParser()
config.read("./config.ini")

PROXY_ADDR = config.get("PROXY", "address")
PROXY_PORT = config.get("PROXY", "port")
PROXY_USER = config.get("PROXY", "username")
PROXY_PASSWORD = config.get("PROXY", "password")

if not PROXY_ADDR.strip() == "" and not PROXY_PORT.strip() == "":
    if PROXY_USER.strip() == "" or PROXY_PASSWORD.strip() == "":
        PROXY = PROXY_ADDR + ":" + PROXY_PORT
    else:
        PROXY = "http://" + PROXY_USER + ":" + PROXY_PASSWORD + "@" + PROXY_ADDR + ":" + PROXY_PORT
else:
    PROXY = None

TIMEOUT = 50

print(PROXY)

def my_ip():
    r = requests.get("https://httpbin.org/ip", timeout=TIMEOUT)

    return r.json()["origin"]

def test_proxy():
    proxies = {
        "http": PROXY,
        "https": PROXY
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15",
        "Cache-Control": "no-cache"
    }

    ip = my_ip()

    try:
        r = requests.get("https://httpbin.org/ip", timeout=TIMEOUT, proxies=proxies, verify=False)
    except requests.RequestException as e:
        print("Proxy didn't respond")
        print(f"Error {e}")
        return False
    
    if r.status_code == 200:
        try:
            if r.json()["origin"] != ip:
                url = "https://www.hepsiburada.com/elbiseler-c-12087202/"
                try:
                    r = requests.get(url, timeout=TIMEOUT, proxies=proxies, headers=headers, verify=False)
                except requests.RequestException as e:
                    print("Proxy didn't worked when trying to access the website")
                    print(e)
                    return False
                
                if r.status_code == 200:
                    print("Everything went fine")
                    return True
                else:
                    print("Proxy works, but is being blocked by the website")
                    print(status_code)
        except json.decoder.JSONDecodeError:
            print("An error occured when trying to make a request")
            return False
    
    return False

test_proxy()