# Carbon Stars – Catálogo + .ASC (Streamlit + Docker)

App para:
- Cargar y **normalizar** catálogos (ALFA/DELTA o RA/DEC) → `ra, dec` en **grados**
- Cargar **.asc** (uno o varios), normalizarlos y hacer **matching** por mínima separación angular
- Descargar resultados (CSV)

## Demo rápida
- `./make_test.sh` (dev) -> http://localhost:8501

## Requisitos locales (sin Docker)
- Python 3.10+
- `pip install -r requirements.txt`
- `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`

## Con Docker (recomendado)
### Dev (hot-reload)
```bash
./make_test.sh
```

## Producción simple
```bash
./start_app.sh
```
(para detener: ./stop_app.sh)
Windows: usar los `.bat`.
Linux/WSL/Mac: usar los `.sh`.

## Uso dentro de la app
- Subir el catálogo (`.txt/.csv/.tsv`). Se detecta cabecera ALFA/DELTA o RA/DEC.
- Subir uno o varios **.asc** (ignora `#`, separador espacios/tabs).
- Ajustar **θ (arcsec)** y ejecutar **matching**.
- Descargar el CSV.

## Estructura
<pre>
├─ app.py
├─ requirements.txt
├─ Dockerfile
├─ make_test.sh
├─ start_app.sh
├─ stop_app.sh
├─ INSTRUCCIONES_OBSERVATORIO.md
├─ CHANGELOG.md
├─ LICENSE
├─ .gitignore
├─ data_ejemplo/
│  ├─ merlo_carbon_star_catalog.txt
│  └─ ejemplo.asc
└─ screenshots/
   ├─ 01_home.png
   └─ 02_matching_ok.png
   </pre>


## Troubleshooting
- **“No module named 'scipy'”** -> revisar `requirements.txt` y reconstruir imagen.
- **“problema de codificación o formato”** -> el lector ahora detecta cabecera ALFA/DELTA; confirmar que el archivo no tenga caracteres exóticos. Probar con `latin-1`.
- **No se ven cambios en la app** -> reiniciar contenedor (`./make_test.sh` o `./start_app.sh`).

## Licencia
MIT

## Próximas mejoras
- Procesamiento optimizado para múltiples `.asc`.
- Filtro avanzado de coincidencias y visualización interactiva.
- Soporte para catálogos de gran tamaño.
