"""
MQ135_v1.py - Adaptacio a MicroPython de la llibreria Arduino MQ135
Formula original: G. Krocker / Mad Frog Labs.

Pensat per Raspberry Pi Pico / Pico 2.
ADC: normalment GP26 (ADC0), amb divisor extern si el mòdul MQ-135
pot donar fins a 5 V a AOUT.

ATENCIO:
- rload ha de correspondre a la resistència de càrrega REAL del mòdul.
- divider_top i divider_bottom descriuen el divisor extern entre AOUT i ADC:
    AOUT -- divider_top --+-- ADC
                          |
                    divider_bottom
                          |
                         GND
- Els ppm són estimacions de la fórmula original, no una mesura selectiva
  ni certificada de CO2.
"""

from machine import ADC, Pin

PARA = 116.6020682
PARB = 2.769034857

CORA = 0.00035
CORB = 0.02718
CORC = 1.39538
CORD = 0.0018
CORE = -0.003333333
CORF = -0.001923077
CORG = 1.130128205

ATMOCO2 = 426.89


class MQ135:
    def __init__(
        self,
        pin=26,
        rzero=76.63,
        rload=10.0,
        vcc=5.0,
        adc_vref=3.3,
        divider_top=10000.0,
        divider_bottom=15000.0,
    ):
        """
        pin: pin ADC del Pico (GPIO numèric, per exemple 26).
        rzero: valor de calibratge en kOhm, com a la llibreria Arduino.
        rload: resistència de càrrega del mòdul en kOhm.
        vcc: alimentació del circuit sensor, habitualment 5.0 V.
        adc_vref: referència ADC del Pico, habitualment 3.3 V.
        divider_top/bottom: resistències del divisor extern en ohms.
          Per 10k entre AOUT i ADC, i 15k entre ADC i GND, usa 10000/15000.
          Per no fer servir divisor (només si AOUT és segur per al Pico),
          posa divider_top=0 i divider_bottom=1.
        """
        if rload <= 0 or vcc <= 0 or adc_vref <= 0:
            raise ValueError("rload, vcc i adc_vref han de ser positius")
        if divider_top < 0 or divider_bottom <= 0:
            raise ValueError("Valors del divisor no vàlids")

        self._pin = pin
        self._rzero = float(rzero)
        self._rload = float(rload)
        self._vcc = float(vcc)
        self._adc_vref = float(adc_vref)
        self._divider_top = float(divider_top)
        self._divider_bottom = float(divider_bottom)
        self._adc = ADC(Pin(pin))

    def _read_aout_voltage(self):
        raw = self._adc.read_u16()
        v_adc = raw * self._adc_vref / 65535.0
        # Recupera la tensió original d'AOUT abans del divisor extern.
        v_aout = v_adc * (
            (self._divider_top + self._divider_bottom)
            / self._divider_bottom
        )
        return v_aout

    def getCorrectionFactor(self, t, h):
        if t < 20:
            return CORA * t * t - CORB * t + CORC - (h - 33.0) * CORD
        return CORE * t + CORF * h + CORG

    def getResistance(self):
        vout = self._read_aout_voltage()
        # La fórmula Arduino equival a ((Vcc / Vout) - 1) * Rload.
        if vout <= 0.0:
            raise ValueError("AOUT és zero: no es pot calcular la resistència")
        if vout >= self._vcc:
            raise ValueError("AOUT >= Vcc: revisa el divisor i el cablejat")
        return ((self._vcc / vout) - 1.0) * self._rload

    def getCorrectedResistance(self, t, h):
        factor = self.getCorrectionFactor(t, h)
        if factor == 0:
            raise ValueError("El factor de correcció és zero")
        return self.getResistance() / factor

    def getPPM(self):
        ratio = self.getResistance() / self._rzero
        if ratio <= 0:
            raise ValueError("R/RZero ha de ser positiu")
        return PARA * (ratio ** (-PARB))

    def getCorrectedPPM(self, t, h):
        ratio = self.getCorrectedResistance(t, h) / self._rzero
        if ratio <= 0:
            raise ValueError("R corregida/RZero ha de ser positiu")
        return PARA * (ratio ** (-PARB))

    def getRZero(self):
        return self.getResistance() * ((ATMOCO2 / PARA) ** (1.0 / PARB))

    def getCorrectedRZero(self, t, h):
        return self.getCorrectedResistance(t, h) * (
            (ATMOCO2 / PARA) ** (1.0 / PARB)
        )
