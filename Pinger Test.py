import os
import sqlite3
import datetime
import ipaddress

DBFILE = r'./pinger.db'

class DB:
    def __init__(self):
        self.dbfile = DBFILE
        self._conn = None
        self.initialize()

    def initialize(self):
        dbfile_exists = os.path.isfile(self.dbfile)
        self._conn = sqlite3.connect(self.dbfile)
        if dbfile_exists:
            if not self.is_schema_installed():
                raise Exception ("pinger.db does not have scheme configured")
            else:
                self.create_scheme()
                print('success')

    def is_schema_installed(self):
        c = self._conn.cursor()
        c.execute("""
            select name from sqlite_master where type='table';
        """)
        return len(c.fetchall()) > 0

    def create_schema(self):
        """
        Creates database schema in a blank database.
        :return: None
        """
        c = self._conn.cursor()
        c.execute("""
            create table ip_add (
                dev_id integer primary key,
                hostname text,
                ip_add text,
                first_seen datetime,
                last_updated datetime,
                latency float,
                status text);
        """)
        self._conn.commit()



"""
hostname = "google.com"
response = os.system("ping -c 1 " + hostname)

#and then check the response...
if response == 0:
  print (hostname, 'is up!')
else:
  print (hostname, 'is down!')
  """