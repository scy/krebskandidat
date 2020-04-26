class Packet:
    def __init__(self, command=0, data=b"", address=b"\xff\xff"):
        self.command = command
        self.data = data
        self.address = address

    @staticmethod
    def checksum_for(data):
        assert isinstance(data, (bytes, bytearray))
        return bytes([sum(data) % 256])

    @classmethod
    def from_bytes(c, data):
        assert isinstance(data, (bytes, bytearray))
        cmd = data[0]
        if cmd == 0xc0:
            c = Measurement
        p = c(cmd, data[1:-3], data[-3:-1])
        if p.checksum == bytes([data[-1]]):
            return p
        raise ValueError("checksum is {0:02x}, expected {1:02x}".format(data[-1], p.checksum[0]))

    @property
    def command(self):
        return self._command

    @command.setter
    def command(self, cmd):
        self._command = int(cmd) & 0xff

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, bytestr):
        assert isinstance(bytestr, (bytes, bytearray))
        self._data = bytes(bytestr)

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, addr):
        assert isinstance(addr, (bytes, bytearray))
        self._address = bytes(addr)

    @property
    def checksum(self):
        return self.checksum_for(self.data + self.address)

    @property
    def bytes(self):
        return bytes([self.command]) + self.data + self.address + self.checksum

    def __str__(self):
        from ubinascii import hexlify
        return "{0:02x}: {1} [{2}]".format(self.command, hexlify(self.data, " "), hexlify(self.address, " "))



class Measurement(Packet):
    @Packet.command.setter
    def command(self, cmd):
        if cmd != 0xc0:
            raise ValueError("Measurement has to be command C0")
        self._command = 0xc0

    @property
    def values(self):
        return {
            "pm25": (self.data[0] + (self.data[1] << 8) / 10.0),
            "pm10": (self.data[2] + (self.data[3] << 8) / 10.0),
            }

    def __str__(self):
        values = self.values
        return "{0:.1f} µg/m³ PM10, {1:.1f} µg/m³ PM2.5".format(values["pm10"], values["pm25"])




class SDS011:
    def __init__(self, uart_id, input_callback):
        from machine import UART
        import ucollections, utime
        self._sendq = ucollections.deque((), 5)
        self._next_send = utime.ticks_ms()
        self._uart = UART(uart_id)
        self._uart.init(9600)
        self._input_callback = input_callback

    async def watch(self, scheduler):
        import utime
        pkt = bytearray(10)
        pkt_len = 0
        new = bytearray(10)
        while True:
            if len(self._sendq) and utime.ticks_diff(utime.ticks_ms(), self._next_send) > 0:
                data = self._sendq.popleft()
                print("writing:", data)
                self._uart.write(data)
                self._next_send = utime.ticks_add(utime.ticks_ms(), 800)
            new_len = self._uart.readinto(new)
            if new_len is None:
                await scheduler.sleep_ms(100)
                continue
            for byte in new[:new_len]:
                if pkt_len == 0 and byte != 0xaa:
                    continue
                pkt[pkt_len] = byte
                pkt_len += 1
                if pkt_len == 10:
                    if pkt[9] == 0xab:
                        p_obj = Packet.from_bytes(pkt[1:-1])
                        try:
                            try:
                                self._input_callback(p_obj)
                            except:
                                pass
                        except Exception as e:
                            print("Invalid SDS011 packet:", pkt, e)
                    pkt_len = 0

    def write_packet(self, packet):
        data = b"\xaa" + packet.bytes + b"\xab"
        self._sendq.append(data)

    def write_command(self, data=[], cmd=0xb4, addr=b"\xff\xff"):
        return self.write_packet(Packet(cmd, bytes(data) + (b"\x00" * (13 - len(data))), addr))

    def set_active_reporting(self, enabled):
        return self.write_command([0x02, 0x01, 0x00 if enabled else 0x01])

    def use_push_mode(self):
        return self.set_active_reporting(True)

    def use_poll_mode(self):
        return self.set_active_reporting(False)

    def query_data(self):
        return self.write_command([0x04])

    def sleep(self):
        return self.write_command([0x06, 0x01, 0x00])

    def wake(self):
        return self.write_command([0x06, 0x01, 0x01])

    def set_sleep_rhythm(self, sleep_for_minutes):
        assert isinstance(sleep_for_minutes, int)
        if sleep_for_minutes < 0 or sleep_for_minutes > 30:
            raise ValueError("sleep time has to be between 0 and 30 minutes")
        return self.write_command([0x08, 0x01, sleep_for_minutes])



class AdaptiveCycle:
    MODE_OFF = 0
    MODE_INTERVAL = 1
    MODE_CONTINUOUS = 2

    PHASE_SLEEP = 0
    PHASE_VENT = 1
    PHASE_MEASURE = 2

    PHASES = ["SLEEP", "VENT", "MEASURE"]

    def __init__(self, sds, interval_minutes=20):
        self._sds = sds
        self._phase = None
        self.interval_minutes = interval_minutes
        self.mode = self.MODE_OFF

    @property
    def interval_minutes(self):
        return self._minutes

    @interval_minutes.setter
    def interval_minutes(self, minutes):
        minutes = int(minutes)
        if minutes < 0:
            raise ValueError("minutes has to be a positive integer")
        self._minutes = minutes

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, mode):
        if mode == self.MODE_OFF:
            self.phase = self.PHASE_SLEEP
            self._countdown = None
        elif mode == self.MODE_INTERVAL:
            self.phase = self.PHASE_VENT
            self._countdown = 30
        elif mode == self.MODE_CONTINUOUS:
            self.phase = self.PHASE_VENT
            self._countdown = 20
        else:
            raise ValueError("invalid mode value:", mode)
        self._mode = mode

    @property
    def phase(self):
        return self._phase

    @phase.setter
    def phase(self, phase):
        if self._phase == phase:
            return
        if phase == self.PHASE_SLEEP:
            self._sds.use_poll_mode()
            self._sds.sleep()
        elif phase == self.PHASE_VENT:
            self._sds.wake()
            self._sds.use_poll_mode()
        elif phase == self.PHASE_MEASURE:
            self._sds.wake()
            self._sds.use_push_mode()
        else:
            raise ValueError("invalid phase value:", phase)
        print("SDS011 phase changed: {0} -> {1}".format(
            "[NONE]" if self._phase is None else self.PHASES[self._phase], self.PHASES[phase]))
        self._phase = phase

    async def watch(self, scheduler):
        while True:
            await scheduler.sleep(1)
            if self._countdown is not None:
                self._countdown -= 1
                if self._countdown <= 0:
                    if self.phase == self.PHASE_SLEEP:
                        self.phase = self.PHASE_VENT
                        self._countdown = 30
                    elif self.phase == self.PHASE_VENT:
                        self.phase = self.PHASE_MEASURE
                        self._countdown = 10 if self.mode == self.MODE_INTERVAL else None
                    elif self.phase == self.PHASE_MEASURE:
                        self.phase = self.PHASE_SLEEP
                        self._countdown = (60 * self.interval_minutes) - 40


# p = Packet()
# p.command = 0xb4
# p.data = b"\x12\x34\x56\x78\x9a\xbc\xde"
# print(p.checksum)
#
# p = Packet.from_bytes(b"\xc5\x02\x00\x00\x00\xa1\x60\x04")
# print(p.checksum)
