# Corpus experimental

El corpus se divide en:

- `positive/`: valores sintéticos que deben detectarse;
- `benign/`: valores que parecen secretos, pero deben permitirse;
- `history/`: casos que existirán únicamente en commits históricos de repositorios efímeros de prueba.

Cada caso tendrá un identificador, clase, formato, resultado esperado y fuente conceptual. Ningún caso puede contener una credencial real o una copia de una credencial de PyroPrev.

## Corpus piloto v1

El generador `scripts/generate_corpus.py` produce cuatro formatos positivos y cuatro controles benignos. Los valores se derivan de forma determinista, nunca fueron emitidos por un proveedor y no se incluyen en el manifiesto. El corpus se genera en `tmp/` o en un directorio temporal y no se versiona como texto sensible.
