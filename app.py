from flask import Flask, render_template, redirect, url_for, request
from dotenv import load_dotenv
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError

from hashlib import md5
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from base64 import b64decode
from base64 import b64encode

import json
import requests
import os
import sys
import re
import time

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("CSRF_SECRET_KEY")

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

def send_local_post(ip, mac, enr):
    characteristics = """
{{
    "mac": "{mac}",
    "index": "0",
    "ts": "{ts}",
    "plist": [
        {{
            "pid": "P3",
            "pvalue": "1"
        }},
        {{
            "pid": "P1507",
            "pvalue": "ff00ff"
        }},
        {{
            "pid": "P1501",
            "pvalue": "100"
        }}
    ]
}}""".format(mac=mac, ts=int(time.time() * 1000))

    # P3 - on/off (1 = on, 0 = off)
    # P1501 - brightness (0 - 100)
    # P1502 - temperature (1000 - 6000)
    # P1507 - rgb (00ff00)

    encrypted = AESCipher(enr, enr).encrypt(characteristics)
    #decrypted = AESCipher(enr, enr).decrypt(encrypted)

    body = {
        "request": "set_status",
        "isSendQueue": 0,
        "characteristics": encrypted
    }
    bodyString = json.dumps(body,separators=(',', ':'))
    print(f"bodyString: {bodyString}")
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(bodyString)),
    }
    response = requests.post(f'http://{ip}:88/device_request', headers=headers, data=bodyString)
    print(response.__dict__, file=sys.stderr)

@app.route('/testlocal')
def localtest():
    # console light:
    #send_local_post("10.5.27.4", "7C78B2212876", "QvoMI4VyzSn7oXDw")
    # bedside bulb:
    send_local_post("10.5.27.7", "7C78B21DFC9F", "bxJs6+NdUP9KOv9h")

    return "ok", 200


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


@app.route('/bulb/set/<mac>/<model>', methods = ['GET', 'POST'])
def bulb_set(mac, model):
    client = get_client()
    try:
        if 'onoff' in request.values and request.values['onoff']:
            onoff = request.values['onoff']
            if onoff == 'on':
                client.bulbs.turn_on(device_mac=mac, device_model=model)
            elif onoff == 'off':
                client.bulbs.turn_off(device_mac=mac, device_model=model)

        if 'brightness' in request.values and request.values['brightness']:
            brightness = request.values['brightness']
            client.bulbs.set_brightness(device_mac=mac, device_model=model, brightness=brightness)

        if 'temp' in request.values and request.values['temp']:
            temp = request.values['temp']
            client.bulbs.set_color_temp(device_mac=mac, device_model=model, color_temp=temp)

        elif 'color' in request.values and request.values['color']:
            color = request.values['color']
            client.bulbs.set_color(device_mac=mac, device_model=model, color=color)

        if 'q' in request.values and request.values['q']:
            q = request.values['q']
            print(f'matching q = "{q}"', file=sys.stderr)

            m = re.search(r'\bon\b', q)
            if (m):
                print('matches for on', file=sys.stderr)
                client.bulbs.turn_on(device_mac=mac, device_model=model)

            m = re.search(r'\boff\b', q)
            if (m):
                print('matches for off', file=sys.stderr)
                client.bulbs.turn_off(device_mac=mac, device_model=model)

            m = re.search(r'\bcool|cold\b', q)
            if (m):
                print('matches for cool/cold', file=sys.stderr)
                client.bulbs.set_color_temp(device_mac=mac, device_model=model, color_temp='4300')

            m = re.search(r'\bdaylight\b', q)
            if (m):
                print('matches for daylight', file=sys.stderr)
                client.bulbs.set_color_temp(device_mac=mac, device_model=model, color_temp='6500')

            m = re.search(r'\bwarm\b', q)
            if (m):
                print('matches for warm', file=sys.stderr)
                client.bulbs.set_color_temp(device_mac=mac, device_model=model, color_temp='3000')

            m = re.search(r'\b#?([a-fA-F0-9]{6})\b', q)
            if (m):
                print(f'matches for rrggbb: #{m[1]}', file=sys.stderr)
                client.bulbs.set_color(device_mac=mac, device_model=model, color=m[1])

            m = re.search(r'\b(\d{1,3}),(\d{1,3}),(\d{1,3})\b', q)
            if (m):
                rgb = '{:02x}{:02x}{:02x}'.format(int(m[1]), int(m[2]), int(m[3]))
                print(f'matches for rr,gg,bb: {m[1]}, {m[2]}, {m[3]} => #{rgb}', file=sys.stderr)
                client.bulbs.set_color(device_mac=mac, device_model=model, color=rgb)

            m = re.search(r'\b(100|\d?\d)%', q)
            if (m):
                print(f'matches for brightness: {m[1]}%', file=sys.stderr)
                client.bulbs.set_brightness(device_mac=mac, device_model=model, brightness=m[1])

            m = re.search(r'\b(\d{4})[kK]\b', q)
            print(m, file=sys.stderr)
            if (m):
                print(f'matches for color temperature: {m[1]}K', file=sys.stderr)
                client.bulbs.set_color_temp(device_mac=mac, device_model=model, color_temp=m[1])

        return "ok", 200
        #return redirect(url_for("bulb_get", mac=mac))

    except WyzeApiError as e:
        return render_template('error.html', error=e)


if __name__ == '__main__':
    app.run(host='0.0.0.0')
