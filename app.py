import io
import re
import sys
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
    "Este lector intenta estandarizar las columnas de coordenadas del catálogo "
    "para producir siempre `ra` y `dec` en **grados**."
)

# ----------------------------
# Utilidades
# ----------------------------

# Nombres alternativos comunes para RA y DEC
RA_ALIASES = {
    "ra", "raj2000", "ra_j2000", "ra_deg", "ra (deg)", "ra(deg)",
    "alpha", "α", "right_ascension", "ra_hours", "ra_h", "ra_hms",
    "ra_h:m:s", "ra_hms_str", "rahour", "ra_hour", "alfa", "ra[deg]"
}
DEC_ALIASES = {
    "dec", "de", "dej2000", "dec_j2000", "dec_deg", "dec (deg)", "dec(deg)",
    "delta", "δ", "declination", "dec_d", "dec_dms", "dec_d:m:s",
    "dec_dms_str", "decl", "dec[deg]"
}

# Regex básico para detectar sexagesimal tipo "12:34:56.7" o "12 34 56.7" o "12h34m56.7s"
SEXAGESIMAL_RX = re.compile(
    r"^\s*([+\-]?\d{1,3})[^0-9+\-]+\s*(\d{1,2})[^0-9]+\s*(\d{1,2}(?:\.\d*)?)\s*$"
)


def _strip_and_lower(s: str) -> str:
    return re.sub(r"\s+", "", s.strip().lower()) if isinstance(s, str) else s


def guess_sep(sample: bytes) -> str:
    """Intenta adivinar separador para texto tabular."""
    try:
        head = sample.decode("utf-8", errors="ignore")
    except Exception:
        head = sample.decode("latin-1", errors="ignore")

    # Conteo simple de candidatos
    counts = {",": head.count(","), ";": head.count(";"), "\t": head.count("\t")}
    # Si hay cabecera con ; o , suele destacarse
    sep = max(counts, key=counts.get)
    # Si no hay separadores claros, que pandas detecte
    if counts[sep] == 0:
        return None
    return "\t" if sep == "\t" else sep


def read_table_auto(file) -> pd.DataFrame:
    """Lectura robusta con separador autodetectado y utf-8/latin-1 fallback."""
    raw = file.read()
    if isinstance(raw, bytes):
        sample = raw[:16384]
    else:
        # UploadedFile puede ser un buffer; obtén bytes
        raw = raw.getvalue()
        sample = raw[:16384]

    sep = guess_sep(sample)  # None => que pandas intente con engine='python', sep=None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            buf = io.BytesIO(raw)
            if sep is None:
                df = pd.read_csv(buf, sep=None, engine="python")
            else:
                df = pd.read_csv(buf, sep=sep)
            return df
        except Exception:
            continue
    raise ValueError("No se pudo leer el archivo: problema de codificación o formato.")


def find_column(df: pd.DataFrame, candidates: set) -> Optional[str]:
    """Encuentra la primera columna cuyo nombre normalizado coincida con los candidatos."""
    norm_map = {col: _strip_and_lower(str(col)) for col in df.columns}
    # Quitar unidades entre corchetes o paréntesis al normalizar
    clean_map = {col: re.sub(r"[\[\(].*?[\]\)]", "", norm).strip() for col, norm in norm_map.items()}

    for col, norm in clean_map.items():
        # coincidencia directa
        if norm in candidates:
            return col
        # variantes típicas tipo "ra_deg", "ra(deg)", etc.
        base = norm.replace("_", "").replace(" ", "")
        if base in candidates:
            return col
        # Algunos catálogos vienen como "rajd", "dej2000"
        if base.endswith("j2000"):
            base2 = base.replace("j2000", "")
            if base2 in candidates:
                return col
    return None


def is_sexagesimal_series(s: pd.Series) -> bool:
    """Heurística: ¿La mayoría de valores parecen sexagesimales?"""
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


def parse_ra_dec_to_deg(
    ra_series: pd.Series,
    dec_series: pd.Series,
) -> Tuple[pd.Series, pd.Series]:
    """
    Convierte RA y DEC a grados intentando:
    - Sexagesimal (strings con : o h/m/s)
    - Números en horas (RA ≤ 24) -> grados * 15
    - Números ya en grados (RA ≤ 360, DEC ≤ 90)
    """
    # Si ambas columnas parecen sexagesimales, usar SkyCoord con unit=(hourangle, deg)
    if is_sexagesimal_series(ra_series) or is_sexagesimal_series(dec_series):
        # Convertir a strings (Astropy tolera distintos separadores)
        ra_str = ra_series.astype(str).replace({"nan": np.nan})
        dec_str = dec_series.astype(str).replace({"nan": np.nan})
        coords = []
        for ra_v, dec_v in zip(ra_str, dec_str):
            if pd.isna(ra_v) or pd.isna(dec_v):
                coords.append((np.nan, np.nan))
                continue
            try:
                c = SkyCoord(ra=ra_v, dec=dec_v, unit=(u.hourangle, u.deg), frame="icrs")
                coords.append((float(c.ra.deg), float(c.dec.deg)))
            except Exception:
                # Intento alternativo: ambos como angulos sexagesimales con dms/hms
                try:
                    c = SkyCoord(Angle(ra_v, unit=u.hourangle), Angle(dec_v, unit=u.deg), frame="icrs")
                    coords.append((float(c.ra.deg), float(c.dec.deg)))
                except Exception:
                    coords.append((np.nan, np.nan))
        out = pd.DataFrame(coords, columns=["ra", "dec"])
        return out["ra"], out["dec"]

    # Si son numéricos, decidir horas vs grados por rango
    ra_num = pd.to_numeric(ra_series, errors="coerce")
    dec_num = pd.to_numeric(dec_series, errors="coerce")

    # Heurística:
    # - Si RA máx <= 24.5 => horas; convertir a grados
    # - Si RA máx <= 360 => ya grados
    # - DEC debe estar en [-90, +90] en grados; si no, intentar parseo fino
    ra_max = np.nanmax(ra_num.values) if np.any(~np.isnan(ra_num.values)) else np.nan
    dec_max = np.nanmax(np.abs(dec_num.values)) if np.any(~np.isnan(dec_num.values)) else np.nan

    # Caso: RA claro en horas
    if not np.isnan(ra_max) and ra_max <= 24.5:
        ra_deg = ra_num * 15.0
    else:
        # Asumir grados (si algunos están >360, marcar NaN)
        ra_deg = ra_num.where((ra_num >= 0) & (ra_num <= 360), np.nan)

    # DEC debe estar en [-90, 90]
    dec_deg = dec_num.where((dec_num >= -90) & (dec_num <= 90), np.nan)

    return ra_deg, dec_deg


