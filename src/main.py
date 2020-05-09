from dht import DHT22
import gc
import machine
from machine import Pin
from perthensis import Debouncer, DHT, Heartbeat, NTPClient, Scheduler, WifiClient
from sds011 import AdaptiveCycle, SDS011

class IoTPlotter:
    def __init__(self, feed_id, api_key):
        self.feed_id = feed_id
        self.api_key = api_key

    def send(self, values):
        import gc, urequests, utime
        gc.collect()
        epoch = ntp.time() if ntp.have_time() else 0
        data = "\n".join(["{0},{1},{2}".format(epoch, key, val) for (key, val) in values.items()])
        print(data)
        res = urequests.post(
            "https://iotplotter.com/api/v2/feed/{0}.csv".format(self.feed_id),
            headers={"api-key": self.api_key},
            data=data
            )
        res.close()

iotp = IoTPlotter("<your_feed_id>", "<your_api_key>")

gc.enable()

sch = Scheduler()

Heartbeat(sch, 2)

wc = WifiClient()
sch.create_task(wc.watch)
wc.enable()

ntp = NTPClient(sch, wc, "fritz.box")

dht = DHT(DHT22(Pin(15)))
dht.on_measurement(lambda event: iotp.send(event.more().last_measurement()))
sch.create_task(dht.watch)

ac = AdaptiveCycle(2, lambda avg: iotp.send(avg.flat_values))
sch.create_task(ac._sds.watch)
sch.create_task(ac.watch)
ac.mode = ac.MODE_INTERVAL

door_power = Pin(13, Pin.OUT, value=1)
door = Debouncer(12, Pin.PULL_DOWN, 3000)
door.on_change(lambda event: print("Door:", event.more().value()))
sch.create_task(door.watch)

sch.run_forever()
