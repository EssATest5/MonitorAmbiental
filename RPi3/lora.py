"""
lora.py - Port a Python de la llibreria Arduino LoRa (Sandeep Mistry, v0.7.0)
per a transceptors Semtech SX1276/77/78/79 (p. ex. Dragino LoRa Shield v1.4).

Funciona amb el MATEIX fitxer a:
  * Raspberry Pi 3 (Python 3, paquets spidev + RPi.GPIO)
  * Raspberry Pi Pico (MicroPython, mòdul machine)

El port conserva la lògica de registres de LoRa.cpp (mateixos valors per
defecte, mateixa seqüència d'operacions), de manera que és compatible amb els
Arduinos que ja tens funcionant.

Llicència original: MIT, (c) Sandeep Mistry. Aquest port: MIT.

Diferències respecte a la versió Arduino
----------------------------------------
* Noms en snake_case (begin_packet, parse_packet...). També estan disponibles
  els noms originals en camelCase (beginPacket, parsePacket...).
* write() accepta int (1 byte), str, bytes, bytearray o llista.
* print()/println() com a Print d'Arduino. read_all() llegeix tot el paquet.
* Pi 3: onReceive/onTxDone es criden automàticament des d'un fil (thread).
* Pico: les interrupcions només marquen un senyal; cal cridar lora.poll()
  al bucle principal perquè s'executin els callbacks (a la Pi 3 poll() no fa
  res, així el mateix codi serveix per a les dues plaques).
"""

import sys
import time

MICROPYTHON = sys.implementation.name == "micropython"

# ---------------------------------------------------------------- registres
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_OCP = 0x0B
REG_LNA = 0x0C
REG_FIFO_ADDR_PTR = 0x0D
REG_FIFO_TX_BASE_ADDR = 0x0E
REG_FIFO_RX_BASE_ADDR = 0x0F
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_SNR_VALUE = 0x19
REG_PKT_RSSI_VALUE = 0x1A
REG_MODEM_CONFIG_1 = 0x1D
REG_MODEM_CONFIG_2 = 0x1E
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_PAYLOAD_LENGTH = 0x22
REG_MODEM_CONFIG_3 = 0x26
REG_FREQ_ERROR_MSB = 0x28
REG_FREQ_ERROR_MID = 0x29
REG_FREQ_ERROR_LSB = 0x2A
REG_RSSI_WIDEBAND = 0x2C
REG_DETECTION_OPTIMIZE = 0x31
REG_INVERTIQ = 0x33
REG_DETECTION_THRESHOLD = 0x37
REG_SYNC_WORD = 0x39
REG_INVERTIQ2 = 0x3B
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42
REG_PA_DAC = 0x4D

# modes
MODE_LONG_RANGE_MODE = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX = 0x03
MODE_RX_CONTINUOUS = 0x05
MODE_RX_SINGLE = 0x06

# PA config
PA_BOOST = 0x80
PA_OUTPUT_RFO_PIN = 0
PA_OUTPUT_PA_BOOST_PIN = 1

# IRQ masks
IRQ_TX_DONE_MASK = 0x08
IRQ_PAYLOAD_CRC_ERROR_MASK = 0x20
IRQ_RX_DONE_MASK = 0x40

MAX_PKT_LENGTH = 255
_TX_TIMEOUT_MS = 30000  # seguretat: l'original esperava indefinidament

# --------------------------------------------- utilitats dependents de plataforma
if MICROPYTHON:
    _DEF_RESET, _DEF_DIO0 = 20, 21  # GP20, GP21

    def sleep_ms(ms):
        time.sleep_ms(ms)

    def millis():
        return time.ticks_ms()

    def ticks_diff(a, b):
        """a - b en ms, correcte encara que el comptador faci la volta."""
        return time.ticks_diff(a, b)

    class _NoLock:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _new_lock():
        return _NoLock()

else:
    import threading

    _DEF_RESET, _DEF_DIO0 = 25, 24  # GPIO25, GPIO24 (numeració BCM)
    _T0 = time.monotonic()

    def sleep_ms(ms):
        time.sleep(ms / 1000.0)

    def millis():
        return int((time.monotonic() - _T0) * 1000)

    def ticks_diff(a, b):
        return a - b

    def _new_lock():
        return threading.RLock()


def decode(data):
    """bytes -> str (UTF-8); si no és text vàlid retorna repr(bytes)."""
    try:
        return data.decode()
    except Exception:
        return repr(data)