def normalize_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """
    Intenta producir columnas 'ra' y 'dec' en grados desde un DataFrame arbitrario.
    No elimina columnas originales; añade/renombra según corresponda.
    """
    if df is None or df.empty:
        raise ValueError("El archivo parece vacío.")

    # Buscar columnas candidatas
    ra_col = find_column(df, RA_ALIASES) or find_column(df, {c + "_deg" for c in RA_ALIASES})
    dec_col = find_column(df, DEC_ALIASES) or find_column(df, {c + "_deg" for c in DEC_ALIASES})

    if ra_col is None or dec_col is None:
        # Intento: buscar por patrones más laxos
        lowered = {_strip_and_lower(c): c for c in df.columns}
        # RA: cualquier cosa que contenga "ra" o "alpha" o "right"
        ra_guess = next((orig for norm, orig in lowered.items() if any(k in norm for k in ["ra", "alpha", "rightasc"])), None)
        # DEC: "dec", "delta", "decl"
        dec_guess = next((orig for norm, orig in lowered.items() if any(k in norm for k in ["dec", "delta", "decl"])), None)
        ra_col = ra_col or ra_guess
        dec_col = dec_col or dec_guess

    if ra_col is None or dec_col is None:
        raise ValueError(
            "No se encontraron columnas de RA/DEC. "
            "Intentá especificar manualmente las columnas en el catálogo."
        )

    # Crear ra, dec en grados
    ra_deg, dec_deg = parse_ra_dec_to_deg(df[ra_col], df[dec_col])

    # Si todavía hay NaN masivos, intentar último recurso:
    # - Si RA estaba en grados pero < 24 en muchos casos (catálogo extraño), probar *15
    frac_nan = (ra_deg.isna() | dec_deg.isna()).mean()
    if frac_nan > 0.5:
        # reintento forzado: tratar RA como horas
        ra_deg2 = pd.to_numeric(df[ra_col], errors="coerce") * 15.0
        dec_deg2 = pd.to_numeric(df[dec_col], errors="coerce")
        if (dec_deg2.between(-90, 90).mean() > 0.5) and (ra_deg2.between(0, 360).mean() > 0.5):
            ra_deg, dec_deg = ra_deg2, dec_deg2

    out = df.copy()
    out["ra"] = ra_deg
    out["dec"] = dec_deg

    # Validación final
    if out["ra"].isna().all() or out["dec"].isna().all():
        raise ValueError(
            "Catálogo inválido: no fue posible convertir RA/DEC a grados. "
            "Revisá el formato (horas, grados o sexagesimal) y los nombres de columna."
        )

    return out


# ----------------------------
# UI de Streamlit
# ----------------------------

with st.sidebar:
    st.subheader("1) Cargar catálogo")
    file = st.file_uploader("Archivo de catálogo (CSV/TSV/TXT)", type=["csv", "tsv", "txt"])
    st.caption("Separador y codificación se detectan automáticamente.")

    st.subheader("2) Opciones")
    show_preview = st.checkbox("Mostrar vista previa (primeras 200 filas)", value=True)

if file is not None:
    try:
        df_raw = read_table_auto(file)
        st.success(f"Archivo leído: {df_raw.shape[0]} filas × {df_raw.shape[1]} columnas")

        # Normalizar a ra/dec (grados)
        df_norm = normalize_catalog(df_raw)

        # Reporte
        n_ok = df_norm[["ra", "dec"]].dropna().shape[0]
        st.info(f"Coordenadas normalizadas. Filas con RA/DEC válidos: **{n_ok}** / {df_norm.shape[0]}")

        if show_preview:
            st.write("**Vista previa del catálogo normalizado (primeras 200 filas):**")
            st.dataframe(df_norm.head(200), use_container_width=True)

        # Botón de descarga del catálogo normalizado
        csv_bytes = df_norm.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar catálogo normalizado (CSV)",
            data=csv_bytes,
            file_name="catalogo_normalizado.csv",
            mime="text/csv",
        )

        st.success("Listo. Las columnas `ra` y `dec` están en grados y disponibles para los siguientes pasos de la app.")

    except Exception as e:
        st.error(f"Error leyendo catálogo: {e}")
        st.stop()
else:
    st.warning("Subí un archivo de catálogo para comenzar.")
