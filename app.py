import io
import math
import tempfile
from typing import Tuple, Optional

import pandas as pd
import streamlit as st
from astropy.coordinates import SkyCoord
import astropy.units as u

st.set_page_config(page_title="Carbon Stars - Matching", layout="wide")

# ---------------------------
# Utilidades
# ---------------------------
@st.cache_data(show_spinner=False)
def load_catalog(file_bytes: bytes, sep: str = ",") -> pd.DataFrame:
    buf = io.BytesIO(file_bytes)
    df = pd.read_csv(buf, sep=sep)
    # Normalización de columnas esperadas
    cols = {c.lower(): c for c in df.columns}
    # Intenta mapear variantes comunes
    rename_map = {}
    for target in ["id", "name"]:
        for k in list(cols):
            if k in [target, f"{target}_star", "star", "source", "obj", "object"]:
                rename_map[cols[k]] = "id"
                break
    for target in ["ra", "ra_deg", "ra_degJ2000"]:
        for k in list(cols):
            if k.startswith("ra"):
                rename_map[cols[k]] = "ra"
                break
    for target in ["dec", "dec_deg", "dec_degJ2000"]:
        for k in list(cols):
            if k.startswith("dec"):
                rename_map[cols[k]] = "dec"
                break
    if rename_map:
        df = df.rename(columns=rename_map)
    # Validación mínima
    for c in ["ra", "dec"]:
        if c not in df.columns:
            raise ValueError(f"Catálogo inválido: falta columna '{c}' (en grados).")
    if "id" not in df.columns:
        df["id"] = df.index.astype(str)
    return df[["id", "ra", "dec"]].copy()

def parse_sep(sep_label: str) -> str:
    return {"CSV (coma)": ",", "TSV (tab)": "\t", "Punto y coma": ";"}.get(sep_label, ",")

def compute_sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    a = SkyCoord(float(ra1)*u.deg, float(dec1)*u.deg, frame="icrs")
    b = SkyCoord(float(ra2)*u.deg, float(dec2)*u.deg, frame="icrs")
    return a.separation(b).arcsecond

def best_match_for_source(src_ra, src_dec, catalog_sc: SkyCoord) -> Tuple[int, float]:
    """Devuelve (idx_mejor, sep_arcsec). Usa vectorización SkyCoord -> mucho más rápido."""
    s = SkyCoord(float(src_ra)*u.deg, float(src_dec)*u.deg, frame="icrs")
    idx, sep = catalog_sc.match_to_catalog_sky(s)
    return int(idx), float(sep.arcsecond)

def to_skycoord(df: pd.DataFrame) -> SkyCoord:
    return SkyCoord(df["ra"].astype(float).values*u.deg,
                    df["dec"].astype(float).values*u.deg,
                    frame="icrs")

# ---------------------------
# UI
# ---------------------------
st.title("🌟 Carbon Stars v0.4")
st.caption("Subí tu catálogo base y uno o varios archivos *.asc para obtener el mejor match por estrella.")

with st.sidebar:
    st.header("1) Catálogo base")
    cat_file = st.file_uploader("Subir catálogo (CSV/TSV)", type=["csv", "tsv", "txt"])
    cat_sep_label = st.selectbox("Separador", ["CSV (coma)", "TSV (tab)", "Punto y coma"], index=0)
    st.divider()
    st.header("2) Archivos .asc")
    asc_files = st.file_uploader("Subir uno o varios .asc", type=["asc", "txt"], accept_multiple_files=True)
    st.divider()
    theta_max = st.number_input("Umbral θ (arcsec)", min_value=0.0, value=1.0, step=0.1)
    st.caption("Mostrar solo coincidencias con separación angular menor o igual a este umbral.")
    run_btn = st.button("🔎 Procesar")

# Estado (para reutilizar catálogo)
if "catalog_df" not in st.session_state:
    st.session_state["catalog_df"] = None
if "catalog_sc" not in st.session_state:
    st.session_state["catalog_sc"] = None