def _locked(fn):
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)

    return wrapper


def _to_bytes(data):
    if isinstance(data, int):
        return bytes((data & 0xFF,))
    if isinstance(data, str):
        return data.encode()
    return bytes(data)


# ---------------------------------------------------------------- backends
class _PiBackend:
    """Raspberry Pi (Linux): spidev + RPi.GPIO. CS per hardware (CE0/CE1)."""

    def __init__(self, reset, dio0, speed, spi_bus=0, spi_device=0):
        self.reset = reset
        self.dio0 = dio0
        self.speed = speed
        self.bus = spi_bus
        self.device = spi_device
        self.spi = None
        self.GPIO = None
        self._irq_on = False

    def open(self):
        if self.spi is not None:
            return
        import spidev
        import RPi.GPIO as GPIO

        self.GPIO = GPIO
        GPIO.setwarnings(False)
        if GPIO.getmode() is None:
            GPIO.setmode(GPIO.BCM)
        elif GPIO.getmode() != GPIO.BCM:
            raise RuntimeError("RPi.GPIO ja està en mode BOARD; cal mode BCM")
        if self.reset is not None:
            GPIO.setup(self.reset, GPIO.OUT, initial=GPIO.HIGH)
        if self.dio0 is not None:
            GPIO.setup(self.dio0, GPIO.IN)
        self.spi = spidev.SpiDev()
        self.spi.open(self.bus, self.device)
        self.spi.max_speed_hz = self.speed
        self.spi.mode = 0

    def hw_reset(self):
        if self.reset is None:
            return
        self.GPIO.output(self.reset, self.GPIO.LOW)
        sleep_ms(10)
        self.GPIO.output(self.reset, self.GPIO.HIGH)
        sleep_ms(10)

    def transfer(self, address, value):
        return self.spi.xfer2([address, value])[1]

    def attach_irq(self, handler):
        if self._irq_on or self.dio0 is None:
            return
        try:
            self.GPIO.add_event_detect(self.dio0, self.GPIO.RISING, callback=handler)
        except RuntimeError:
            # RPi.GPIO sense detecció de flancs (p. ex. Raspberry Pi OS Bookworm):
            # vigilem DIO0 des d'un fil, amb sondeig cada ~1 ms.
            self._start_polling(handler)
        self._irq_on = True

    def _start_polling(self, handler):
        import threading

        self._stop = threading.Event()
        pin, GPIO, stop = self.dio0, self.GPIO, self._stop

        def run():
            last = GPIO.input(pin)
            while not stop.is_set():
                cur = GPIO.input(pin)
                if cur and not last:
                    handler(pin)
                last = cur
                time.sleep(0.001)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def detach_irq(self):
        if self._irq_on:
            if getattr(self, "_thread", None) is not None:
                self._stop.set()
                self._thread.join()
                self._thread = None
            else:
                self.GPIO.remove_event_detect(self.dio0)
            self._irq_on = False

    def close(self):
        self.detach_irq()
        if self.spi is not None:
            self.spi.close()
            self.spi = None
        pins = [p for p in (self.reset, self.dio0) if p is not None]
        if pins and self.GPIO is not None:
            self.GPIO.cleanup(pins)


class _PicoBackend:
    """Raspberry Pi Pico (MicroPython): machine.SPI + CS per programari."""

    def __init__(self, reset, dio0, speed, spi_id=0, sck=18, mosi=19, miso=16, cs=17):
        self.reset = reset
        self.dio0 = dio0
        self.speed = speed
        self.spi_id = spi_id
        self.sck, self.mosi, self.miso, self.cs = sck, mosi, miso, cs
        self.spi = None
        self._irq_on = False

    def open(self):
        if self.spi is not None:
            return
        from machine import Pin, SPI

        self._Pin = Pin
        self.cs_pin = Pin(self.cs, Pin.OUT, value=1)
        self.reset_pin = Pin(self.reset, Pin.OUT, value=1) if self.reset is not None else None
        self.dio0_pin = Pin(self.dio0, Pin.IN) if self.dio0 is not None else None
        self.spi = SPI(
            self.spi_id,
            baudrate=self.speed,
            polarity=0,
            phase=0,
            bits=8,
            firstbit=SPI.MSB,
            sck=Pin(self.sck),
            mosi=Pin(self.mosi),
            miso=Pin(self.miso),
        )
        self._out = bytearray(2)
        self._in = bytearray(2)

    def hw_reset(self):
        if self.reset_pin is None:
            return
        self.reset_pin.value(0)
        sleep_ms(10)
        self.reset_pin.value(1)
        sleep_ms(10)

    def transfer(self, address, value):
        self._out[0] = address
        self._out[1] = value
        self.cs_pin.value(0)
        self.spi.write_readinto(self._out, self._in)
        self.cs_pin.value(1)
        return self._in[1]

    def attach_irq(self, handler):
        if self._irq_on or self.dio0_pin is None:
            return
        self.dio0_pin.irq(trigger=self._Pin.IRQ_RISING, handler=handler)
        self._irq_on = True

    def detach_irq(self):
        if self._irq_on:
            self.dio0_pin.irq(handler=None)
            self._irq_on = False

    def close(self):
        self.detach_irq()
        if self.spi is not None:
            self.spi.deinit()
            self.spi = None


