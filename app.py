# flask
from flask import Flask, render_template, redirect, url_for, request

# wyze
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

# crypto
from hashlib import md5
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base64 import b64decode
from base64 import b64encode

# system utils
import json
import requests
import os
import sys
import re
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(12).hex()

cached_client_expiration = 0
cached_client_ttl = 60 * 60 * 12

class AESCipher:
    def __init__(self, key, iv):
        self.key = key.encode('utf8')
        self.iv = iv.encode('utf8')

    def encrypt(self, data):
        self.cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return b64encode(self.cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))).decode('utf-8')

    def decrypt(self, data):
        raw = b64decode(data)
        self.cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return unpad(self.cipher.decrypt(raw), AES.block_size).decode('utf-8')

def get_client():
    global cached_client_expiration
    global cached_client_ttl
    global cached_client
    now = time.time()
    if now > cached_client_expiration:
        cached_client = Client(email=os.environ.get("WYZE_USER"), password=os.environ.get("WYZE_PASSWORD"))
        cached_client_expiration = now + cached_client_ttl
    return cached_client


def api_bulb_set(bulb, onoff="", color="", brightness="", temp=""):
    client = get_client()
    if onoff == "on":
        client.bulbs.turn_on(device_mac=bulb.mac, device_model=bulb.product.model)
    elif onoff == "off":
        client.bulbs.turn_off(device_mac=bulb.mac, device_model=bulb.product.model)

    if color:
        client.bulbs.set_color(device_mac=bulb.mac, device_model=bulb.product.model, color=color)
    elif temp:
        client.bulbs.set_color_temp(device_mac=bulb.mac, device_model=bulb.product.model, color_temp=temp)

    if brightness:
        client.bulbs.set_brightness(device_mac=bulb.mac, device_model=bulb.product.model, brightness=brightness)


def local_bulb_set(bulb, onoff="", color="", brightness="", temp=""):
    characteristics = {
        "mac": bulb.mac,
        "index": "0",
        "ts": str(int(time.time() * 1000)),
        "plist": []
    }

    # P3 - on/off (1 = on, 0 = off)
    # P1501 - brightness (0 - 100)
    # P1502 - temperature (1000 - 6000)
    # P1507 - rgb (00ff00)

    if onoff == "on":
        characteristics["plist"].append({ "pid": "P3", "pvalue": "1" })
    elif onoff == "off":
        characteristics["plist"].append({ "pid": "P3", "pvalue": "0" })

    if color:
        characteristics["plist"].append({ "pid": "P1507", "pvalue": color })
    elif temp:
        characteristics["plist"].append({ "pid": "P1502", "pvalue": str(temp) })

    if brightness:
        characteristics["plist"].append({ "pid": "P1501", "pvalue": str(brightness) })

    if not len(characteristics["plist"]):
        return

    dumped = json.dumps(characteristics, separators=(',',':'))
    encrypted = AESCipher(bulb.enr, bulb.enr).encrypt(dumped)
    #decrypted = AESCipher(bulb.enr, bulb.enr).decrypt(encrypted)

    body = {
        "request": "set_status",
        "isSendQueue": 0,
        "characteristics": encrypted
    }
    response = requests.post(f'http://{bulb.ip}:88/device_request', json=body)
    print(response.__dict__, file=sys.stderr)

@app.route('/')
def get_lights():
    client = get_client()
    message = ''
    try:
        response = client.bulbs.list()
        return render_template('index.html', bulbs=response, message=message)

    except WyzeApiError as e:
        message = e
    return render_template('index.html', message=message)


@app.route('/bulb/<mac>')
def bulb_get(mac):
    client = get_client()
    message = ''
    try:
        response = client.bulbs.info(device_mac=mac)
        print(response.__dict__, file=sys.stderr)
        return render_template('bulb.html', bulb=response, message=message)

    except WyzeApiError as e:
        return render_template('error.html', error=e)


@app.route('/bulb/set/<mac>', methods = ['GET', 'POST'])
def bulb_set(mac):

    onoff = ""
    brightness = ""
    temp = ""
    color = ""

    if 'onoff' in request.values and request.values['onoff']:
        onoff = request.values['onoff']

    if 'brightness' in request.values and request.values['brightness']:
        brightness = request.values['brightness']

    if 'temp' in request.values and request.values['temp']:
        temp = request.values['temp']

    elif 'color' in request.values and request.values['color']:
        color = request.values['color']

    if 'q' in request.values and request.values['q']:
        q = request.values['q']
        print(f'matching q = "{q}"', file=sys.stderr)

        m = re.search(r'\bon\b', q)
        if (m):
            print('matches for on', file=sys.stderr)
            onoff = "on"

        m = re.search(r'\boff\b', q)
        if (m):
            print('matches for off', file=sys.stderr)
            onoff = "off"

        m = re.search(r'\bcool|cold\b', q)
        if (m):
            print('matches for cool/cold', file=sys.stderr)
            temp = "4300"

        m = re.search(r'\bdaylight\b', q)
        if (m):
            print('matches for daylight', file=sys.stderr)
            temp = "6500"

        m = re.search(r'\bwarm\b', q)
        if (m):
            print('matches for warm', file=sys.stderr)
            temp = "3000"

        m = re.search(r'\b#?([a-fA-F0-9]{6})\b', q)
        if (m):
            print(f'matches for rrggbb: #{m[1]}', file=sys.stderr)
            color = m[1]

        m = re.search(r'\b(\d{1,3}),(\d{1,3}),(\d{1,3})\b', q)
        if (m):
            rgb = '{:02x}{:02x}{:02x}'.format(int(m[1]), int(m[2]), int(m[3]))
            print(f'matches for rr,gg,bb: {m[1]}, {m[2]}, {m[3]} => #{rgb}', file=sys.stderr)
            color = rgb

        m = re.search(r'\b(100|\d?\d)%', q)
        if (m):
            print(f'matches for brightness: {m[1]}%', file=sys.stderr)
            brightness = m[1]

        m = re.search(r'\b(\d{4})[kK]\b', q)
        print(m, file=sys.stderr)
        if (m):
            print(f'matches for color temperature: {m[1]}K', file=sys.stderr)
            temp = m[1]

    if onoff or brightness or color or temp:
        client = get_client()
        bulb = client.bulbs.info(device_mac=mac)
        local_bulb_set(bulb, onoff=onoff, brightness=brightness, color=color, temp=temp)
        #try:
            #api_bulb_set(bulb, onoff=onoff, brightness=brightness, color=color, temp=temp)
        #except WyzeApiError as e:
            #return render_template('error.html', error=e)

    return "ok", 200
    #return redirect(url_for("bulb_get", mac=mac))



if __name__ == '__main__':
    app.run(host='0.0.0.0')
