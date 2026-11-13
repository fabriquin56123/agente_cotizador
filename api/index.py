"""Punto de entrada OPCIONAL para Vercel (Functions de Python con FastAPI).

Vercel expone la variable `app` (ASGI). No se despliega nada automáticamente:
ver README, sección "Vercel", para el plan y la aprobación.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.app import app  # noqa: E402,F401
