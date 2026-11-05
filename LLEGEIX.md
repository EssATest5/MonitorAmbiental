# MonitorAmbiental

Monitor ambiental amb LoRa: una **Raspberry Pi Pico** (sensor de gas MQ-135 + DHT11) envia les lectures per
LoRa (868 MHz) a una **Raspberry Pi 3**, que les desa en una base de dades SQLite i les mostra en una web
(tauler, històric amb agrupació, CSV) des d'on també es configura la Pico (període, mostres, interval).

Esquema de mòduls, fils i flux: [`ESQUEMA.md`](ESQUEMA.md) i `esquema_moduls.svg`.

## Estructura

```
MonitorAmbiental/
├── PICO/            tot el que va a la Pico (es copia el contingut de la carpeta, sense proves/)
├── RPi3/            tot el que va a la RPi3 (es copia el contingut a /home/pi/MonitorAmbiental)
├── Llibreries/      llibreries originals, documentació i traduccions (només de referència)
├── eines_windows/   scripts per baixar i consultar la base de dades des d'un PC Windows
├── comprova_comuns.py   comprova que lora.py i protocol.py són idèntics a PICO/ i RPi3/
├── LLEGEIX.md, ESQUEMA.md, esquema_moduls.svg
```

- **`lora.py` i `protocol.py` són a PICO/ i a RPi3/** perquè cada carpeta es pugui copiar sencera a la seva placa.
  Han de ser **idèntics**: si en canvies un, copia'l a l'altra carpeta i executa `python3 comprova_comuns.py`.
- **`Llibreries/`** conté: `Sensor_Gas_MQ-135/` (llibreria Arduino original i les versions MicroPython de prova) i
  `Shield_LoRa/` (datasheet del shield, llibreria Arduino original, i la traducció a Python/MicroPython amb exemples).
  El `MQ135.py` de `PICO/` és el de `Llibreries/` ampliat (paràmetre `brut` i `llegir_brut()`).

## Instal·lació a la RPi3

1. Copia el contingut de `RPi3/` a `/home/pi/MonitorAmbiental` i activa l'SPI (`sudo raspi-config`).
2. `sudo apt install python3-flask python3-rpi.gpio python3-spidev`
3. Serveis:
   ```
   sudo cp serveis/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now monitor-receptor monitor-web
   ```
4. Web: `http://<ip de la RPi3>:5002` (sense contrasenya!).
5. Pins del shield LoRa a `configuracio.py`. La base de dades es crea sola a `dades/sensors.db`.

## Instal·lació a la Pico (MicroPython)

Copia a la Pico el contingut de `PICO/` (`main.py`, `lora.py`, `protocol.py`, `MQ135_DHT11.py`, `MQ135.py`);
la carpeta `proves/` no cal. Pins LoRa i LED a la capçalera de `main.py`; pins i calibratge dels sensors a
`MQ135_DHT11.py`. `DEPURACIO = True` només amb Thonny connectat.

## Ràdio

868 MHz, SF9, 125 kHz, CR 4/5, CRC activat, sync 0x12 (a `protocol.py`).

## Sensor de gas: valors de treball

- `RLOAD = 0.92` kΩ (mesurat) i `RZERO = 4.7` kΩ (`PICO/MQ135_DHT11.py`). **RZERO és una estimació de treball**, no una
  calibració: surt d'un registre de 24 h (4-5/11/26) suposant que l'aire valia 426,89 ppm.
- El **ppm és una estimació**; la dada més directa és `lectura_brut` (ADC), que sempre es guarda i permet recalcular-lo.
- El sensor té caigudes aleatòries de lectura (la Rs puja de cop a un 36 % de les mostres). Per això la Pico envia
  el valor **màxim** de l'ADC entre les mostres, no la mitjana: convé mantenir `mostres >= 5`.
- Correcció per temperatura i humitat: desactivada (no hi ha calibració per validar-la).
