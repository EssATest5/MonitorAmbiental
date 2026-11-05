#############################################################################
# test_led.py
#Autor: Pedro J
#modificat: 
#	28/09/26 : creació
#############################################################################


import RPi.GPIO as GPIO
from time import sleep

# Definim el pin utilitzant la numeració GPIO (BCM)
LED_D1  = 26


B_ESTAT_ACTUAL = True

# Configuració dels pins
GPIO.setmode(GPIO.BCM)       # Fes servir  la numeració de Broadcom (GPIO)
GPIO.setup( LED_D1,  GPIO.OUT) # Configura el pins com a sortida . Des de una llista de pins


#print("El pin està parpellejant... Prem Ctrl+C per sortir.")

try:
   while True:
      #GPIO.output(LED_D1, GPIO.HIGH) # Envia corrent (encén)
      GPIO.output(LED_D1, B_ESTAT_ACTUAL) # Envia corrent (encén)
      
      B_ESTAT_ACTUAL = not(B_ESTAT_ACTUAL)
      
      #GPIO.output(LED_D1, GPIO.LOW) # Envia corrent (encén)
	
      sleep(1)

except KeyboardInterrupt:
      print("\nAturant el programa...")
finally:
      GPIO.cleanup() # Neteja la configuració dels pins al sortir
      print("Pins alliberats correctament.")
