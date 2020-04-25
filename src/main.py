import machine
from perthensis import Heartbeat, NTPClient, Scheduler, WifiClient

machine.freq(80_000_000)

sch = Scheduler()

Heartbeat(sch, 2)

wc = WifiClient()
sch.create_task(wc.watch)
wc.enable()
wc._connect()

NTPClient(sch, wc, "fritz.box")

sch.run_forever()
