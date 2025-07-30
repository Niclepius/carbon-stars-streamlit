import streamlit as st
import pandas as pd
from astropy.coordinates import SkyCoord
import astropy.units as u
import os
import time
import math

# =========================
# Estado global
# =========================
if "carbon_stars" not in st.session_state:
    st.session_state["carbon_stars"] = {}

# =========================
# Funciones principales
# =========================
def cargar_catalogo(file):
    st.session_state["carbon_stars"].clear()
    if file is None:
        return pd.DataFrame(), "⚠️ No se cargó ningún catálogo."

    lines = file.read().decode("utf-8").splitlines()
    estrellas = []
    started = False

    for line in lines:
        if line.strip().startswith("s"):
            started = True
        if started and line.strip():
            partes = line.strip().split()
            if len(partes) >= 7:
                key = partes[0]
                name = partes[1]
                ra_str = " ".join(partes[2:5])
                dec_str = " ".join(partes[5:8])
                try:
                    coord = SkyCoord(f"{ra_str} {dec_str}", unit=(u.hourangle, u.deg), frame='icrs')
                    st.session_state["carbon_stars"][key] = {
                        'name': name, 'coord': coord, 'ra': ra_str, 'dec': dec_str
                    }
                    estrellas.append((key, name, ra_str, dec_str))
                except Exception as e:
                    print(f"Error en la línea: {line.strip()} – {e}")

    if estrellas:
        return pd.DataFrame(estrellas, columns=["ID", "Nombre", "RA", "DEC"]), "✅ Catálogo cargado correctamente."
    else:
        return pd.DataFrame(), "⚠️ No se pudieron cargar estrellas del catálogo."


def calcular_estimacion_tiempo(files):
    if not files:
        return "⚠️ No se subieron archivos .asc."
    total_mb = sum(file.size for file in files) / 1_000_000
    tiempo_aprox = total_mb * 0.5  # 0.5 seg por MB
    t_min = round((tiempo_aprox * 0.9) / 60)
    t_max = round((tiempo_aprox * 1.1) / 60)
    return f"🕒 El procesamiento tomará entre {t_min} y {t_max} minutos."


def procesar_lote(files, theta_max):
    resultados = []
    errores = []

    for file in files:
        try:
            df = pd.read_csv(file, delim_whitespace=True, header=None)
            if df.shape[1] < 12:
                errores.append(f"{file.name}: columnas insuficientes")
                continue

            df = df[[0, 1, 2, 3, 4, 5, 8, 9, 11]].copy()
            df.columns = ['RA_h', 'RA_m', 'RA_s', 'DEC_d', 'DEC_m', 'DEC_s', 'MAG', 'MAG_ERR', 'TYPE']
            df = df[df['TYPE'] == -1].reset_index(drop=True)

            if df.empty:
                errores.append(f"{file.name}: sin fuentes tipo -1")
                continue

            ra_str = df['RA_h'].astype(int).astype(str) + "h" + df['RA_m'].astype(int).astype(str) + "m" + df['RA_s'].astype(str) + "s"
            dec_sign = df['DEC_d'].apply(lambda x: '-' if x < 0 else '+')
            dec_str = dec_sign + df['DEC_d'].abs().astype(int).astype(str) + "d" + df['DEC_m'].astype(int).astype(str) + "m" + df['DEC_s'].astype(int).astype(str) + "s"
            coords = SkyCoord(ra=ra_str.values, dec=dec_str.values, frame='icrs')

            for key, c_star in st.session_state["carbon_stars"].items():
                separations = coords.separation(c_star['coord']).arcsecond
                if len(separations) == 0:
                    continue
                min_idx = separations.argmin()

                if separations[min_idx] <= theta_max:
                    row = df.loc[min_idx].copy()
                    row['carbon_star_key'] = key
                    row['coord'] = str(coords[min_idx])
                    row['separation_arcsec'] = separations[min_idx]
                    row['source_file'] = os.path.basename(file.name)
                    resultados.append(row)

        except Exception as e:
            errores.append(f"{file.name}: {str(e)}")

    return pd.DataFrame(resultados), errores


def procesar_archivos(files, theta_max, batch_size=5):
    if not st.session_state["carbon_stars"]:
        return None, None, "⚠️ Primero cargá el catálogo antes de procesar."

    resultados_totales = []
    errores_totales = []

    num_batches = math.ceil(len(files) / batch_size)

    for i in range(num_batches):
        batch_files = files[i * batch_size:(i + 1) * batch_size]
        st.write(f"🔄 Procesando lote {i+1}/{num_batches}...")
        df_lote, errores = procesar_lote(batch_files, theta_max)
        if not df_lote.empty:
            resultados_totales.append(df_lote)
        errores_totales.extend(errores)

    if not resultados_totales:
        mensaje_error = "❌ No se encontraron coincidencias."
        if errores_totales:
            mensaje_error += "\n⚠️ Archivos con problemas:\n" + "\n".join(errores_totales)
        return None, None, mensaje_error

    df_completo = pd.concat(resultados_totales, ignore_index=True)
    df_preview = df_completo.head(500)

    return df_completo, df_preview, "✅ Procesamiento finalizado."


# =========================
# Interfaz de Streamlit
# =========================
st.set_page_config(page_title="Carbon Stars App", layout="wide")
st.title("⭐ Carbon Stars v0.3.3")

# --- Cargar catálogo ---
st.header("📄 Cargar catálogo de estrellas")
catalog_file = st.file_uploader("Subí el catálogo .txt", type=["txt"])
if st.button("Cargar catálogo"):
    catalog_df, catalog_msg = cargar_catalogo(catalog_file)
    st.info(catalog_msg)
    if not catalog_df.empty:
        st.dataframe(catalog_df, use_container_width=True)

# --- Subida de archivos ASC ---
st.header("📁 Procesar archivos .asc")
asc_files = st.file_uploader("Subí uno o varios archivos .asc", type=["asc"], accept_multiple_files=True)

if asc_files:
    st.info(calcular_estimacion_tiempo(asc_files))
    theta_max = st.number_input("Filtro θ máximo (arcsec)", min_value=0.0, value=0.5, step=0.1)
    confirmar = st.checkbox("Confirmar procesamiento")

    if confirmar and st.button("Procesar"):
        with st.spinner("Procesando archivos en lotes..."):
            df_completo, df_preview, msg = procesar_archivos(asc_files, theta_max, batch_size=5)

        st.info(msg)
        if df_completo is not None:
            st.dataframe(df_preview, use_container_width=True)
            csv = df_completo.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Descargar resultados completos", data=csv, file_name="resultados.csv", mime="text/csv")
