# MonitorAmbiental - esquema de mòduls

Pico (sensors + LoRa) → LoRa → RPi3 (receptor + base de dades + web).
Vegeu també `esquema_moduls.svg` (versió visual).
Els fitxers de la Pico són a `PICO/`, els de la RPi3 a `RPi3/`; `lora.py` i `protocol.py` hi són als dos llocs (idèntics).

## Fitxers comuns a la Pico i a la RPi3

| Fitxer | Nota |
|---|---|
| `lora.py` | Llibreria LoRa (port de l'Arduino LoRa). És el mateix fitxer als dos costats: detecta MicroPython i tria internament el *backend* (`_PicoBackend` o `_PiBackend`). |
| `protocol.py` | Radio (freqüència, SF, BW, CR...), format dels missatges i límits de configuració. **Ha de ser idèntic als dos costats** (p. ex. `FACTOR_EXPANSIO`). |

## Pico (MicroPython)

```
main.py ──┬─ lora.py          (llibreria)
          ├─ protocol.py
          └─ MQ135_DHT11.py ──┬─ MQ135.py (llibreria, classe MQ135)
                              └─ dht      (llibreria MicroPython, classe DHT11)
```

| Mòdul | Contingut | Paràmetres |
|---|---|---|
| `main.py` | 11 funcions, cap classe | Pins LoRa i LED, `FITXER_CONFIG`, `CONFIG_DEFECTE`, `DEPURACIO`, `ESPERA_ARRENCADA_MS`, `INTENTS_LORA` |
| `MQ135_DHT11.py` | 3 funcions (`llegir_brut`, `calcula_ppm`, `llegir_dht11_mostra`) | GP26, GP27, divisor, RLOAD, RZERO |
| `MQ135.py` | classe `MQ135` | `pin, rzero, rload, vcc, adc_vref, divider_top, divider_bottom` |
| `lora.py` | classe `LoRa` | `LoRa(reset, dio0, spi_id, sck, mosi, miso, cs)` |

- Classes pròpies: **cap** (només s'usen `LoRa`, `MQ135` i `DHT11`).
- Fils: **cap**. Un sol bucle a `main.py` que crida `lora.poll()`; el callback de recepció s'executa dins d'aquest bucle.
- Fitxers que genera: `configuracio.csv` (`periode;mostres;interval;versio`).

## RPi3 (Python)

Dos serveis systemd independents que només es comuniquen a través de la BD:

```
SERVEI 1  monitor-receptor        SERVEI 2  monitor-web
lora_receptor.py                  web.py (Flask)
  ├─ lora.py        (llibreria)     ├─ base_dades.py
  ├─ protocol.py                    ├─ protocol.py
  ├─ configuracio.py                ├─ configuracio.py
  └─ base_dades.py                  └─ plantilles_web/ + recursos/
          └────────→  dades/sensors.db (SQLite, WAL)  ←────────┘
```

Compartits entre els dos serveis: `protocol.py` (límits i validació), `base_dades.py` i `configuracio.py`.
Només el servei 1 usa `lora.py` i toca la ràdio.

| Mòdul | Contingut | Paràmetres |
|---|---|---|
| `configuracio.py` | només constants | Ruta BD, pins LoRa (`PIN_LORA_RESET`, `PIN_LORA_DIO0`, `SPI_BUS`, `SPI_DISPOSITIU`), `PIN_LED`, host i port web (5002) |
| `base_dades.py` | 11 funcions | Esquema, desar i llegir lectures i configuració, agrupacions |
| `lora_receptor.py` | 8 funcions | Cua, LED, SIGINT/SIGTERM |
| `web.py` | classe `ErrorPeticio` + rutes Flask | Pàgines `/`, `/historic`, `/configuracio`; API `/api/...` |
| `exporta_copia.py` | eina independent | Còpia consistent de la BD |

- Classes pròpies: **una** (`ErrorPeticio`, a `web.py`).

## Fils (threading)

| Lloc | Fils |
|---|---|
| Pico | Un sol fil |
| Receptor (RPi3) | Fil principal + fil de la ràdio dins `lora.py` (daemon, vigila DIO0). El callback `en_rebre` només deixa la trama a una `queue.Queue`; el fil principal la desa a la BD i respon a la Pico. |
| Web (RPi3) | Flask amb `threaded=True`: un fil per petició, cada una amb la seva connexió a la BD. |

`lora.py` és el mateix fitxer als dos costats, però a la Pico no crea cap fil (no hi ha `threading`): fa servir `_PicoBackend` i el bucle ha de cridar `poll()`. A la RPi3 `_PiBackend` crea el fil i tots els mètodes de `LoRa` es protegeixen amb un `RLock`.

## Flux d'un cicle

1. Pico: pren N mostres (separades per `interval`) i en fa la mitjana.
2. Pico → RPi3: missatge `D;ppm;brut;temp;hum;versio`.
3. Receptor: desa la lectura (hora UTC posada per la RPi3, RSSI, SNR) i respon.
4. RPi3 → Pico: `R;seq` (confirmació) o `R;seq;periode;mostres;interval;versio` si hi ha configuració pendent.
5. Pico: aplica la configuració nova i la desa a `configuracio.csv`.
