"""RAG local y gratuito: búsqueda BM25 sobre los .txt de política e informe de zonas.

No usa embeddings ni servicios externos (costo cero, determinista).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import DIR_DATOS
from .validacion import MAX_CONSULTA, normalizar, validar_entero, validar_texto

DOCUMENTOS_RAG = ("politica_pricing_izipay.txt", "informe_rentabilidad_zonas.txt")
MAX_CARACTERES_FRAGMENTO = 900
_RE_TITULO = re.compile(r"^\d+\.\s+[A-ZÁÉÍÓÚÑ]")
_RE_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "de la el en y a los las un una por con para que se del al es o u su sus lo como si".split()
)
K1, B = 1.5, 0.75


@dataclass(frozen=True)
class Fragmento:
    fuente: str
    texto: str


def raiz(token: str) -> str:
    """Stemming mínimo del español (plural y vocal final): 'mínima' y 'minimo' → 'minim'."""
    if len(token) > 4 and token.endswith("es"):
        token = token[:-2]
    elif len(token) > 3 and token.endswith("s"):
        token = token[:-1]
    if len(token) > 4 and token[-1] in "ao":
        token = token[:-1]
    return token


def tokenizar(texto: str) -> list[str]:
    return [raiz(t) for t in _RE_TOKEN.findall(normalizar(texto)) if t not in _STOPWORDS]


def _empaquetar(lineas: list[str]) -> list[str]:
    """Agrupa líneas en bloques de hasta MAX_CARACTERES_FRAGMENTO repitiendo el título."""
    titulo, cuerpo = lineas[0], lineas[1:]
    bloques, actual = [], [titulo]
    for linea in cuerpo:
        if sum(len(x) for x in actual) + len(linea) > MAX_CARACTERES_FRAGMENTO and len(actual) > 1:
            bloques.append("\n".join(actual))
            actual = [titulo]
        actual.append(linea)
    bloques.append("\n".join(actual))
    return bloques


def dividir_en_fragmentos(texto: str, fuente: str) -> list[Fragmento]:
    """Divide por secciones numeradas ('3. REGLAS…') y empaqueta secciones largas."""
    secciones: list[list[str]] = [[]]
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        if _RE_TITULO.match(linea) and secciones[-1]:
            secciones.append([])
        secciones[-1].append(linea.strip())
    return [Fragmento(fuente, b) for sec in secciones if sec for b in _empaquetar(sec)]


class IndiceBM25:
    def __init__(self, fragmentos: list[Fragmento]) -> None:
        self.fragmentos = fragmentos
        self._tokens = [tokenizar(f.texto) for f in fragmentos]
        self._largo_medio = sum(len(t) for t in self._tokens) / max(len(self._tokens), 1)
        self._df: dict[str, int] = {}
        for tokens in self._tokens:
            for t in set(tokens):
                self._df[t] = self._df.get(t, 0) + 1

    def _idf(self, termino: str) -> float:
        n, df = len(self.fragmentos), self._df.get(termino, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _puntaje(self, consulta: list[str], tokens: list[str]) -> float:
        total = 0.0
        for termino in set(consulta):
            f = tokens.count(termino)
            if f:
                denom = f + K1 * (1 - B + B * len(tokens) / max(self._largo_medio, 1e-9))
                total += self._idf(termino) * f * (K1 + 1) / denom
        return total

    def buscar(self, consulta: str, top_k: int = 3) -> list[tuple[Fragmento, float]]:
        tokens_q = tokenizar(consulta)
        puntajes = [(f, self._puntaje(tokens_q, t)) for f, t in zip(self.fragmentos, self._tokens)]
        ordenados = sorted((p for p in puntajes if p[1] > 0), key=lambda p: p[1], reverse=True)
        return ordenados[:top_k]


@lru_cache(maxsize=2)
def _indice(directorio: str) -> IndiceBM25:
    fragmentos: list[Fragmento] = []
    for nombre in DOCUMENTOS_RAG:
        ruta = Path(directorio) / nombre
        if ruta.is_file():
            fragmentos.extend(dividir_en_fragmentos(ruta.read_text(encoding="utf-8"), nombre))
    return IndiceBM25(fragmentos)


def buscar_politica(consulta: str, top_k: int = 3, directorio: Path | None = None) -> list[dict[str, object]]:
    """Busca fragmentos relevantes. Valida consulta (≤300 car.) y top_k (1-5)."""
    texto = validar_texto(consulta, "consulta", MAX_CONSULTA)
    k = validar_entero(top_k, "top_k", 1, 5)
    indice = _indice(str(directorio or DIR_DATOS))
    return [{"fuente": f.fuente, "fragmento": f.texto, "puntaje": round(p, 3)}
            for f, p in indice.buscar(texto, k)]
