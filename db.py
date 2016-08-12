import sqlite3
import subprocess
import os
import re
import threading
import datetime

DBFILE = r'./ip_address.db'

class DB:

    def __init__(self):
        self._conn = None
        self.dbfile = DBFILE
        self.initialize()
        #self.repeat_check()

    def initialize(self):
        dbfile_exists = os.path.isfile(self.dbfile)
        db = self._conn = sqlite3.connect(self.dbfile)
        if dbfile_exists:
            if not self.schema_installed():
                raise Exception("ip_address.db doesnot have schema")
        else:
            self.create_schema()

    def schema_installed(self):
        c = self._conn.cursor()
        c.execute ("select name from sqlite_master where type = 'table';")
        return len(c.fetchall()) > 0

    def create_schema(self):
        c = self._conn.cursor()
        c.execute("""create table ip_address (
                dev_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname text,
                ip_add text,
                status text DEFAULT Pending,
                latency int,
                first_seen datetime,
                last_seen datetime
                )""")
        c.execute("""create table ping_history(
                hostname text,
                ip_add text,
                latency int,
                last_seen datetime
                )""")
        c.execute("""create trigger update_history update of last_seen on ip_address
                for each row
                begin
                 insert into ping_history(
                 hostname
                 , ip_add
                 , latency
                 , last_seen
                 )
                values
                 (
                 new.hostname
                 , new.ip_add
                 , new.latency
                 , new.last_seen
                 );
                END""")
        self._conn.commit()


    def insert(self, row):
        c = self._conn.cursor()
        c.execute("""
                    select
                        dev_id
                    from ip_address
                    where ip_add=?;
                """, [row['ip_add']])
        result = c.fetchall()
        if len(result) > 0:
            dev_id = result[0][0]
        else:
            dev_id = None
        now = datetime.datetime.utcnow()
        if dev_id is not None:
            c.execute("""update ip_address set
                            hostname=?
                            , ip_add=?
                            , last_seen=?
                            , status=?
                        where dev_id=?;""", [row['hostname'], row['ip_add'], now, row['status'],dev_id])
            self._conn.commit()
        else:
            c.execute("""insert into ip_address(
            hostname
            , ip_add
            , first_seen
            , last_seen
            , status
            ) values (?, ?, ?, ?, ?);
            """, [row['hostname'], row['ip_add'], now, now, row['status']])
        self._conn.commit()

    def retrieve(self, dev_id):
        c = self._conn.cursor()
        cursor = c.execute('select * from ip_address where dev_id = ?', (dev_id, ))
        return cursor.fetchone()

    def update(self, row):
        c = self._conn.cursor()
        c.execute('update ip_address set status = ? where dev_id = ?', (row['status'], row['dev_id']))
        self._conn.commit()

    def update_latency(self, row):
        c = self._conn.cursor()
        c.execute('update ip_address set latency= ? where dev_id = ?', (row['latency'], row['dev_id']))
        self._conn.commit()

    def delete(self, hostname):
        c = self._conn.cursor()
        c.execute('delete from ip_address where hostname = ?', (hostname,))
        self._conn.commit()

    def disp_rows(self):
        c = self._conn.cursor()
        cursor = c.execute('select * from ip_address order by hostname')
        for row in cursor:
            print('  {} | {} | {} | {} | {}'.format(row['dev_id'], row['hostname'], row['ip_add'], row['status'], row['latency']))

    def get_device_data (self, ip_add = None):
        devlist = list()
        c = self._conn.cursor()
        if ip_add is None:
            c.execute("""select dev_id,
                            hostname,
                            ip_add,
                            status,
                            latency,
                            last_seen,
                            first_seen
                            from ip_address;""")
        else:
            c.execute("""select dev_id,
                            hostname,
                            ip_add,
                            status,
                            latency,
                            last_seen,
                            first_seen from ip_address where ip_add=?""", [ip_add])
        results = c.fetchall()
        for r in results:
            dev_dict = dict()
            dev_id = r[0]
            dev_dict['dev_id'] = r[0]
            dev_dict['hostname'] = r[1]
            dev_dict['ip_add'] = r[2]
            dev_dict['status'] = r[3]
            dev_dict['latency'] = r[4]
            dev_dict['last_seen'] = r[5]
            dev_dict['first_seen'] = r[6]
            devlist.append(dev_dict)
        return devlist

    def check_ping(self):
        rows = self.get_device_data()
        for row in rows:
            r = os.system('ping -c 1 ' + row['ip_add'])
            if r == 0:
                self.insert(dict(hostname = row['hostname'], dev_id=row['dev_id'], status='UP', ip_add=row['ip_add']))
            else:
                self.insert(dict(hostname = row['hostname'], dev_id=row['dev_id'], status='DOWN', ip_add=row['ip_add']))
            cmd = subprocess.Popen(["ping", "-c", "1", row['ip_add']], stdout=subprocess.PIPE)
            output = cmd.communicate()[0]
            match = re.search(b'(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)\s+ms', output)
            if not (match is None):
                avg = float(match.group(1))
                self.update_latency(dict(dev_id=row['dev_id'], latency=avg))

    def get_device_history(self, hostname):
        devlist = list()
        c = self._conn.cursor()
        c.execute("""select
              ip_add
            , last_seen
            , latency
            from ping_history where hostname=? order by last_seen DESC limit 120""", [hostname])
        results = c.fetchall()
        for r in results:
            dev_dict = dict()
            dev_dict['ip_add'] = r[0]
            dev_dict['last_seen'] = r[1]
            dev_dict['latency'] = r[2]
            devlist.append(dev_dict)
        return devlist

    def repeat_check(self):
        self.check_ping()
        threading.Timer(30, self.repeat_check)

    def close(self):
        self._conn.close()

