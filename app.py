import io
import os
import re
import numpy as np
import pandas as pd
import streamlit as st
from typing import Optional, Tuple, List

from astropy.coordinates import SkyCoord, Angle
import astropy.units as u

# =========================
# Config
# =========================
st.set_page_config(page_title="Carbon Stars • v0.4.2", layout="wide")
st.title("🌟Carbon Stars v0.4.2")

st.write(
    "1) Subí tu **catálogo** (Merlo/ALFA-DELTA o RA/DEC) → se normaliza a `ra/dec` en grados.\n"
    "2) Subí uno o varios **.asc** → se normalizan y se hace **matching** por mínima separación.\n"
    "3) Descargá resultados."
)

# =========================
# Utilidades comunes
# =========================

RA_ALIASES = {
    "ra", "raj2000", "ra_j2000", "ra_deg", "ra(deg)", "ra (deg)", "right_ascension",
    "alpha", "α", "ra_hours", "ra_h", "ra_hms", "rahour", "ra_hour",
    "alfa", "alfa(j2000)", "alfa j2000", "ra[deg]"
}
DEC_ALIASES = {
    "dec", "dej2000", "dec_j2000", "dec_deg", "dec(deg)", "dec (deg)", "declination",
    "delta", "δ", "dec_d", "dec_dms", "decl", "delta(j2000)", "delta j2000", "dec[deg]"
}

SEXAGESIMAL_RX = re.compile(
    r"^\s*([+\-]?\d{1,3})[^0-9+\-]+\s*(\d{1,2})[^0-9]+\s*(\d{1,2}(?:\.\d*)?)\s*$"
)

def _strip_and_lower(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower()) if isinstance(s, str) else s

def _clean_name(norm: str) -> str:
    norm = re.sub(r"[\[\(].*?[\]\)]", "", norm).strip()
    return norm.replace("_", " ")

def find_column(df: pd.DataFrame, candidates: set) -> Optional[str]:
    norm_map = {col: _clean_name(_strip_and_lower(str(col))) for col in df.columns}
    for col, norm in norm_map.items():
        base = norm.replace(" ", "")
        if norm in candidates or base in {c.replace("_", "").replace(" ", "") for c in candidates}:
            return col
        if base.endswith("j2000") and base.replace("j2000", "") in {c.replace(" ", "") for c in candidates}:
            return col
    return None

def is_sexagesimal_series(s: pd.Series) -> bool:
    try:
        values = s.dropna().astype(str).head(50).tolist()
    except Exception:
        return False
    hits = 0
    for v in values:
        v = v.strip()
        if SEXAGESIMAL_RX.match(v) or any(x in v for x in ("h", "m", "s", ":")):
            hits += 1
    return hits >= max(3, int(0.5 * len(values))) and len(values) > 0

def parse_ra_dec_to_deg(ra_series: pd.Series, dec_series: pd.Series) -> Tuple[pd.Series, pd.Series]:
    # Sexagesimal → usar Astropy
    if is_sexagesimal_series(ra_series) or is_sexagesimal_series(dec_series):
        ra_str = ra_series.astype(str).replace({"nan": np.nan})
        dec_str = dec_series.astype(str).replace({"nan": np.nan})
        out_ra, out_dec = [], []
        for ra_v, dec_v in zip(ra_str, dec_str):
            if pd.isna(ra_v) or pd.isna(dec_v):
                out_ra.append(np.nan); out_dec.append(np.nan); continue
            try:
                c = SkyCoord(ra=ra_v, dec=dec_v, unit=(u.hourangle, u.deg), frame="icrs")
                out_ra.append(float(c.ra.deg)); out_dec.append(float(c.dec.deg))
            except Exception:
                try:
                    c = SkyCoord(Angle(ra_v, unit=u.hourangle), Angle(dec_v, unit=u.deg), frame="icrs")
                    out_ra.append(float(c.ra.deg)); out_dec.append(float(c.dec.deg))
                except Exception:
                    out_ra.append(np.nan); out_dec.append(np.nan)
        return pd.Series(out_ra), pd.Series(out_dec)

    # Numérico → decidir horas vs grados
    ra_num = pd.to_numeric(ra_series, errors="coerce")
    dec_num = pd.to_numeric(dec_series, errors="coerce")
    ra_max = np.nanmax(ra_num.values) if np.any(~np.isnan(ra_num.values)) else np.nan

    if not np.isnan(ra_max) and ra_max <= 24.5:  # horas
        ra_deg = ra_num * 15.0
    else:
        ra_deg = ra_num.where((ra_num >= 0) & (ra_num <= 360), np.nan)
    dec_deg = dec_num.where((dec_num >= -90) & (dec_num <= 90), np.nan)
    return ra_deg, dec_deg