# ------------------------------------------------------------------ classe
class LoRa:
    """
    Raspberry Pi 3:
        LoRa(spi_speed=1000000, reset=25, dio0=24, spi_bus=0, spi_device=0)
    Raspberry Pi Pico:
        LoRa(spi_speed=1000000, reset=20, dio0=21,
             spi_id=0, sck=18, mosi=19, miso=16, cs=17)
    Passa reset=None (o -1) si no tens el pin RESET connectat.
    """

    def __init__(self, spi_speed=1000000, reset=_DEF_RESET, dio0=_DEF_DIO0, **spi_pins):
        if reset == -1:
            reset = None
        if dio0 == -1:
            dio0 = None
        backend = _PicoBackend if MICROPYTHON else _PiBackend
        self._backend = backend(reset, dio0, spi_speed, **spi_pins)
        self._lock = _new_lock()
        self._frequency = 0
        self._packet_index = 0
        self._implicit_header_mode = 0
        self._on_receive = None
        self._on_tx_done = None
        self._irq_flag = False
        self._irq_cb = self._irq_entry

    # --------------------------------------------------- accés a registres
    def _read(self, address):
        return self._backend.transfer(address & 0x7F, 0x00)

    def _write(self, address, value):
        self._backend.transfer(address | 0x80, value & 0xFF)

    def read_register(self, address):
        return self._read(address)

    def write_register(self, address, value):
        self._write(address, value)

    # --------------------------------------------------------- inici / final
    def begin(self, frequency):
        """Inicialitza el mòdul. Retorna True si s'ha detectat l'SX127x."""
        self._backend.open()
        self._backend.hw_reset()

        if self._read(REG_VERSION) != 0x12:
            return False

        self.sleep()
        self.set_frequency(frequency)

        self._write(REG_FIFO_TX_BASE_ADDR, 0)
        self._write(REG_FIFO_RX_BASE_ADDR, 0)

        self._write(REG_LNA, self._read(REG_LNA) | 0x03)  # LNA boost
        self._write(REG_MODEM_CONFIG_3, 0x04)  # AGC automàtic
        self.set_tx_power(17)
        self.idle()
        return True

    def end(self):
        self.sleep()
        self._backend.close()

    # ------------------------------------------------------------ transmissió
    def begin_packet(self, implicit_header=False):
        if self._is_transmitting():
            return 0
        self.idle()
        if implicit_header:
            self._implicit_header()
        else:
            self._explicit_header()
        self._write(REG_FIFO_ADDR_PTR, 0)
        self._write(REG_PAYLOAD_LENGTH, 0)
        return 1

    def end_packet(self, asynchronous=False):
        if asynchronous and self._on_tx_done:
            self._write(REG_DIO_MAPPING_1, 0x40)  # DIO0 => TXDONE

        self._write(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_TX)

        if not asynchronous:
            waited = 0
            while (self._read(REG_IRQ_FLAGS) & IRQ_TX_DONE_MASK) == 0:
                sleep_ms(1)
                waited += 1
                if waited > _TX_TIMEOUT_MS:
                    return 0
            self._write(REG_IRQ_FLAGS, IRQ_TX_DONE_MASK)
        return 1

    def _is_transmitting(self):
        if (self._read(REG_OP_MODE) & MODE_TX) == MODE_TX:
            return True
        if self._read(REG_IRQ_FLAGS) & IRQ_TX_DONE_MASK:
            self._write(REG_IRQ_FLAGS, IRQ_TX_DONE_MASK)
        return False

    def write(self, data):
        """Afegeix dades al paquet (int = 1 byte, str, bytes, bytearray, llista)."""
        data = _to_bytes(data)
        size = len(data)
        current = self._read(REG_PAYLOAD_LENGTH)
        if current + size > MAX_PKT_LENGTH:
            size = MAX_PKT_LENGTH - current
        for i in range(size):
            self._write(REG_FIFO, data[i])
        self._write(REG_PAYLOAD_LENGTH, current + size)
        return size

    def print(self, *values):
        return self.write("".join([str(v) for v in values]))

    def println(self, *values):
        return self.write("".join([str(v) for v in values]) + "\r\n")

    # --------------------------------------------------------------- recepció
    def parse_packet(self, size=0):
        """Retorna la longitud del paquet rebut, o 0 si no n'hi ha cap."""
        packet_length = 0
        irq_flags = self._read(REG_IRQ_FLAGS)

        if size > 0:
            self._implicit_header()
            self._write(REG_PAYLOAD_LENGTH, size & 0xFF)
        else:
            self._explicit_header()

        self._write(REG_IRQ_FLAGS, irq_flags)  # esborra IRQs

        if (irq_flags & IRQ_RX_DONE_MASK) and (irq_flags & IRQ_PAYLOAD_CRC_ERROR_MASK) == 0:
            self._packet_index = 0
            if self._implicit_header_mode:
                packet_length = self._read(REG_PAYLOAD_LENGTH)
            else:
                packet_length = self._read(REG_RX_NB_BYTES)
            self._write(REG_FIFO_ADDR_PTR, self._read(REG_FIFO_RX_CURRENT_ADDR))
            self.idle()
        elif self._read(REG_OP_MODE) != (MODE_LONG_RANGE_MODE | MODE_RX_SINGLE):
            self._write(REG_FIFO_ADDR_PTR, 0)
            self._write(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_RX_SINGLE)

        return packet_length

    def packet_rssi(self):
        return self._read(REG_PKT_RSSI_VALUE) - (164 if self._frequency < 868000000 else 157)

    def packet_snr(self):
        v = self._read(REG_PKT_SNR_VALUE)
        if v > 127:
            v -= 256
        return v * 0.25

    def packet_frequency_error(self):
        err = self._read(REG_FREQ_ERROR_MSB) & 0x07
        err <<= 8
        err += self._read(REG_FREQ_ERROR_MID)
        err <<= 8
        err += self._read(REG_FREQ_ERROR_LSB)
        if self._read(REG_FREQ_ERROR_MSB) & 0x08:  # bit de signe
            err -= 524288
        f_xtal = 32000000.0
        f_error = ((err * (1 << 24)) / f_xtal) * (self._get_signal_bandwidth() / 500000.0)
        return int(f_error)

    def available(self):
        return self._read(REG_RX_NB_BYTES) - self._packet_index

    def read(self):
        """Llegeix 1 byte del paquet (int) o -1 si no n'hi ha més."""
        if not self.available():
            return -1
        self._packet_index += 1
        return self._read(REG_FIFO)

    def read_all(self):
        """Llegeix tots els bytes pendents del paquet com a bytes."""
        out = bytearray()
        while self.available() > 0:
            out.append(self._read(REG_FIFO))
            self._packet_index += 1
        return bytes(out)

    def peek(self):
        if not self.available():
            return -1
        current = self._read(REG_FIFO_ADDR_PTR)
        b = self._read(REG_FIFO)
        self._write(REG_FIFO_ADDR_PTR, current)
        return b

    def flush(self):
        pass

    # ----------------------------------------------------------- interrupcions
    def on_receive(self, callback):
        """callback(packet_length). Cal anar cridant poll() a la Pico."""
        self._on_receive = callback
        self._update_irq()

    def on_tx_done(self, callback):
        """callback() quan acaba una transmissió asíncrona (end_packet(True))."""
        self._on_tx_done = callback
        self._update_irq()

    def _update_irq(self):
        # (a l'original, treure un callback desactivava la IRQ dels dos)
        if self._on_receive or self._on_tx_done:
            self._backend.attach_irq(self._irq_cb)
        else:
            self._backend.detach_irq()

    def _irq_entry(self, *_):
        if MICROPYTHON:
            self._irq_flag = True  # a la IRQ només marquem; poll() ho processa
        else:
            self._handle_dio0_rise()  # fil de RPi.GPIO

    def poll(self):
        """Processa events pendents. Imprescindible a la Pico; no-op a la Pi 3."""
        if self._irq_flag:
            self._irq_flag = False
            self._handle_dio0_rise()

    def _handle_dio0_rise(self):
        irq_flags = self._read(REG_IRQ_FLAGS)
        self._write(REG_IRQ_FLAGS, irq_flags)

        if (irq_flags & IRQ_PAYLOAD_CRC_ERROR_MASK) == 0:
            if irq_flags & IRQ_RX_DONE_MASK:
                self._packet_index = 0
                if self._implicit_header_mode:
                    length = self._read(REG_PAYLOAD_LENGTH)
                else:
                    length = self._read(REG_RX_NB_BYTES)
                self._write(REG_FIFO_ADDR_PTR, self._read(REG_FIFO_RX_CURRENT_ADDR))
                if self._on_receive:
                    self._on_receive(length)
                self._write(REG_FIFO_ADDR_PTR, 0)
            elif irq_flags & IRQ_TX_DONE_MASK:
                if self._on_tx_done:
                    self._on_tx_done()

    def receive(self, size=0):
        """Mode recepció contínua (per a on_receive)."""
        self._write(REG_DIO_MAPPING_1, 0x00)  # DIO0 => RXDONE
        if size > 0:
            self._implicit_header()
            self._write(REG_PAYLOAD_LENGTH, size & 0xFF)
        else:
            self._explicit_header()
        self._write(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_RX_CONTINUOUS)

    # ------------------------------------------------------------ configuració
    def idle(self):
        self._write(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_STDBY)

    def sleep(self):
        self._write(REG_OP_MODE, MODE_LONG_RANGE_MODE | MODE_SLEEP)

    def set_tx_power(self, level, output_pin=PA_OUTPUT_PA_BOOST_PIN):
        if output_pin == PA_OUTPUT_RFO_PIN:
            level = max(0, min(14, level))
            self._write(REG_PA_CONFIG, 0x70 | level)
        else:
            if level > 17:
                if level > 20:
                    level = 20
                level -= 3  # 18..20 -> 15..17
                self._write(REG_PA_DAC, 0x87)  # +20 dBm
                self.set_ocp(140)
            else:
                if level < 2:
                    level = 2
                self._write(REG_PA_DAC, 0x84)
                self.set_ocp(100)
            self._write(REG_PA_CONFIG, PA_BOOST | (level - 2))

    def set_frequency(self, frequency):
        frequency = int(frequency)
        self._frequency = frequency
        frf = (frequency << 19) // 32000000
        self._write(REG_FRF_MSB, (frf >> 16) & 0xFF)
        self._write(REG_FRF_MID, (frf >> 8) & 0xFF)
        self._write(REG_FRF_LSB, frf & 0xFF)

    def _get_spreading_factor(self):
        return self._read(REG_MODEM_CONFIG_2) >> 4

    def set_spreading_factor(self, sf):
        sf = max(6, min(12, int(sf)))
        if sf == 6:
            self._write(REG_DETECTION_OPTIMIZE, 0xC5)
            self._write(REG_DETECTION_THRESHOLD, 0x0C)
        else:
            self._write(REG_DETECTION_OPTIMIZE, 0xC3)
            self._write(REG_DETECTION_THRESHOLD, 0x0A)
        self._write(REG_MODEM_CONFIG_2, (self._read(REG_MODEM_CONFIG_2) & 0x0F) | ((sf << 4) & 0xF0))
        self._set_ldo_flag()

    def _get_signal_bandwidth(self):
        bw = self._read(REG_MODEM_CONFIG_1) >> 4
        table = (7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000, 500000)
        return table[bw] if bw < len(table) else -1

    def set_signal_bandwidth(self, sbw):
        limits = (7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000)
        bw = 9
        for i in range(len(limits)):
            if sbw <= limits[i]:
                bw = i
                break
        self._write(REG_MODEM_CONFIG_1, (self._read(REG_MODEM_CONFIG_1) & 0x0F) | (bw << 4))
        self._set_ldo_flag()

    def _set_ldo_flag(self):
        # Divisions enteres, idèntic a la llibreria Arduino (així el bit LDO
        # coincideix amb el dels Arduinos, que és el que importa per interoperar).
        symbol_duration = 1000 // (self._get_signal_bandwidth() // (1 << self._get_spreading_factor()))
        ldo_on = symbol_duration > 16
        config3 = self._read(REG_MODEM_CONFIG_3)
        config3 = (config3 | 0x08) if ldo_on else (config3 & ~0x08)
        self._write(REG_MODEM_CONFIG_3, config3)

    def set_coding_rate4(self, denominator):
        denominator = max(5, min(8, int(denominator)))
        cr = denominator - 4
        self._write(REG_MODEM_CONFIG_1, (self._read(REG_MODEM_CONFIG_1) & 0xF1) | (cr << 1))

    def set_preamble_length(self, length):
        self._write(REG_PREAMBLE_MSB, (length >> 8) & 0xFF)
        self._write(REG_PREAMBLE_LSB, length & 0xFF)

    def set_sync_word(self, sw):
        self._write(REG_SYNC_WORD, sw)

    def enable_crc(self):
        self._write(REG_MODEM_CONFIG_2, self._read(REG_MODEM_CONFIG_2) | 0x04)

    def disable_crc(self):
        self._write(REG_MODEM_CONFIG_2, self._read(REG_MODEM_CONFIG_2) & 0xFB)

    def enable_invert_iq(self):
        self._write(REG_INVERTIQ, 0x66)
        self._write(REG_INVERTIQ2, 0x19)

    def disable_invert_iq(self):
        self._write(REG_INVERTIQ, 0x27)
        self._write(REG_INVERTIQ2, 0x1D)

    def set_ocp(self, mA):
        ocp_trim = 27
        if mA <= 120:
            ocp_trim = int((mA - 45) / 5)
        elif mA <= 240:
            ocp_trim = int((mA + 30) / 10)
        self._write(REG_OCP, 0x20 | (0x1F & ocp_trim))

    def random(self):
        return self._read(REG_RSSI_WIDEBAND)

    def dump_registers(self, out=None):
        for i in range(128):
            line = "0x%X: 0x%X" % (i, self._read(i))
            if out is None:
                print(line)
            else:
                out(line)

    def _explicit_header(self):
        self._implicit_header_mode = 0
        self._write(REG_MODEM_CONFIG_1, self._read(REG_MODEM_CONFIG_1) & 0xFE)

    def _implicit_header(self):
        self._implicit_header_mode = 1
        self._write(REG_MODEM_CONFIG_1, self._read(REG_MODEM_CONFIG_1) | 0x01)


