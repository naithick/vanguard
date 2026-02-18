"""
GreenRoute Mesh v2 — Report Generator

Generates air-quality summary reports for a given period (day / month / quarter).
Outputs: JSON summary, Excel (.xlsx), PDF.

Usage from API:
  GET /api/reports/generate?period=day                → JSON summary
  GET /api/reports/generate?period=month&format=excel  → .xlsx download
  GET /api/reports/generate?period=quarter&format=pdf  → .pdf download
"""

import io
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

log = logging.getLogger("greenroute.report_gen")


# ── Period helpers ────────────────────────────────────────────────────────────

def _period_range(period: str, ref_date: datetime = None) -> Tuple[datetime, datetime, str]:
    """
    Return (start, end, label) for the requested period.
    period: 'day' | 'week' | 'month' | 'quarter' | 'year'
    """
    now = ref_date or datetime.now(timezone.utc)

    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        label = start.strftime("%Y-%m-%d")
    elif period == "week":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=7)
        label = f"Week of {start.strftime('%Y-%m-%d')}"
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # First day of next month
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        label = start.strftime("%B %Y")
    elif period == "quarter":
        q = (now.month - 1) // 3
        start = now.replace(month=q * 3 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_month = q * 3 + 4
        if end_month > 12:
            end = start.replace(year=start.year + 1, month=end_month - 12)
        else:
            end = start.replace(month=end_month)
        label = f"Q{q + 1} {start.year}"
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + 1)
        label = str(start.year)
    else:
        # Default to last 24h
        end = now
        start = now - timedelta(hours=24)
        label = f"Last 24h ({start.strftime('%m/%d %H:%M')} – {end.strftime('%m/%d %H:%M')})"

    return start, end, label


# ── Data fetching ─────────────────────────────────────────────────────────────

def _fetch_readings(db, start: datetime, end: datetime, device_id: str = None) -> pd.DataFrame:
    """Fetch processed_data for a period as a DataFrame."""
    q = (
        db.client.table("processed_data")
        .select("*")
        .gte("recorded_at", start.isoformat())
        .lt("recorded_at", end.isoformat())
        .order("recorded_at", desc=False)
    )
    if device_id:
        q = q.eq("device_id", device_id)

    # Paginate (Supabase default limit is 1000)
    all_rows = []
    offset = 0
    page_size = 1000
    while True:
        res = q.range(offset, offset + page_size - 1).execute()
        if not res.data:
            break
        all_rows.extend(res.data)
        if len(res.data) < page_size:
            break
        offset += page_size

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True)
    return df