# Carga catálogo
if cat_file:
    try:
        df_cat = load_catalog(cat_file.read(), sep=parse_sep(cat_sep_label))
        st.session_state["catalog_df"] = df_cat
        st.session_state["catalog_sc"] = to_skycoord(df_cat)
        st.success(f"Catálogo cargado: {len(df_cat):,} fuentes.")
        with st.expander("Ver primeras filas del catálogo"):
            st.dataframe(df_cat.head(20), use_container_width=True)
    except Exception as e:
        st.error(f"Error leyendo catálogo: {e}")

# Procesamiento
if run_btn:
    if st.session_state["catalog_df"] is None or st.session_state["catalog_sc"] is None:
        st.warning("Subí primero el catálogo base.")
    elif not asc_files:
        st.warning("Subí al menos un archivo .asc.")
    else:
        cat_df = st.session_state["catalog_df"]
        cat_sc = st.session_state["catalog_sc"]

        results = []
        prog = st.progress(0, text="Procesando archivos .asc …")
        total = len(asc_files)

        for i, asc in enumerate(asc_files, start=1):
            st.write(f"📄 Archivo: **{asc.name}**")
            # Lectura robusta (línea a línea, manejando formatos simples RA,DEC por columna o separado)
            lines = asc.read().decode(errors="ignore").splitlines()
            # Detección ingenua de separador (espacio o coma o tab)
            for ln in lines:
                if ln.strip().startswith("#") or len(ln.strip()) == 0:
                    continue
                if "\t" in ln:
                    asc_sep = "\t"
                elif "," in ln:
                    asc_sep = ","
                else:
                    asc_sep = None  # intentar split por espacios
                break
            # Parseo a DF
            rows = []
            for ln in lines:
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                try:
                    if asc_sep:
                        parts = [p for p in s.split(asc_sep) if p != ""]
                    else:
                        parts = s.split()
                    # Heurística mínima: RA y DEC en grados en las dos primeras columnas numéricas
                    nums = []
                    for p in parts:
                        try:
                            nums.append(float(p))
                        except:
                            continue
                    if len(nums) >= 2:
                        rows.append((nums[0], nums[1]))
                except:
                    continue
            if not rows:
                st.warning(f"No se pudieron extraer RA/DEC de {asc.name}.")
                prog.progress(i/total)
                continue

            df_src = pd.DataFrame(rows, columns=["ra", "dec"])
            st.write(f"→ Fuentes detectadas en {asc.name}: {len(df_src):,}")

            # MATCH vectorizado con SkyCoord
            src_sc = to_skycoord(df_src)
            idx_cat, sep_sky = cat_sc.match_to_catalog_sky(src_sc)
            seps_arcsec = sep_sky.arcsecond

            matched = pd.DataFrame({
                "src_ra": df_src["ra"].astype(float).round(8),
                "src_dec": df_src["dec"].astype(float).round(8),
                "match_id": cat_df.iloc[idx_cat]["id"].values,
                "match_ra": cat_df.iloc[idx_cat]["ra"].astype(float).round(8).values,
                "match_dec": cat_df.iloc[idx_cat]["dec"].astype(float).round(8).values,
                "theta_arcsec": seps_arcsec.round(4)
            })
            matched["source_file"] = asc.name

            # Filtro por θ
            matched_f = matched[matched["theta_arcsec"] <= float(theta_max)].reset_index(drop=True)
            st.success(f"Coincidencias ≤ {theta_max}\" en {asc.name}: {len(matched_f):,}")
            with st.expander(f"Ver resultados de {asc.name}"):
                st.dataframe(matched_f, use_container_width=True)
            results.append(matched_f)

            prog.progress(i/total)

        if results:
            out = pd.concat(results, ignore_index=True)
            st.divider()
            st.subheader("✅ Resultados combinados")
            st.dataframe(out, use_container_width=True)

            csv = out.to_csv(index=False).encode()
            st.download_button("⬇️ Descargar resultados (CSV)", data=csv, file_name="matches.csv", mime="text/csv")
        else:
            st.info("No hubo resultados para descargar.")
