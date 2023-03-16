wyze-python
===========

A simple web frontend for controlling Wyze bulbs. This uses the popular [python api from shauntarves](https://github.com/shauntarves/wyze-sdk), and also uses the unpublished local API for bulbs, as discussed on [wyze forums](https://forums.wyze.com/t/wyze-local-api-encoding-changes/206479) and a long time ago in [this issue](https://github.com/noelportugal/wyze-node/issues/15) on wyze-node. [This example](https://gist.github.com/lopes/168c9d74b988391e702aac5f4aa69e41) helped sort out the crypto bit.

Think of this as a gateway to your local Wyze bulbs. It could be run on a Raspbery Pi. I use it with Node-RED. It provides a simple GET request interface to control your bulbs. Here are some examples:

Run the server:
```
> WYZE_USER=me@gmail.com WYZE_PASSWORD=mypassword python3 app.py
```

Go find your bulbs and try out some examples from the comfort of your browser:
```
http://raspberrypi:5000/
```

Turn on the office bulb:
```
http://raspberrypi:5000/bulb/set/7C78B1234567?q=on
```

Change it to green:
```
http://raspberrypi:5000/bulb/set/7C78B1234567?q=00ff00
```

Dim it to 50% and set it to a warm white:
```
http://raspberrypi:5000/bulb/set/7C78B1234567?q=warm,50%25
```