def _fetch_alerts(db, start: datetime, end: datetime) -> List[Dict]:
    """Alerts that were created in the period."""
    res = (
        db.client.table("alerts")
        .select("*")
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []


def _fetch_hotspots(db, start: datetime, end: datetime) -> List[Dict]:
    """Hotspots active during the period."""
    res = (
        db.client.table("identified_hotspots")
        .select("*")
        .gte("last_updated_at", start.isoformat())
        .order("last_updated_at", desc=False)
        .execute()
    )
    return res.data or []


# ── Summary computation ──────────────────────────────────────────────────────

def _safe(val):
    """Convert NaN / inf to None for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return round(val, 2) if isinstance(val, float) else val


def generate_summary(db, period: str = "day", device_id: str = None) -> Dict:
    """
    Build a JSON-ready summary for the given period.
    Returns dict with: period_info, overview, per_device, alerts, hotspots
    """
    start, end, label = _period_range(period)
    df = _fetch_readings(db, start, end, device_id)
    alerts = _fetch_alerts(db, start, end)
    hotspots = _fetch_hotspots(db, start, end)

    summary = {
        "period": {
            "type": period,
            "label": label,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if df.empty:
        summary["overview"] = {"total_readings": 0, "message": "No data for this period"}
        summary["per_device"] = []
        summary["alerts"] = {"total": len(alerts), "items": alerts[:20]}
        summary["hotspots"] = {"total": len(hotspots), "items": hotspots[:20]}
        return summary

    # ── Overall stats ─────────────────────────────────────────────────
    num_cols = ["aqi_value", "pm25_ugm3", "co_ppm", "co2_ppm",
                "temperature_c", "humidity_pct", "heat_index_c", "toxic_gas_index"]

    overview = {
        "total_readings": len(df),
        "devices_active": int(df["device_id"].nunique()),
        "time_span_hours": round((df["recorded_at"].max() - df["recorded_at"].min()).total_seconds() / 3600, 1),
    }

    for col in num_cols:
        if col in df.columns and df[col].notna().any():
            overview[f"{col}_avg"] = _safe(df[col].mean())
            overview[f"{col}_max"] = _safe(df[col].max())
            overview[f"{col}_min"] = _safe(df[col].min())

    # AQI distribution
    if "aqi_category" in df.columns:
        dist = df["aqi_category"].value_counts().to_dict()
        overview["aqi_distribution"] = {k: int(v) for k, v in dist.items()}

    # Respiratory risk distribution
    if "respiratory_risk_label" in df.columns:
        risk = df["respiratory_risk_label"].value_counts().to_dict()
        overview["respiratory_risk_distribution"] = {k: int(v) for k, v in risk.items()}

    summary["overview"] = overview

    # ── Per-device breakdown ──────────────────────────────────────────
    per_device = []
    for dev_id, grp in df.groupby("device_id"):
        entry = {
            "device_id": dev_id,
            "readings": len(grp),
        }
        for col in ["aqi_value", "pm25_ugm3", "co_ppm", "temperature_c", "humidity_pct"]:
            if col in grp.columns and grp[col].notna().any():
                entry[f"{col}_avg"] = _safe(grp[col].mean())
                entry[f"{col}_max"] = _safe(grp[col].max())
        if "aqi_category" in grp.columns:
            entry["worst_category"] = grp.loc[grp["aqi_value"].idxmax(), "aqi_category"] if grp["aqi_value"].notna().any() else None
        per_device.append(entry)

    per_device.sort(key=lambda x: x.get("aqi_value_avg", 0) or 0, reverse=True)
    summary["per_device"] = per_device

    # ── Alerts summary ────────────────────────────────────────────────
    alert_summary = {"total": len(alerts)}
    if alerts:
        sev_counts = {}
        for a in alerts:
            s = a.get("severity", "unknown")
            sev_counts[s] = sev_counts.get(s, 0) + 1
        alert_summary["by_severity"] = sev_counts
        alert_summary["items"] = alerts[:20]
    summary["alerts"] = alert_summary

    # ── Hotspots summary ──────────────────────────────────────────────
    hs_summary = {"total": len(hotspots)}
    if hotspots:
        active = [h for h in hotspots if h.get("is_active")]
        hs_summary["active"] = len(active)
        hs_summary["items"] = hotspots[:20]
    summary["hotspots"] = hs_summary

    return summary


# ── Excel export ──────────────────────────────────────────────────────────────

def generate_excel(db, period: str = "day", device_id: str = None) -> io.BytesIO:
    """
    Generate a multi-sheet Excel workbook.
    Sheets: Summary, Readings, Alerts, Hotspots
    """
    start, end, label = _period_range(period)
    df = _fetch_readings(db, start, end, device_id)
    alerts = _fetch_alerts(db, start, end)
    hotspots = _fetch_hotspots(db, start, end)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # ── Summary sheet ─────────────────────────────────────────────
        summary_data = {
            "Metric": ["Period", "Label", "Start", "End", "Total Readings",
                       "Active Devices", "Total Alerts", "Active Hotspots"],
            "Value": [period, label, str(start)[:19], str(end)[:19],
                      len(df), df["device_id"].nunique() if not df.empty else 0,
                      len(alerts), len([h for h in hotspots if h.get("is_active")])]
        }

        if not df.empty:
            for col in ["aqi_value", "pm25_ugm3", "co_ppm", "temperature_c", "humidity_pct"]:
                if col in df.columns and df[col].notna().any():
                    summary_data["Metric"].append(f"Avg {col}")
                    summary_data["Value"].append(round(df[col].mean(), 2))
                    summary_data["Metric"].append(f"Max {col}")
                    summary_data["Value"].append(round(df[col].max(), 2))

        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

        # ── Readings sheet ────────────────────────────────────────────
        if not df.empty:
            export_cols = [
                "recorded_at", "device_id", "aqi_value", "aqi_category",
                "pm25_ugm3", "co_ppm", "co2_ppm", "temperature_c",
                "humidity_pct", "heat_index_c", "toxic_gas_index",
                "respiratory_risk_label", "latitude", "longitude",
            ]
            available = [c for c in export_cols if c in df.columns]
            df[available].to_excel(writer, sheet_name="Readings", index=False)

            # ── Per-device sheet ──────────────────────────────────────
            agg = df.groupby("device_id").agg(
                readings=("aqi_value", "count"),
                aqi_avg=("aqi_value", "mean"),
                aqi_max=("aqi_value", "max"),
                pm25_avg=("pm25_ugm3", "mean"),
                pm25_max=("pm25_ugm3", "max"),
                temp_avg=("temperature_c", "mean"),
            ).round(2).reset_index()
            agg.to_excel(writer, sheet_name="Per Device", index=False)
        else:
            pd.DataFrame({"Info": ["No readings for this period"]}).to_excel(
                writer, sheet_name="Readings", index=False
            )

        # ── Alerts sheet ──────────────────────────────────────────────
        if alerts:
            adf = pd.DataFrame(alerts)
            alert_cols = [c for c in ["created_at", "device_id", "alert_type", "severity",
                                       "title", "message", "resolved_at"] if c in adf.columns]
            adf[alert_cols].to_excel(writer, sheet_name="Alerts", index=False)

        # ── Hotspots sheet ────────────────────────────────────────────
        if hotspots:
            hdf = pd.DataFrame(hotspots)
            hs_cols = [c for c in ["first_detected_at", "latitude", "longitude", "location",
                                    "primary_pollutant", "peak_aqi", "peak_value",
                                    "severity_level", "contributing_readings",
                                    "is_active", "resolved_at"] if c in hdf.columns]
            hdf[hs_cols].to_excel(writer, sheet_name="Hotspots", index=False)

    buf.seek(0)
    return buf


# ── PDF export ────────────────────────────────────────────────────────────────

def generate_pdf(db, period: str = "day", device_id: str = None) -> io.BytesIO:
    """
    Generate a styled PDF summary report.
    """
    from fpdf import FPDF

    start, end, label = _period_range(period)
    df = _fetch_readings(db, start, end, device_id)
    alerts = _fetch_alerts(db, start, end)
    hotspots = _fetch_hotspots(db, start, end)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Title ─────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(46, 125, 50)  # green
    pdf.cell(0, 14, "GreenRoute Mesh", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"Air Quality Report — {label}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generated: {now_str}   |   Period: {str(start)[:16]} → {str(end)[:16]}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ── Helper: section heading ───────────────────────────────────────
    def heading(text):
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(33, 33, 33)
        pdf.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(46, 125, 50)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 180, pdf.get_y())
        pdf.ln(3)

    def kv_row(key, value):
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(65, 6, key)
        pdf.set_text_color(33, 33, 33)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, str(value), new_x="LMARGIN", new_y="NEXT")

    # ── Overview ──────────────────────────────────────────────────────
    heading("Overview")
    kv_row("Total Readings", len(df))
    kv_row("Active Devices", df["device_id"].nunique() if not df.empty else 0)
    kv_row("Alerts in Period", len(alerts))
    kv_row("Hotspots Detected", len(hotspots))

    if not df.empty:
        for col, name in [
            ("aqi_value", "AQI"),
            ("pm25_ugm3", "PM2.5 (µg/m³)"),
            ("co_ppm", "CO (ppm)"),
            ("temperature_c", "Temperature (°C)"),
            ("humidity_pct", "Humidity (%)"),
        ]:
            if col in df.columns and df[col].notna().any():
                avg = round(df[col].mean(), 1)
                mx = round(df[col].max(), 1)
                mn = round(df[col].min(), 1)
                kv_row(f"{name} (avg / max / min)", f"{avg}  /  {mx}  /  {mn}")

        # AQI distribution
        if "aqi_category" in df.columns:
            pdf.ln(4)
            heading("AQI Distribution")
            dist = df["aqi_category"].value_counts()
            for cat, cnt in dist.items():
                pct = round(cnt / len(df) * 100, 1)
                kv_row(f"  {cat}", f"{cnt} readings ({pct}%)")

    # ── Per-device table ──────────────────────────────────────────────
    if not df.empty:
        pdf.ln(4)
        heading("Per-Device Summary")

        # Table header
        col_widths = [50, 22, 22, 22, 22, 22, 22]
        headers = ["Device", "Readings", "AQI avg", "AQI max", "PM2.5 avg", "Temp avg", "Risk"]
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(240, 240, 240)
        for w, h in zip(col_widths, headers):
            pdf.cell(w, 7, h, border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(33, 33, 33)
        for dev_id, grp in df.groupby("device_id"):
            short_id = dev_id[:18] if len(dev_id) > 18 else dev_id
            aqi_avg = round(grp["aqi_value"].mean(), 1) if grp["aqi_value"].notna().any() else "—"
            aqi_max = round(grp["aqi_value"].max(), 1) if grp["aqi_value"].notna().any() else "—"
            pm_avg = round(grp["pm25_ugm3"].mean(), 1) if "pm25_ugm3" in grp and grp["pm25_ugm3"].notna().any() else "—"
            t_avg = round(grp["temperature_c"].mean(), 1) if "temperature_c" in grp and grp["temperature_c"].notna().any() else "—"
            # Worst risk
            risk = "—"
            if "respiratory_risk_label" in grp.columns:
                risk = grp["respiratory_risk_label"].mode().iloc[0] if not grp["respiratory_risk_label"].isna().all() else "—"

            row = [short_id, str(len(grp)), str(aqi_avg), str(aqi_max), str(pm_avg), str(t_avg), str(risk)]
            for w, val in zip(col_widths, row):
                pdf.cell(w, 6, val, border=1)
            pdf.ln()

    # ── Alerts ────────────────────────────────────────────────────────
    if alerts:
        pdf.ln(4)
        heading(f"Alerts ({len(alerts)})")
        pdf.set_font("Helvetica", "", 9)
        for a in alerts[:15]:
            sev = (a.get("severity") or "").upper()
            title = a.get("title", "")[:60]
            ts = (a.get("created_at") or "")[:16]
            pdf.set_text_color(33, 33, 33)
            pdf.cell(0, 5, f"[{sev}] {title}  ({ts})", new_x="LMARGIN", new_y="NEXT")

    # ── Hotspots ──────────────────────────────────────────────────────
    if hotspots:
        pdf.ln(4)
        heading(f"Hotspots ({len(hotspots)})")
        pdf.set_font("Helvetica", "", 9)
        for h in hotspots[:10]:
            loc = h.get("location") or f"({h.get('latitude')}, {h.get('longitude')})"
            pollutant = h.get("primary_pollutant", "?")
            aqi = h.get("peak_aqi", "?")
            active = "ACTIVE" if h.get("is_active") else "RESOLVED"
            pdf.set_text_color(33, 33, 33)
            pdf.cell(0, 5, f"{loc} — {pollutant} peak AQI {aqi} [{active}]", new_x="LMARGIN", new_y="NEXT")

    # ── Footer ────────────────────────────────────────────────────────
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "GreenRoute Mesh v2 — Automated Air Quality Report", new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf
