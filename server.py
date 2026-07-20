#!/usr/bin/env python3
"""Petit serveur local pour le lecteur de L'Odyssée."""

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os


PORT = 8000
os.chdir(Path(__file__).resolve().parent)

print("⛵ L’Odyssée est prête.")
print(f"📖 Ouvrez http://localhost:{PORT}")
print("Arrêt : Ctrl+C")

try:
    ThreadingHTTPServer(("", PORT), SimpleHTTPRequestHandler).serve_forever()
except KeyboardInterrupt:
    print("\nServeur arrêté.")
