# LoRa (SX1276) per a Raspberry Pi 3 i Raspberry Pi Pico

Port a Python de la llibreria Arduino *LoRa* 0.7.0 (Sandeep Mistry) per al
Dragino LoRa Shield v1.4. **Un únic `lora.py`** serveix per a la Pi 3
(Python 3) i per a la Pico (MicroPython); els exemples són idèntics.

## Cablejat (el shield no s'endolla: cal connectar-lo amb cables)

| Shield Dragino (Arduino) | Pi 3 (BCM / pin físic) | Pico (GP / pin físic) |
|---|---|---|
| D13 SCK  | GPIO11 SCLK / 23 | GP18 / 24 |
| D12 MISO | GPIO9 MISO / 21  | GP16 / 21 |
| D11 MOSI | GPIO10 MOSI / 19 | GP19 / 25 |
| D10 NSS  | GPIO8 CE0 / 24   | GP17 / 22 |
| D9 RESET | GPIO25 / 22      | GP20 / 26 |
| D2 DIO0  | GPIO24 / 18      | GP21 / 27 |
| GND      | GND / 6          | GND / 23  |
| 3V3 (o 5V segons shield) | 3V3 / 1 | 3V3(OUT) / 36 |

Pi i Pico treballen a **3,3 V**: no hi connectis mai senyals de 5 V. Comprova a
la documentació de Dragino com s'ha d'alimentar el shield fora d'un Arduino.

Si canvies pins: `LoRa(reset=.., dio0=.., spi_bus=0, spi_device=0)` (Pi) o
`LoRa(reset=.., dio0=.., spi_id=0, sck=.., mosi=.., miso=.., cs=..)` (Pico).

## Raspberry Pi 3
```bash
sudo raspi-config        # Interface Options -> SPI -> Enable
sudo apt install python3-spidev python3-rpi.gpio
python3 test_connexio.py # ha de dir "SX127x detectat, versió = 0x12"
python3 receiver.py      # a l'altre extrem: sender.py
```

## Raspberry Pi Pico
1. Instal·la MicroPython (UF2) a la Pico.
2. Copia `lora.py` i els exemples que vulguis a la Pico (Thonny o `mpremote cp lora.py :`).
3. Executa `test_connexio.py`, després `receiver.py` / `sender.py`.

A la Pico, **crida `lora.poll()` al bucle principal** si uses `on_receive` /
`on_tx_done` (simple_node.py / simple_gateway.py ja ho fan). A la Pi 3 és un no-op.

## Compatibilitat amb els Arduinos
* Mateixa freqüència (`FREQUENCY`, als exemples 915E6 com als teus .ino; 868E6 si el mòdul és de 868 MHz).
* Paràmetres per defecte idèntics: SF7, BW125 kHz, CR 4/5, sync word 0x12, CRC desactivat.
  Si canvies SF/BW/CR/sync/CRC/preàmbul en un extrem, fes-ho igual a l'altre.
* `simple_node` / `simple_gateway` usen InvertIQ igual que els .ino.

## Si `begin()` retorna False
Versió llegida 0x00 o 0xFF = no hi ha comunicació SPI: revisa cablejat, que SPI
estigui activat (Pi) i que CS/RESET coincideixin. Prova `LoRa(spi_speed=500000)`.

## Referència ràpida
`begin, end, begin_packet, end_packet(asynchronous), write, print, println,
parse_packet, read, read_all, peek, available, packet_rssi, packet_snr,
packet_frequency_error, on_receive, on_tx_done, receive, idle, sleep,
set_tx_power, set_frequency, set_spreading_factor, set_signal_bandwidth,
set_coding_rate4, set_preamble_length, set_sync_word, enable/disable_crc,
enable/disable_invert_iq, set_ocp, random, dump_registers, read/write_register,
poll`. Els noms camelCase originals (`beginPacket`, `parsePacket`...) també funcionen.

## Exemples
test_connexio, sender, receiver, duplex, duplex_callback, receiver_callback,
sender_nonblocking, sender_nonblocking_callback, simple_node, simple_gateway,
set_spread (SF8) i set_sync_word (0xF3). Als dos extrems cal el mateix SF i
el mateix sync word perquè es rebin.
