## Telegram Bot Usage

### Python Installation Guide
A nice step-by-step guide on how to install python can be found on https://phoenixnap.com/kb/how-to-install-python-3-windows. I would make a video showing to you, but I am using Linux while you are using Windows. Just make sure to choose python 3.6 when needing to choose the Python version.

If you prefer a video, the following link is a good option https://www.youtube.com/watch?v=UvcQlPZ8ecA.

If you still cannot download it with none of those tutorials, contact me and I will help you.

### Making sure everything was installed
Before following to this next step make sure Python was installed by following these small steps.

- Click on the Windows icon in the bottom-left corner of your screen,
- Type `cmd`
- Press ENTER and wait for the terminal to open
- Type `python --version`

If you can see a `Python 3.x.y` (not `x` and `y` literally, but something like that), it was installed successfuly.

### Telegram Bot Instalation
After installing Python, the next steps are simple.

First thing you need to do is to open a terminal (same steps as before) and move to the directory where this project folder is by typing `cd <path to this folder>`. So let's say this is in the Downloads folder. You would open a terminal and type `cd Downloads/telegram_tracker`.

Now you should install the dependencies. This is easily done by typing `pip install -r requirements.txt`

To run the bot now is simple, you can type `python src/main.py` and your bot is running.

If you are confused by what commands to send, you can type `/help` and the bot will send you the explanation of each command. If you still don't understand, though, you can ask me.
