#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import descargar_wattpad, descargar_tumblr
import logging

logging.basicConfig(level=logging.INFO)

def test_wattpad():
    print("=== Probando Wattpad ===")
    url = "https://www.wattpad.com/story/234768105?utm_source=android&utm_medium=Share&utm_campaign=App_Wattpad"
    titulo, capitulos = descargar_wattpad(url)
    if titulo and capitulos:
        print(f"✅ Éxito: {titulo} - {len(capitulos)} capítulos")
        print(f"Primer capítulo: {capitulos[0][0]} - {len(capitulos[0][1])} caracteres")
    else:
        print("❌ Falló Wattpad")

def test_tumblr():
    print("\n=== Probando Tumblr ===")
    url = "https://www.tumblr.com/bywons/798039788420808704/say-it-right-sim-jaeyun-smau-synopsis?source=share"
    titulo, capitulos = descargar_tumblr(url)
    if titulo and capitulos:
        print(f"✅ Éxito: {titulo} - {len(capitulos)} posts")
        print(f"Contenido extraído: {len(capitulos[0][1])} caracteres")
        print(f"Preview: {capitulos[0][1][:200]}...")
    else:
        print("❌ Falló Tumblr")



if __name__ == "__main__":
    test_wattpad()
    test_tumblr()
