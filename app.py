import io
import re
import numpy as np
import pandas as pd
import streamlit as st
from typing import Optional, Tuple

from astropy.coordinates import SkyCoord, Angle
import astropy.units as u

# ----------------------------
# Configuración de la página
# ----------------------------
st.set_page_config(page_title="Carbon Stars • Catálogo", layout="wide")
st.title("Carbon Stars v0.4.0")
st.write(
    "Este lector estandariza columnas de coordenadas para producir siempre `ra` y `dec` en **grados**."
)

# ----------------------------
# Utilidades
# ----------------------------

# Aliases para RA y DEC (incluyendo español)
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
    # quita unidades entre paréntesis/corchetes y espacios/underscores
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
    # Si parecen sexagesimales, usar Astropy con (hourangle, deg)
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

    # Tratamiento numérico por rangos
    ra_num = pd.to_numeric(ra_series, errors="coerce")
    dec_num = pd.to_numeric(dec_series, errors="coerce")
    ra_max = np.nanmax(ra_num.values) if np.any(~np.isnan(ra_num.values)) else np.nan

    # RA en horas si el máx ≤ 24.5
    if not np.isnan(ra_max) and ra_max <= 24.5:
        ra_deg = ra_num * 15.0
    else:
        ra_deg = ra_num.where((ra_num >= 0) & (ra_num <= 360), np.nan)
    dec_deg = dec_num.where((dec_num >= -90) & (dec_num <= 90), np.nan)
    return ra_deg, dec_deg

def read_table_general(uploaded) -> pd.DataFrame:
    """
    Lector robusto:
    - Si detecta una fila con ALFA/DELTA (como tu catálogo), empieza a leer desde ahí.
    - Acepta separadores por tab o por espacios múltiples.
    - Fallback a autodetección genérica.
    """
    raw = uploaded.read()
    if not isinstance(raw, (bytes, bytearray)):
        raw = uploaded.getvalue()

    # Decodifica
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc, errors="strict")
            break
        except Exception:
            text = None
    if text is None:
        raise ValueError("No se pudo leer el archivo: problema de codificación o formato.")

    # 1) ¿Hay fila de cabecera con ALFA/DELTA? (caso Merlo)
    lines = text.splitlines()
    header_idx = None
    for i, l in enumerate(lines):
        if ("ALFA" in l.upper() or "RA" in l.upper()) and ("DELTA" in l.upper() or "DEC" in l.upper()):
            # Evitar falsos positivos en líneas sin campos
            if re.search(r"[A-ZÁÉÍÓÚÑ]+\s+.*(ALFA|RA).*(DELTA|DEC)", l.upper()):
                header_idx = i
                break

    if header_idx is not None:
        data_block = "\n".join(lines[header_idx:])
        # separador: tabs o grupos de ≥2 espacios
        try:
            df = pd.read_csv(io.StringIO(data_block), sep=r"\s*\t\s*|\s{2,}", engine="python")
            return df
        except Exception as e:
            # Intento alternativo: fixed-width
            try:
                df = pd.read_fwf(io.StringIO(data_block))
                return df
            except Exception:
                pass  # seguirá al fallback genérico

    # 2) Fallback genérico (CSV/TSV)
    try:
        return pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
    except Exception:
        # Prueba con separadores comunes
        for sep in ("\t", ",", ";", r"\s{2,}"):
            try:
                return pd.read_csv(io.BytesIO(raw), sep=sep, engine="python")
            except Exception:
                continue
    raise ValueError("No se pudo leer el archivo: problema de codificación o formato.")

def normalize_catalog(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("El archivo parece vacío.")

    # Buscar columnas RA/DEC (incluye español)
    ra_col = find_column(df, RA_ALIASES)
    dec_col = find_column(df, DEC_ALIASES)

    # Si no, heurística por contenidos
    if ra_col is None or dec_col is None:
        lowered = {_strip_and_lower(c): c for c in df.columns}
        ra_guess = next((orig for norm, orig in lowered.items() if any(k in norm for k in ["ra", "alfa", "alpha", "right asc"])), None)
        dec_guess = next((orig for norm, orig in lowered.items() if any(k in norm for k in ["dec", "delta", "decl"])), None)
        ra_col = ra_col or ra_guess
        dec_col = dec_col or dec_guess

    if ra_col is None or dec_col is None:
        raise ValueError(
            "No se encontraron columnas de RA/DEC. "
            "Revisá que el catálogo tenga ALFA/DELTA (o RA/DEC)."
        )

    # Convertir a grados
    ra_deg, dec_deg = parse_ra_dec_to_deg(df[ra_col], df[dec_col])

    # Reintento forzado si hubo demasiados NaN: asumir RA en horas
    frac_nan = (ra_deg.isna() | dec_deg.isna()).mean()
    if frac_nan > 0.5:
        ra_num = pd.to_numeric(df[ra_col], errors="coerce")
        dec_num = pd.to_numeric(df[dec_col], errors="coerce")
        ra_deg2 = ra_num * 15.0
        dec_deg2 = dec_num
        if (dec_deg2.between(-90, 90).mean() > 0.5) and (ra_deg2.between(0, 360).mean() > 0.5):
            ra_deg, dec_deg = ra_deg2, dec_deg2

    out = df.copy()
    out["ra"] = ra_deg
    out["dec"] = dec_deg

    if out["ra"].isna().all() or out["dec"].isna().all():
        raise ValueError(
            "Catálogo inválido: no fue posible convertir RA/DEC a grados. "
            "Revisá el formato (sexagesimal, horas o grados) y los nombres de columna."
        )
    return out

# ----------------------------
# UI de Streamlit
# ----------------------------
with st.sidebar:
    st.subheader("1) Cargar catálogo")
    file = st.file_uploader("Archivo de catálogo (TXT/CSV/TSV)", type=["txt", "csv", "tsv"])
    st.caption("Se detectan cabeceras estilo 'ALFA/DELTA' y separadores (tab/espacios).")

    st.subheader("2) Opciones")
    show_preview = st.checkbox("Mostrar vista previa (primeras 200 filas)", value=True)

if file is not None:
    try:
        df_raw = read_table_general(file)
        st.success(f"Archivo leído: {df_raw.shape[0]} filas × {df_raw.shape[1]} columnas")

        df_norm = normalize_catalog(df_raw)

        n_ok = df_norm[["ra", "dec"]].dropna().shape[0]
        st.info(f"Coordenadas normalizadas. Filas con RA/DEC válidos: **{n_ok}** / {df_norm.shape[0]}")

        if show_preview:
            st.write("**Vista previa del catálogo normalizado (primeras 200 filas):**")
            st.dataframe(df_norm.head(200), use_container_width=True)

        csv_bytes = df_norm.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar catálogo normalizado (CSV)",
            data=csv_bytes,
            file_name="catalogo_normalizado.csv",
            mime="text/csv",
        )
        st.success("Listo. `ra` y `dec` están en grados y listas para el pipeline.")

    except Exception as e:
        st.error(f"Error leyendo catálogo: {e}")
        st.stop()
else:
    st.warning("Subí un archivo de catálogo para comenzar.")
