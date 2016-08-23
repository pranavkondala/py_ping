from datetime import datetime
import re, os, subprocess, time
from flask import Flask, request, jsonify, g, render_template, Response
from db import DB
import threading
import logging
import socket
from cymruwhois import Client

app = Flask(__name__)


def trace_route(dest_name):
    logging.debug('started trace '+ dest_name)
    dest_addr = socket.gethostbyname(dest_name)
    port = 33434
    max_hops = 30
    icmp = socket.getprotobyname('icmp')
    udp = socket.getprotobyname('udp')
    ttl = 1
    ttl_list = []
    asn_list = []
    host_addr_list = []
    host_name_list = []
    while True:
        recv_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, udp)
        send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
        recv_socket.bind(("", port))
        send_socket.sendto("", (dest_name, port))
        curr_addr = None
        curr_name = None
        try:
            _, curr_addr = recv_socket.recvfrom(512)
            curr_addr = curr_addr[0]
            try:
                curr_name = socket.gethostbyaddr(curr_addr)[0]
            except socket.error:
                curr_name = curr_addr
        except socket.error:
            pass
        finally:
            send_socket.close()
            recv_socket.close()

        if curr_addr is not None:
            curr_host = "%s (%s)" % (curr_name, curr_addr)
        else:
            curr_host = "*"
        c = Client()
        r = c.lookup(curr_addr)
        if r.asn is not None:
            host_addr_list.append(curr_addr)
            asn_list.append(r.asn)
            ttl_list.append(ttl)
            host_name_list.append(curr_host)

        ttl += 1
        if curr_addr == dest_addr or ttl == max_hops:
            break
    logging.debug('stop trace')
    return { 'asn_list':asn_list, 'host_list':host_name_list, 'host_add':host_addr_list}


def avg_packet_loss(packet_loss):
    count = 0
    total = 0
    loss = 0
    for i in packet_loss:
        if i != None:
            total += i
            count += 1
    if count != 0:
        loss = total / count
    print(loss)
    return loss


def avg_latency(latency):
    count = 0
    total = 0
    avg = 0
    for i in latency:
        if i != None:
            total += i
            count += 1
    if count != 0:
        avg = total / count
    print(avg)
    return avg


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
                    db.insert(dict(hostname=row['hostname'], dev_id=row['dev_id'], status='DOWN', ip_add=row['ip_add']))
                cmd = subprocess.Popen(["ping", "-c", "1", row['ip_add']], stdout=subprocess.PIPE)
                output = cmd.communicate()[0]
                match = re.search(b'(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)\s+ms', output)
                match_loss = re.search(b'(\d+\.\d+)+%', output)
                if not (match is None):
                    avg = float(match.group(1))
                    db.update_latency(dict(dev_id=row['dev_id'], latency=avg))
                    print(avg)
                if not (match_loss is None):
                    loss = float(match_loss.group(1))
                    db.update_packet_loss(dict(dev_id=row['dev_id'], packet_loss=loss))
                    print(loss)
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
    packet_loss = []
    devices = db.get_device_history(hostname)
    for dev in devices:
        x_data.append(dev['last_seen'])
        y_data.append(dev['latency'])
        packet_loss.append(dev['packet_loss'])
    # print (x_data,y_data,hostname)
    data = dict(x=x_data, y=y_data)
    length = len(x_data)
    avg = avg_latency(y_data)
    loss = avg_packet_loss(packet_loss)
    return render_template('device.html', data=data, length=length, avg=avg, loss=loss,
                           hostname=hostname)

@app.route('/traceroute/<ip_add>')
def traceroute(ip_add):
    db = get_db()
    devices = db.get_device_data(ip_add)
    data = trace_route(ip_add)
    logging.debug('stop trace webapp')
    return render_template('traceroute.html', devices=devices, data=data)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s', )
    ping = threading.Thread(name='pinger', target=check_ping)
    ping.setDaemon(True)
    ping.start()
    app.run(host='0.0.0.0', debug=True)
    ping.join()

