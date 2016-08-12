from datetime import datetime
import re, os, subprocess, time
from flask import Flask, request, jsonify, g, render_template
from db import DB
import pygal
import threading
import logging

app = Flask(__name__)

def check_ping():
    with app.app_context():
         logging.debug('started')
         db = get_db()
         while True:
             rows = db.get_device_data()
             for row in rows:
                 r = os.system('ping -c 1 ' + row['ip_add'])
                 if r == 0:
                     db.insert(dict(hostname=row['hostname'], dev_id=row['dev_id'], status='UP', ip_add=row['ip_add']))
                 else:
                     db.insert(dict(hostname=row['hostname'], dev_id=row['dev_id'], status='Down', ip_add=row['ip_add']))
                 cmd = subprocess.Popen(["ping", "-c", "1", row['ip_add']], stdout=subprocess.PIPE)
                 output = cmd.communicate()[0]
                 match = re.search(b'(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)\s+ms', output)
                 if not (match is None):
                     avg = float(match.group(1))
                     db.update_latency(dict(dev_id=row['dev_id'], latency=avg))
             time.sleep(1)
         logging.debug('exited')
         return None


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = DB()
    return db


@app.route("/")
def hello():
    return render_template('index.html')


@app.route("/devices")
def devices():
    db = get_db()
    devices = db.get_device_data()
    print(devices)
    return render_template('devices.html', devices=devices)


@app.route("/add_dev")
def add_dev():
    return render_template('add_dev.html')


@app.route('/adddev', methods=['POST', 'GET'])
def adddev():
    db = get_db()
    if request.method == 'POST':
        try:
            hn = request.form['hostname']
            ipadd = request.form['ip_add']
            print(hn, ipadd)
            db.insert(dict(hostname=hn, ip_add=ipadd, status=None))
            msg = "record successful"
        except:
            msg = "error"

        finally:
            return render_template("result.html", msg=msg)


@app.route('/device/<hostname>')
def device(hostname):
    db = get_db()
    x_data = []
    y_data = []
    devices = db.get_device_history(hostname)
    for dev in devices:
        x_data.append(dev['last_seen'])
        y_data.append(dev['latency'])
    # print (x_data,y_data,hostname)
    line_chart = pygal.StackedLine(fill=True)
    line_chart.title = 'Ping History'
    line_chart.x_lablels = x_data
    line_chart.add(hostname, y_data)
    graph = line_chart.render(is_unicode=True)
    return render_template('device.html', graph=graph)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s', )
    ping = threading.Thread(name='pinger', target=check_ping)
    ping.setDaemon(True)
    ping.start()
    app.run()