# =========================
# Lectores
# =========================

def read_catalog(uploaded) -> pd.DataFrame:
    """Catálogo estilo Merlo (cabecera ALFA/DELTA no en primera línea) o CSV/TSV clásico."""
    raw = uploaded.read()
    if not isinstance(raw, (bytes, bytearray)):
        raw = uploaded.getvalue()

    # decodificación
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc, errors="strict")
            break
        except Exception:
            continue
    if text is None:
        raise ValueError("No se pudo leer el archivo: problema de codificación o formato.")

    lines = text.splitlines()
    header_idx = None
    for i, l in enumerate(lines):
        if ("ALFA" in l.upper() or "RA" in l.upper()) and ("DELTA" in l.upper() or "DEC" in l.upper()):
            if re.search(r"(ALFA|RA).*(DELTA|DEC)", l.upper()):
                header_idx = i
                break

    if header_idx is not None:
        data_block = "\n".join(lines[header_idx:])
        # tabs o espacios múltiples
        try:
            df = pd.read_csv(io.StringIO(data_block), sep=r"\s*\t\s*|\s{2,}", engine="python")
            return df
        except Exception:
            try:
                return pd.read_fwf(io.StringIO(data_block))
            except Exception:
                pass

    # Fallback genérico
    try:
        return pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
    except Exception:
        for sep in ("\t", ",", ";", r"\s{2,}"):
            try:
                return pd.read_csv(io.BytesIO(raw), sep=sep, engine="python")
            except Exception:
                continue
    raise ValueError("No se pudo leer el catálogo: formato no reconocido.")

def read_asc(uploaded) -> pd.DataFrame:
    """
    Lector robusto para .asc:
    - Ignora líneas de comentario que empiezan con '#'
    - Detecta separador por espacios/tabs
    - Soporta cabeceras en la primera línea no comentada
    """
    raw = uploaded.read()
    if not isinstance(raw, (bytes, bytearray)):
        raw = uploaded.getvalue()

    # decodificación
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc, errors="strict")
            break
        except Exception:
            continue
    if text is None:
        raise ValueError("No se pudo leer el .asc: problema de codificación.")

    # Drop comentarios y líneas vacías al frente
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    # Si el archivo viene con mucho “ruido” inicial, buscar fila con posibles nombres
    # comunes que delaten presencia de cabecera (ra/dec/x/y/etc.)
    header_idx = None
    for i, l in enumerate(lines[:50]):  # mirar primeras 50
        if re.search(r"(ra|alfa|alpha).*|(dec|delta|decl)", l, flags=re.I):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0

    block = "\n".join(lines[header_idx:])
    # Intento 1: espacios/tabs
    try:
        df = pd.read_csv(io.StringIO(block), sep=r"\s+", engine="python")
        return df
    except Exception:
        pass

    # Intento 2: TSV
    try:
        return pd.read_csv(io.StringIO(block), sep="\t")
    except Exception:
        pass

    # Intento 3: fixed width
    try:
        return pd.read_fwf(io.StringIO(block))
    except Exception:
        pass

    raise ValueError("No se pudo leer el .asc: formato no reconocido.")

# =========================
# Normalización
# =========================

