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

ntp = NTPClient(sch, wc, "fritz.box")

def send_to_iotplotter(feed_id, api_key, values):
    import gc, urequests, utime
    gc.collect()
    epoch = ntp.time() if ntp.have_time() else 0
    data = "\n".join(["{0},{1},{2}".format(epoch, key, val) for (key, val) in values.items()])
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

ac = AdaptiveCycle(2, lambda avg: send_to_iotplotter("<your_feed_id>", "<your_api_key>", avg.flat_values))
sch.create_task(ac._sds.watch)
sch.create_task(ac.watch)
ac.mode = ac.MODE_INTERVAL

sch.run_forever()
