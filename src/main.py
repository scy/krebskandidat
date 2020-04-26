from dht import DHT22
import gc
import machine
from perthensis import DHT, Heartbeat, NTPClient, Scheduler, WifiClient
from sds011 import AdaptiveCycle, SDS011

gc.enable()

sch = Scheduler()

Heartbeat(sch, 2)

wc = WifiClient()
sch.create_task(wc.watch)
wc.enable()

NTPClient(sch, wc, "fritz.box")

def send_to_iotplotter(feed_id, api_key, values):
    import gc, urequests, utime
    gc.collect()
    data = "\n".join(["0,{1},{2}".format(key, val) for (key, val) in values.items()])
    print(data)
    res = urequests.post(
        "https://iotplotter.com/api/v2/feed/{0}.csv".format(feed_id),
        headers={"api-key": api_key},
        data=data
        )
    res.close()

dht = DHT(DHT22(machine.Pin(15)))
dht.on_measurement(lambda event: send_to_iotplotter("<your_feed_id>", "<your_api_key>", event.more().last_measurement()))
sch.create_task(dht.watch)

sds = SDS011(2, lambda pkt: print(str(pkt)))
sch.create_task(sds.watch)
ac = AdaptiveCycle(sds, 1)
sch.create_task(ac.watch)
ac.mode = ac.MODE_INTERVAL

sch.run_forever()
