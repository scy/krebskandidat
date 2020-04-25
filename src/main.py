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

dht = DHT(DHT22(machine.Pin(15)), 10)
dht.on_measurement(lambda event: print(event.more().last_measurement()))
sch.create_task(dht.watch)

sch.run_forever()
