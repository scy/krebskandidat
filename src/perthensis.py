from machine import Pin, Signal
import network
import sys
import uasyncio
import ujson
import utime



class Scheduler:
    def __init__(self):
        self._tasks = []
        self.run = uasyncio.run
        self.sleep = uasyncio.sleep
        self.sleep_ms = uasyncio.sleep_ms
        self.wait_for = uasyncio.wait_for

    async def _wait_loop(self, interval):
        while True:
            await self.sleep_ms(interval)

    def create_task(self, coro, *args):
        task = uasyncio.create_task(coro(self, *args))
        self._tasks.append(task)
        return task

    def run_forever(self):
        self.run(self._wait_loop(10_000))



class Event:
    def __init__(self, name, more=None):
        self._listeners = []
        self._name = name
        self._more = more

    def __str__(self):
        return self._name

    def more(self):
        return self._more

    def listen(self, callback):
        self._listeners.append(callback)

    def trigger(self):
        for listener in self._listeners:
            try:
                listener(self)
            except Exception as e:
                print("Event listener for {} event failed:".format(self._name))
                sys.print_exception(e)



class Heartbeat:
    def __init__(self, scheduler, pin_id, invert=False):
        self._sig = Signal(pin_id, Pin.OUT, invert=invert)
        self._sig.off()
        scheduler.create_task(self._cycle)

    async def _cycle(self, sch):
        self._sig.on()
        await sch.sleep(2)
        while True:
            self._sig.on()
            await sch.sleep_ms(50)
            self._sig.off()
            await sch.sleep_ms(100)
            self._sig.on()
            await sch.sleep_ms(100)
            self._sig.off()
            await sch.sleep_ms(750)



class NTPClient:
    INITIAL_INTERVAL_SECONDS =     30 * 60
    REFRESH_INTERVAL_SECONDS = 6 * 60 * 60
    def __init__(self, scheduler, network, custom_host=None):
        import ntptime
        if isinstance(custom_host, str):
            ntptime.host = custom_host
        self._settime = ntptime.settime
        self._next_fetch_in = self.INITIAL_INTERVAL_SECONDS
        self._schedule_next_fetch()
        network.on_connect(self._connected)
        scheduler.create_task(self._watch)

    def _schedule_next_fetch(self):
        delay = self.REFRESH_INTERVAL_SECONDS if self.have_time() else self.INITIAL_INTERVAL_SECONDS
        print("Will try fetching time again in {0} minutes.".format(int(delay / 60)))
        self._next_fetch_in = delay

    def _watch(self, sch):
        self._try_fetch()
        while True:
            await sch.sleep(min(60, self._next_fetch_in))
            self._next_fetch_in -= 60
            if self._next_fetch_in <= 0:
                self._try_fetch()

    def _try_fetch(self):
        print("Fetching NTP time at:", utime.localtime())
        try:
            res = self._settime()
            if res or res is None:
                print("Fetching time was successful:", utime.localtime())
                self._schedule_next_fetch()
                return True
        except:
            pass
        print("Fetching time was unsuccessful.")
        self._schedule_next_fetch()
        return False

    def _connected(self, ev):
        if not self.have_time():
            self._try_fetch()

    def have_time(self):
        return utime.localtime()[0] >= 2020



class WifiClient:
    def __init__(self, config="/wifi.json"):
        self._statestrings = {}
        for state in ["IDLE", "CONNECTING", "WRONG_PASSWORD", "NO_AP_FOUND", "ASSOC_FAIL", "HANDSHAKE_TIMEOUT", "CONNECT_FAIL", "GOT_IP"]:
            attr = getattr(network, "STAT_" + state, None)
            if attr is not None:
                self._statestrings[attr] = state

        if isinstance(config, str): # read JSON file
            with open(config, "r") as cfg_file:
                config = ujson.load(cfg_file)
        if not isinstance(config, dict):
            raise RuntimeError("provide wifi config as path to JSON file or dict")
        self._ssid = config["ssid"]
        self._psk = config["psk"]
        self._hostname = config["hostname"]

        self._enable = False
        self._last_status = None

        self._on_connect = Event("connect", self)
        self.on_connect = self._on_connect.listen

        self._wifi = network.WLAN(network.STA_IF)

    def _statestr(self, state):
        return self._statestrings[state] if state in self._statestrings else "[unknown]"

    def _check(self):
        if self._wifi is None:
            return
        status = self._wifi.status()
        if self._enable:
            if status == network.STAT_IDLE:
                self._connect()
        else:
            if status != network.STAT_IDLE:
                self._disconnect()
        if status != self._last_status:
            print("Network state changed: {0} -> {1}".format(self._statestr(self._last_status), self._statestr(status)))
            if status == network.STAT_GOT_IP:
                self._on_connect.trigger()
            self._last_status = status

    def _connect(self):
        self._wifi.active(True)
        self._wifi.config(dhcp_hostname=self._hostname)
        #utime.sleep_ms(40) # this seems to help against some issues, see <https://github.com/micropython/micropython/issues/4269>
        self._wifi.connect(self._ssid, self._psk)

    def _disconnect(self):
        self._wifi.disconnect()
        self._wifi.active(False)

    def enable(self):
        self._enable = True
        self._check()

    def disable(self):
        self._enable = False
        self._check()

    async def watch(self, scheduler):
        while True:
            self._check()
            await scheduler.sleep_ms(5_000)

    def set_time_from_ntp(self):
        import ntptime
        ntptime.settime()



class DHT:
    def __init__(self, sensor, interval_s=60):
        self._sensor = sensor
        self._interval = int(interval_s)
        self._temperature = None
        self._humidity = None
        self._measurement = Event("measurement", self)
        self.on_measurement = self._measurement.listen

    def _measure(self):
        self._sensor.measure()
        self._temperature = self._sensor.temperature()
        self._humidity = self._sensor.humidity()
        self._measurement.trigger()

    def last_measurement(self):
        return {"temperature_c": self._temperature, "humidity_percent": self._humidity}

    async def watch(self, scheduler):
        while True:
            self._measure()
            await scheduler.sleep(self._interval)
