# Instrucciones – Carbon Stars (Observatorio)

Este documento explica **cómo ejecutar la app** de Carbon Stars tanto con **Docker** (recomendado) como sin Docker, y describe el **flujo de uso** y la **resolución de problemas** más comunes.

---

## Opción A: con Docker (recomendado)

> **Requisitos**: Docker Engine (Linux) o Docker Desktop (Windows/Mac).

1. **Clonar el repositorio**:
   ```bash
   git clone <REPO_URL>
   cd <REPO_DIR>
   ```

2. **Ejecutar la app**  
   - **Linux / WSL / Mac**:
     ```bash
     ./start_app.sh
     ```
   - **Windows**:
     - Doble clic en `start_app.bat` **o** desde PowerShell/CMD:
       ```bat
       start_app.bat
       ```

3. **Abrir en el navegador**:  
   <http://localhost:8501>

4. **Para detener la app**  
   - **Linux / WSL / Mac**:
     ```bash
     ./stop_app.sh
     ```
   - **Windows**:
     - Doble clic en `stop_app.bat` **o**:
       ```bat
       stop_app.bat
       ```

> **Notas**  
> - Los scripts de arranque construyen la imagen y levantan el contenedor automáticamente.  
> - Si el navegador no muestra cambios tras actualizar el código, **reiniciá** el contenedor (volver a ejecutar el script).

---

## Opción B: sin Docker (Python local)

> **Requisitos**: Python 3.10+ y `pip`.

1. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Ejecutar la app**:
   ```bash
   streamlit run app.py --server.port=8501 --server.address=0.0.0.0
   ```

3. **Navegar a**: <http://localhost:8501>

---

## Flujo de uso

1. **Cargar Catálogo** (Merlo **ALFA/DELTA** o **RA/DEC**).  
   La app normaliza automáticamente y crea columnas **`ra`** y **`dec`** en **grados**.
2. **Cargar archivos `.asc`** (uno o varios).  
   La app ignora líneas con `#`, detecta separadores (espacios/tabs) y normaliza RA/DEC.
3. **Ajustar** **θ (arcsec)** y presionar **“Ejecutar matching”**.  
   El sistema realiza el emparejamiento por **mínima separación angular**.
4. **Descargar resultados (CSV)**.  
   También podés descargar el catálogo normalizado.

---

## Archivos de ejemplo

- `data_ejemplo/merlo_carbon_star_catalog.txt`
- `data_ejemplo/ejemplo.asc`

---

## Problemas frecuentes (Troubleshooting)

- **“No module named 'scipy'” / errores de Astropy**  
  → Usar **Docker** o instalar dependencias con `pip install -r requirements.txt` y volver a ejecutar.

- **“problema de codificación o formato” al leer el catálogo**  
  → La app detecta cabecera **ALFA/DELTA**; si el archivo tiene encabezados no estándar, enviar una muestra para ajustar el lector.

- **No se ven los cambios en la app**  
  → Reiniciar el contenedor: `./start_app.sh` (Linux/WSL/Mac) o `start_app.bat` (Windows).

- **Puerto 8501 ocupado**  
  → Cerrar procesos previos (`./stop_app.sh` o `stop_app.bat`) o cambiar de puerto en el comando de Streamlit.

---

## Notas finales

- La app funciona en **ICRS** (RA/DEC) y entrega coordenadas en **grados**.  
- Para reproducibilidad, se proveen **Dockerfile**, **scripts de arranque** y **requirements**.  
- Cualquier formato de catálogo/`.asc` fuera de los contemplados puede incorporarse rápidamente con un ejemplo de archivo.
