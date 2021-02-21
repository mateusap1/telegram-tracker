import sqlite3


class Database(object):

    def __init__(self):
        self.conn = sqlite3.connect("data.db")
        self.c = self.conn.cursor()
    
    def __execute_command(self, command: str) -> None:
        self.c.execute(command)

    def create_table(self, name, **rows)    
    
database = Database()
database.execute_command("""CREATE TABLE users;
CREATE TABLE categories


""")