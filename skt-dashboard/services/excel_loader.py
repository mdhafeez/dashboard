from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

from services.status_engine import classify_status


SECTION_SHEETS = ["SLPPI", "SLAD", "SLKD", "SLPD ", "SLID", "SLPS"]
MAIN_SHEETS = ["MasterList", "Utk analisis"]


def load_excel_to_rows(path: str | Path) -> list[dict]:
    path = Path(path)
    xls = pd.ExcelFile(path)
    psp_map = _load_psp_map(path, xls)
    actual_map = _load_actual_map(path, xls)

    frames = []
    for sheet in SECTION_SHEETS:
        if sheet in xls.sheet_names:
            frames.append(_read_sheet(path, sheet, psp_map, actual_map))

    if not frames and "MasterList" in xls.sheet_names:
        frames.append(_read_sheet(path, "MasterList", psp_map, actual_map))

    if not frames:
        return []

    df = pd.concat(frames, ignore_index=True)
    df = df[df["course_title"].notna() & (df["course_title"].astype(str).str.strip() != "")]
    df = df.drop_duplicates(subset=["course_title", "section", "planned_start_date", "planned_end_date"], keep="first")
    rows = []
    for _, record in df.iterrows():
        row = {key: _clean_value(value) for key, value in record.to_dict().items()}
        row["status"] = classify_status(row)
        rows.append(row)
    return rows


def _read_sheet(path: Path, sheet: str, psp_map: dict, actual_map: dict) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet)
    raw.columns = [_clean_column(c) for c in raw.columns]
    raw = raw.dropna(how="all")
    raw = raw[raw.apply(_has_course, axis=1)]

    out = pd.DataFrame()
    out["source_row"] = raw.index + 2
    out["source_sheet"] = sheet.strip()
    out["course_title"] = _pick(raw, ["kursus", "tajuk_kursus"])
    out["course_type"] = _pick(raw, ["jenis"])
    out["collaboration_type"] = _pick(raw, ["jenis_kolaborasi", "nama_agensi", "kampus"])
    out["planned_start_date"] = _pick(raw, ["tarikh_mula_rancang", "tarikh_mula"])
    out["planned_end_date"] = _pick(raw, ["tarikh_tamat_rancang", "tarikh_akhir", "tarikh_tamat"])
    out["actual_start_date"] = _pick(raw, ["tarikh_mula_sebenar"])
    out["actual_end_date"] = _pick(raw, ["tarikh_tamat_sebenar"])
    out["days"] = pd.to_numeric(_pick(raw, ["bilangan_hari"]), errors="coerce")
    out["target_participants"] = pd.to_numeric(_pick(raw, ["anggaran_bilangan_peserta", "bilangan_peserta"]), errors="coerce").fillna(0)
    out["actual_participants"] = pd.NA
    out["target_group"] = _pick(raw, ["kumpulan_sasaran"])
    out["budget"] = pd.to_numeric(_pick(raw, ["anggaran_bajet_rm", "anggaran_bajet"]), errors="coerce").fillna(0)
    out["section"] = _pick(raw, ["seksyen"]).replace({"SKLD": "SLKD", "SPPD": "SLPD"})
    out["coordinator"] = _pick(raw, ["penyelaras", "penceramah"])
    out["paid_status"] = _pick(raw, ["berbayar_tidak_berbayar"])
    out["source_status"] = _pick(raw, ["status_selesai_dalam_tindakan"])
    out["remarks"] = _merge_text(raw, ["catatan_tambah_batal_tangguh", "justifikasi_ulasan_status", "catatan_justifikasi"])
    out["mode"] = _pick(raw, ["mod_bersemuka_dalam_talian_hibrid"])
    out["secretary"] = _pick(raw, ["setiausaha_kursus_suk"])
    out["level"] = _pick(raw, ["tahap_1_awareness_2_asas_3_pertengahan_4_lanjutan"])
    out["bitara_program"] = _pick(raw, ["program_bitara_ya_tidak"])
    out["cluster_training"] = _pick(raw, ["kluster_latihan"])
    out["focus_area"] = _pick(raw, ["7_bidang_tujahan"])

    out["planned_start_date"] = pd.to_datetime(out["planned_start_date"], errors="coerce")
    out["planned_end_date"] = pd.to_datetime(out["planned_end_date"], errors="coerce")
    out["actual_start_date"] = pd.to_datetime(out["actual_start_date"], errors="coerce")
    out["actual_end_date"] = pd.to_datetime(out["actual_end_date"], errors="coerce")
    out["month"] = out["planned_start_date"].dt.strftime("%b").fillna(_pick(raw, ["bulan"]))
    out["month_year"] = out["planned_start_date"].dt.strftime("%b-%Y")

    titles = out["course_title"].fillna("").map(_norm_title)
    out["psp_category"] = titles.map(psp_map).fillna(_pick(raw, ["kategori_psp"]))
    out["actual_participants"] = titles.map(actual_map)
    out["status_override"] = pd.NA
    out["user_remarks"] = pd.NA

    for col in ["planned_start_date", "planned_end_date", "actual_start_date", "actual_end_date"]:
        out[col] = out[col].dt.strftime("%Y-%m-%d")
    return out


def _load_psp_map(path: Path, xls: pd.ExcelFile) -> dict:
    if "PSP" not in xls.sheet_names:
        return {}
    df = pd.read_excel(path, sheet_name="PSP")
    df.columns = [_clean_column(c) for c in df.columns]
    return {_norm_title(r["kursus"]): r.get("kategori_psp") for _, r in df.iterrows() if pd.notna(r.get("kursus"))}


def _load_actual_map(path: Path, xls: pd.ExcelFile) -> dict:
    actual = {}
    for sheet in MAIN_SHEETS:
        if sheet not in xls.sheet_names:
            continue
        df = pd.read_excel(path, sheet_name=sheet)
        df.columns = [_clean_column(c) for c in df.columns]
        if "kursus" not in df.columns or "jumlah_peserta_sebenar" not in df.columns:
            continue
        for _, row in df.iterrows():
            title = _norm_title(row.get("kursus"))
            val = pd.to_numeric(row.get("jumlah_peserta_sebenar"), errors="coerce")
            if title and pd.notna(val):
                actual[title] = float(val)
    return actual


def _clean_column(value) -> str:
    text = str(value).strip().lower().replace("\n", " ")
    text = re.sub(r"\(rm\)", "rm", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _pick(df: pd.DataFrame, names: list[str]) -> pd.Series:
    for name in names:
        if name in df.columns:
            return df[name]
    return pd.Series([pd.NA] * len(df), index=df.index)


def _merge_text(df: pd.DataFrame, names: list[str]) -> pd.Series:
    parts = [_pick(df, [name]).fillna("").astype(str).str.strip() for name in names]
    if not parts:
        return pd.Series([pd.NA] * len(df), index=df.index)
    merged = parts[0]
    for part in parts[1:]:
        merged = (merged + " " + part).str.strip()
    return merged.replace("", pd.NA)


def _has_course(row) -> bool:
    value = row.get("kursus", row.get("tajuk_kursus", ""))
    if pd.isna(value):
        return False
    text = str(value).strip()
    return bool(text) and text.upper() not in {"JANUARI", "FEBRUARI", "MAC", "APRIL", "MEI", "JUN", "JULAI", "OGOS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DISEMBER"}


def _norm_title(value) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _clean_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value
