"""
MQ135_v2.py - Adaptacio a MicroPython de la llibreria Arduino MQ135
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

AMPLIACIÓ (monitor ambiental): tots els mètodes de càlcul accepten, opcionalment,
el valor cru de l'ADC (paràmetre `brut`, 0-65535). Si no es dona, llegeixen l'ADC
com sempre. Així es pot calcular a partir d'un valor cru ja mesurat o promitjat.
"""

from machine import ADC, Pin

# Constants de la corba que relaciona la resistència del sensor amb els ppm.
PARA = 116.6020682
PARB = 2.769034857

# Coeficients del model de correcció per temperatura i humitat.
CORA = 0.00035
CORB = 0.02718
CORC = 1.39538
CORD = 0.0018
CORE = -0.003333333
CORF = -0.001923077
CORG = 1.130128205

# Concentració atmosfèrica de CO2 de referència per calcular RZero (ppm).
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
        Inicialització del sensor i configuració de l'ADC.

        pin: GPIO del Pico utilitzat com a entrada ADC. (GPIO numèric, per exemple 26)
        rzero: resistència de referència/calibratge, en kOhm. , com a la llibreria Arduino.
        rload: resistència de càrrega del mòdul, en kOhm.
        vcc: tensió d'alimentació del circuit sensor, habitualment 5.0 V.
        adc_vref: tensió de referència de l'ADC de la PICO, habitualment 3.3 V
        divider_top: resistència entre AOUT i ADC, en ohms.
        divider_bottom: resistència entre ADC i GND, en ohms.

        Exemple divisor:
          10 kOhm entre AOUT i ADC.
          15 kOhm entre ADC i GND.
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

    def llegir_brut(self):
        """Retorna una lectura crua de l'ADC (0-65535)."""

        return self._adc.read_u16()

    def _read_aout_voltage(self, brut=None):
        """
        Recupera la tensió original d'AOUT.
        Si es dona `brut` (valor cru de l'ADC) el fa servir; si no, llegeix l'ADC.
        """

        # Lectura ADC de MicroPython: valor entre 0 i 65535.
        raw = self._adc.read_u16() if brut is None else brut

        # Conversió de la lectura digital a tensió al pin ADC.
        v_adc = raw * self._adc_vref / 65535.0

        # Recuperació de la tensió AOUT abans del divisor extern.
        v_aout = v_adc * (
            (self._divider_top + self._divider_bottom)
            / self._divider_bottom
        )

        return v_aout

    def getCorrectionFactor(self, t, h):
        """
        Calcula el factor de correcció segons temperatura i humitat.

        t: temperatura ambient en graus Celsius.
        h: humitat relativa en percentatge (%).

        La resistència del MQ135 varia amb la temperatura i la humitat.
        Aquest factor permet compensar parcialment aquestes variacions.

        El model original utilitza dues expressions diferents:

        1) Temperatura inferior a 20 graus:
           - Utilitza una expressió quadràtica respecte a la temperatura.
           - També incorpora un terme de correcció segons la humitat.
           - CORA, CORB i CORC defineixen la part dependent de temperatura.
           - CORD defineix la influència de la humitat.

        2) Temperatura igual o superior a 20 graus:
           - Utilitza una expressió lineal respecte a la temperatura.
           - També incorpora la humitat relativa.
           - CORE, CORF i CORG són els coeficients d'aquesta expressió.

        El resultat és un factor multiplicador/divisor que s'utilitza
        posteriorment per corregir la resistència del sensor.

        NOTA: És un model empíric de la llibreria original i la seva
        precisió depèn de les condicions reals de funcionament.
        """

        if t < 20:
            # Tram de temperatura baixa: model quadràtic.
            return CORA * t * t - CORB * t + CORC - (h - 33.0) * CORD
        else:
            # Tram de temperatura alta: model lineal.
            return CORE * t + CORF * h + CORG

    def getResistance(self, brut=None):
        """
        Calcula la resistència del sensor en kOhm.

        Utilitza la tensió AOUT i la resistència de càrrega Rload.
        La fórmula correspon al divisor resistiu del circuit MQ135:
            Rs = ((Vcc / Vout) - 1) * Rload
        """

        vout = self._read_aout_voltage(brut)

        # Evitem divisions per zero i valors físicament no vàlids.
        if vout <= 0.0:
            raise ValueError("AOUT és zero: no es pot calcular la resistència")
        if vout >= self._vcc:
            raise ValueError("AOUT >= Vcc: revisa el divisor i el cablejat")

        return ((self._vcc / vout) - 1.0) * self._rload

    def getCorrectedResistance(self, t, h, brut=None):
        """
        Calcula la resistència corregida per temperatura i humitat.

        Primer calcula la resistència normal i després l'ajusta
        utilitzant el factor obtingut amb getCorrectionFactor().
        """

        factor = self.getCorrectionFactor(t, h)

        if factor == 0:
            raise ValueError("El factor de correcció és zero")

        return self.getResistance(brut) / factor

    def getPPM(self, brut=None):
        """
        Estima la concentració en ppm segons la resistència mesurada.

        Utilitza la relació entre la resistència actual i RZero.
        No aplica correcció de temperatura ni humitat.
        """

        ratio = self.getResistance(brut) / self._rzero

        if ratio <= 0:
            raise ValueError("R/RZero ha de ser positiu")

        return PARA * (ratio ** (-PARB))

    def getCorrectedPPM(self, t, h, brut=None):
        """
        Estima els ppm utilitzant la resistència corregida.

        A diferència de getPPM(), aplica abans la correcció
        de temperatura i humitat.
        """

        ratio = self.getCorrectedResistance(t, h, brut) / self._rzero

        if ratio <= 0:
            raise ValueError("R corregida/RZero ha de ser positiu")

        return PARA * (ratio ** (-PARB))

    def getRZero(self, brut=None):
        """
        Calcula el valor RZero a partir de la resistència actual.

        ATMOCO2 és la concentració de CO2 de referència utilitzada
        per la llibreria original.

        Aquest mètode és útil durant el calibratge del sensor.
        """

        return self.getResistance(brut) * ((ATMOCO2 / PARA) ** (1.0 / PARB))

    def getCorrectedRZero(self, t, h, brut=None):
        """
        Calcula RZero utilitzant la resistència corregida
        per temperatura i humitat.
        """

        return self.getCorrectedResistance(t, h, brut) * (
            (ATMOCO2 / PARA) ** (1.0 / PARB)
        )
