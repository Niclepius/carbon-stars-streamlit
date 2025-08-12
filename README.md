# Carbon Stars – Streamlit App

Aplicación Streamlit para identificar y visualizar coincidencias entre un catálogo base y archivos de coordenadas `.asc`.  
Esta versión está optimizada para despliegue simple en Docker.

## Requisitos

- Docker instalado (Linux nativo o WSL2; no requiere Docker Desktop).
- Acceso a internet para construir la imagen (descarga de dependencias PyPI).

## Instalación y ejecución

```bash
git clone https://github.com/Niclepius/carbon-stars-streamlit.git
cd carbon-stars-streamlit
./start_app.sh
```

La aplicación estará disponible en:  
[http://localhost:8501](http://localhost:8501)

---

## Formato esperado de archivos

### Catálogo base
- CSV/TSV con columnas `ra` y `dec` en grados.
- La app intenta mapear nombres de columna comunes (`ra_deg`, `dec_deg`, `object`, `source`, etc.).
- Si no existe `id`, se creará automáticamente usando el índice.

### Archivos `.asc`
- Texto con filas que contengan al menos dos valores numéricos por línea (RA y DEC en grados).
- Se ignoran líneas vacías y comentarios que comiencen con `#`.
- El separador puede ser tabulación, coma o espacio.

---

## Uso

1. **Subir catálogo base** (seleccionar el separador correcto).
2. **Subir uno o varios archivos `.asc`**.
3. **Ajustar el umbral θ (arcsec)** para filtrar coincidencias.
4. **Descargar el CSV** con los resultados combinados.

---

## Archivos de prueba incluidos

En este repositorio se incluyen **dos archivos reales de prueba** para validar la app:

- `Testing/merlo_carbon_star_catalog.txt` — Catálogo base (Merlo Carbon Star Catalog).
- `Testing/v20100313_00394_st_tl_cat.asc` — Archivo `.asc` con coordenadas de fuentes.

### Cómo probar con los archivos incluidos

1. Construir y ejecutar la app:
   ```bash
   ./start_app.sh
   ```
   Abrir [http://localhost:8501](http://localhost:8501).

2. En la interfaz:
   - En **“1) Catálogo base”**, subir `Testing/merlo_carbon_star_catalog.txt`.  
     *(Seleccionar separador: probablemente “TSV (tab)” o “Punto y coma” según el formato).*
   - En **“2) Archivos .asc”**, subir `Testing/v20100313_00394_st_tl_cat.asc`.
   - Ajustar el **umbral θ (arcsec)** si lo desean y presionar **“Procesar”**.

3. Descargar los resultados combinados con el botón **“⬇️ Descargar resultados (CSV)”**.

---

## Notas técnicas

- El cálculo de coincidencias usa `SkyCoord.match_to_catalog_sky` de Astropy para lograr alta velocidad en el matching.
- El archivo `requirements.txt` tiene versiones fijadas para garantizar reproducibilidad.
- El contenedor expone el puerto `8501`. Si está ocupado, se puede cambiar el mapeo:
  ```bash
  docker run --rm -p 8080:8501 carbon-stars:dev
  ```
  y abrir [http://localhost:8080](http://localhost:8080).

---

## Troubleshooting

**La app muestra contenido viejo**  
Es posible que haya otro contenedor ocupando el puerto 8501:
```bash
docker ps
docker rm -f $(docker ps -q)
```
y volver a ejecutar `./start_app.sh`.

**Error durante la construcción**  
Limpiar y reconstruir:
```bash
docker system prune -af
docker builder prune -af
docker build --no-cache -t carbon-stars:dev .
```

**Sin acceso a Docker como usuario**  
Agregar el usuario al grupo `docker`:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

## Próximas mejoras
- Procesamiento optimizado para múltiples `.asc`.
- Filtro avanzado de coincidencias y visualización interactiva.
- Soporte para catálogos de gran tamaño.