def normalize_catalog(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("El catálogo está vacío.")

    ra_col = find_column(df, RA_ALIASES)
    dec_col = find_column(df, DEC_ALIASES)

    if ra_col is None or dec_col is None:
        lowered = {_strip_and_lower(c): c for c in df.columns}
        ra_guess = next((orig for norm, orig in lowered.items() if any(k in norm for k in ["ra", "alfa", "alpha", "right asc"])), None)
        dec_guess = next((orig for norm, orig in lowered.items() if any(k in norm for k in ["dec", "delta", "decl"])), None)
        ra_col = ra_col or ra_guess
        dec_col = dec_col or dec_guess

    if ra_col is None or dec_col is None:
        raise ValueError("Catálogo: no se encontraron columnas RA/DEC (o ALFA/DELTA).")

    ra_deg, dec_deg = parse_ra_dec_to_deg(df[ra_col], df[dec_col])

    out = df.copy()
    out["ra"] = ra_deg
    out["dec"] = dec_deg

    if out["ra"].isna().all() or out["dec"].isna().all():
        raise ValueError("Catálogo inválido: no fue posible convertir RA/DEC a grados.")
    return out

def normalize_asc(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError(".ASC vacío.")

    ra_col = find_column(df, RA_ALIASES)
    dec_col = find_column(df, DEC_ALIASES)

    # SExtractor/otros pueden traer nombres raros: 'ALPHA_J2000', 'DELTA_J2000'
    if ra_col is None:
        for c in df.columns:
            if re.fullmatch(r"alpha.*j2000", _clean_name(_strip_and_lower(str(c)))): ra_col = c; break
    if dec_col is None:
        for c in df.columns:
            if re.fullmatch(r"delta.*j2000|dec.*j2000", _clean_name(_strip_and_lower(str(c)))): dec_col = c; break

    if ra_col is None or dec_col is None:
        # último recurso: buscar columnas con rangos compatibles
        num_cols = {c: pd.to_numeric(df[c], errors="coerce") for c in df.columns}
        # RA candidata: [0,360] o [0,24]
        ra_candidates = [c for c, s in num_cols.items() if s.notna().mean()>0.5 and ((s.between(0,360).mean()>0.5) or (s.between(0,24.5).mean()>0.5))]
        # DEC candidata: [-90,90]
        dec_candidates = [c for c, s in num_cols.items() if s.notna().mean()>0.5 and (s.between(-90,90).mean()>0.5)]
        if not ra_candidates or not dec_candidates:
            raise ValueError(".ASC: no se detectaron columnas RA/DEC.")
        ra_col, dec_col = ra_candidates[0], dec_candidates[0]

    ra_deg, dec_deg = parse_ra_dec_to_deg(df[ra_col], df[dec_col])
    out = df.copy()
    out["ra"] = ra_deg
    out["dec"] = dec_deg

    if out["ra"].isna().all() or out["dec"].isna().all():
        raise ValueError(".ASC inválido: no fue posible convertir RA/DEC a grados.")
    return out

# =========================
# Matching
# =========================

def match_catalog_to_ascs(cat_df: pd.DataFrame, asc_list: List[Tuple[str, pd.DataFrame]], theta_arcsec: float) -> pd.DataFrame:
    """
    Para cada fila del catálogo, encuentra el mejor match (mínima separación)
    entre todos los .asc normalizados, si la separación < theta_arcsec.
    """
    results = []

    # Preparar catálogo
    cat_valid = cat_df.dropna(subset=["ra","dec"]).copy()
    if cat_valid.empty:
        raise ValueError("El catálogo no tiene filas válidas con RA/DEC.")

    # Inicializar SkyCoord del catálogo
    cat_coords = SkyCoord(ra=cat_valid["ra"].values * u.deg, dec=cat_valid["dec"].values * u.deg, frame="icrs")

    # Identificador de la estrella (STAR o NOMBRE o índice)
    star_col = None
    for cand in ["STAR", "star", "nombre", "NOMBRE", "id", "ID"]:
        if cand in cat_valid.columns:
            star_col = cand
            break

    # Buscar mejor en cada .asc
    best_sep = np.full(len(cat_valid), np.inf)
    best_file = np.array([""] * len(cat_valid), dtype=object)
    best_row_idx = np.full(len(cat_valid), -1)

    for fname, asc_df in asc_list:
        asc_valid = asc_df.dropna(subset=["ra","dec"]).copy()
        if asc_valid.empty:
            continue
        asc_coords = SkyCoord(ra=asc_valid["ra"].values * u.deg, dec=asc_valid["dec"].values * u.deg, frame="icrs")
        # matriz de separaciones: cat x asc (usar match_to_catalog_sky por rapidez)
        idx, sep2d, _ = cat_coords.match_to_catalog_sky(asc_coords)
        sep_arcsec = sep2d.to(u.arcsec).value

        # actualizar mejores
        better = sep_arcsec < best_sep
        best_sep[better] = sep_arcsec[better]
        best_file[better] = fname
        best_row_idx[better] = idx[better]

        # Construir tabla final
    results = []
    cat_reset = cat_valid.reset_index(drop=True)

    for i, row in cat_reset.iterrows():
        sep = best_sep[i]
        # Id de la estrella (STAR, NOMBRE o índice)
        if "STAR" in cat_reset.columns:
            star_id_val = row["STAR"]
        elif "NOMBRE" in cat_reset.columns:
            star_id_val = row["NOMBRE"]
        else:
            star_id_val = i

        if np.isfinite(sep) and sep <= theta_arcsec:
            src_file = best_file[i]
            src_idx = int(best_row_idx[i])

            # Recuperar datos del .asc con el MISMO dropna() que se usó para hacer match
            asc_df_full = dict(asc_list)[src_file]
            asc_valid = asc_df_full.dropna(subset=["ra", "dec"])
            asc_row = asc_valid.iloc[src_idx]

            results.append({
                "star_id":       star_id_val,
                "cat_ra_deg":    float(row["ra"]),
                "cat_dec_deg":   float(row["dec"]),
                "match_file":    src_file,
                "match_ra_deg":  float(asc_row["ra"]),
                "match_dec_deg": float(asc_row["dec"]),
                "theta_arcsec":  float(sep),
            })
        else:
            results.append({
                "star_id":       star_id_val,
                "cat_ra_deg":    float(row["ra"]),
                "cat_dec_deg":   float(row["dec"]),
                "match_file":    "",
                "match_ra_deg":  np.nan,
                "match_dec_deg": np.nan,
                "theta_arcsec":  np.nan,
            })

    return pd.DataFrame(results)

# =========================
# UI
# =========================

with st.sidebar:
    st.subheader("1) Catálogo")
    cat_file = st.file_uploader("Catálogo (TXT/CSV/TSV)", type=["txt","csv","tsv"], key="catalog")
    st.caption("Detecta cabeceras ALFA/DELTA o RA/DEC; convierte a grados.")

    st.subheader("2) Archivos .ASC")
    asc_files = st.file_uploader(".ASC (uno o varios)", type=["asc","txt","dat"], accept_multiple_files=True, key="ascs")
    st.caption("Ignora líneas con '#'; separador por espacios/tabs; convierte a grados.")

    st.subheader("3) Matching")
    theta_arcsec = st.slider("Umbral de separación (θ) en arcsec", min_value=0.1, max_value=5.0, value=0.8, step=0.1)
    run_match = st.button("Ejecutar matching")

# Panel principal
cat_df_norm = None
if cat_file is not None:
    try:
        cat_df_raw = read_catalog(cat_file)
        st.success(f"Catálogo leído: {cat_df_raw.shape[0]} filas × {cat_df_raw.shape[1]} columnas")
        cat_df_norm = normalize_catalog(cat_df_raw)
        n_ok = cat_df_norm[["ra","dec"]].dropna().shape[0]
        st.info(f"Catálogo normalizado → RA/DEC en grados. Filas válidas: {n_ok}/{len(cat_df_norm)}")
        with st.expander("Vista previa de catálogo normalizado", expanded=False):
            st.dataframe(cat_df_norm.head(200), use_container_width=True)
        dl_cat = cat_df_norm.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar catálogo normalizado (CSV)", data=dl_cat, file_name="catalogo_normalizado.csv", mime="text/csv")
    except Exception as e:
        st.error(f"Error catálogo: {e}")

asc_norm_list = []
if asc_files:
    for up in asc_files:
        try:
            asc_raw = read_asc(up)
            asc_norm = normalize_asc(asc_raw)
            asc_norm_list.append((up.name, asc_norm))
            st.success(f"{up.name}: leído y normalizado ({asc_norm.shape[0]} filas)")
            with st.expander(f"Vista previa {up.name}", expanded=False):
                st.dataframe(asc_norm.head(100), use_container_width=True)
        except Exception as e:
            st.error(f"{up.name}: {e}")

# Matching
if run_match:
    if cat_df_norm is None:
        st.error("Subí y normalizá primero el **catálogo**.")
    elif not asc_norm_list:
        st.error("Subí al menos un archivo **.asc** normalizado.")
    else:
        try:
            res = match_catalog_to_ascs(cat_df_norm, asc_norm_list, theta_arcsec)
            st.success("Matching completado.")
            st.write(f"Coincidencias dentro de θ ≤ {theta_arcsec} arcsec: {(res['theta_arcsec'].notna()).sum()} / {len(res)}")
            st.dataframe(res, use_container_width=True)
            dl = res.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Descargar resultados (CSV)", data=dl, file_name="matching_resultados.csv", mime="text/csv")
        except Exception as e:
            st.error(f"Error en matching: {e}")