# Tots els mètodes públics agafen el bloqueig (thread-safe a la Pi 3).
for _name in (
    "begin", "end", "begin_packet", "end_packet", "write", "print", "println",
    "parse_packet", "packet_rssi", "packet_snr", "packet_frequency_error",
    "available", "read", "read_all", "peek", "on_receive", "on_tx_done",
    "receive", "idle", "sleep", "set_tx_power", "set_frequency",
    "set_spreading_factor", "set_signal_bandwidth", "set_coding_rate4",
    "set_preamble_length", "set_sync_word", "enable_crc", "disable_crc",
    "enable_invert_iq", "disable_invert_iq", "set_ocp", "random",
    "dump_registers", "read_register", "write_register", "_handle_dio0_rise",
):
    setattr(LoRa, _name, _locked(getattr(LoRa, _name)))

# Noms originals d'Arduino (camelCase)
_ALIASES = {
    "beginPacket": "begin_packet", "endPacket": "end_packet",
    "parsePacket": "parse_packet", "packetRssi": "packet_rssi",
    "packetSnr": "packet_snr", "packetFrequencyError": "packet_frequency_error",
    "onReceive": "on_receive", "onTxDone": "on_tx_done",
    "setTxPower": "set_tx_power", "setFrequency": "set_frequency",
    "setSpreadingFactor": "set_spreading_factor",
    "setSignalBandwidth": "set_signal_bandwidth",
    "setCodingRate4": "set_coding_rate4", "setPreambleLength": "set_preamble_length",
    "setSyncWord": "set_sync_word", "enableCrc": "enable_crc",
    "disableCrc": "disable_crc", "enableInvertIQ": "enable_invert_iq",
    "disableInvertIQ": "disable_invert_iq", "setOCP": "set_ocp",
    "dumpRegisters": "dump_registers",
}
for _camel, _snake in _ALIASES.items():
    setattr(LoRa, _camel, getattr(LoRa, _snake))
