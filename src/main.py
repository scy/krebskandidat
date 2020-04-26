from dht import DHT22
import machine
from perthensis import DHT, Heartbeat, NTPClient, Scheduler, WifiClient

machine.freq(80_000_000)

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

sch.run_forever()
