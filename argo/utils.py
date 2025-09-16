import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# try import argopy
try:
    from argopy import DataFetcher as ArgoDataFetcher
    HAS_ARGOPY = True
except Exception:
    HAS_ARGOPY = False

def _filter_by_bbox_and_time(df, bbox, period_num=5, period_unit="years"):
    lon_min, lon_max, lat_min, lat_max = bbox
    df = df[(df["lon"] >= lon_min) & (df["lon"] <= lon_max) & (df["lat"] >= lat_min) & (df["lat"] <= lat_max)]
    # filter by time relative window if period specified
    now = pd.Timestamp.utcnow()
    if period_unit and period_num:
        if period_unit.startswith("year"):
            start = now - pd.DateOffset(years=period_num)
        else:
            start = now - pd.DateOffset(months=period_num)
        if "time" in df.columns:
            df = df[pd.to_datetime(df["time"]) >= start]
    return df

def fetch_argo_data(params):
    """
    params: dict including 'bbox' (lon_min, lon_max, lat_min, lat_max), 'variable', 'period_num','period_unit'
    Attempts to use argopy; falls back to demo CSV in demo_data/argo_sample.csv
    Returns a pandas.DataFrame with columns: float_id, lon, lat, time, temperature, salinity
    """
    bbox = params.get("bbox", [-180,180,-90,90])
    variable = params.get("variable", "temperature")
    period_num = params.get("period_num", params.get("years", 5))
    period_unit = params.get("period_unit", "years")

    # Try argopy if available
    if HAS_ARGOPY:
        try:
            # Basic region fetch. Note: adjust depth/params as needed.
            # argopy region signature can be: lon_min, lon_max, lat_min, lat_max, depth_min, depth_max, start_date, end_date
            now = pd.Timestamp.utcnow()
            if isinstance(period_num, int):
                if period_unit and period_unit.startswith("year"):
                    start = (now - pd.DateOffset(years=period_num)).strftime("%Y-%m-%d")
                else:
                    start = (now - pd.DateOffset(months=period_num)).strftime("%Y-%m-%d")
            else:
                start = (now - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
            ds = ArgoDataFetcher().region([bbox[0], bbox[1], bbox[2], bbox[3], 0, 2000, start, now.strftime("%Y-%m-%d")]).to_xarray()
            # Convert to DataFrame: extract profiles into flat table
            df = ds.to_dataframe().reset_index()
            # try to normalize names
            rename_map = {}
            if "TEMP" in df.columns:
                rename_map["TEMP"] = "temperature"
            if "PSAL" in df.columns:
                rename_map["PSAL"] = "salinity"
            df = df.rename(columns=rename_map)
            # ensure required cols
            if "longitude" in df.columns:
                df["lon"] = df["longitude"]
            if "latitude" in df.columns:
                df["lat"] = df["latitude"]
            if "JULD" in df.columns:
                df["time"] = pd.to_datetime(df["JULD"])
            # keep only columns we want
            keep = [c for c in ["platform_number", "lon", "lat", "time", "temperature", "salinity"] if c in df.columns]
            df = df[keep]
            if "platform_number" in df.columns:
                df = df.rename(columns={"platform_number":"float_id"})
            return _filter_by_bbox_and_time(df, bbox, period_num, period_unit)
        except Exception:
            # fallback to demo data
            pass

    # Fallback: demo CSV shipped with project
    demo = os.path.join(os.path.dirname(__file__), "..", "demo_data", "argo_sample.csv")
    demo = os.path.abspath(demo)
    if os.path.exists(demo):
        df = pd.read_csv(demo, parse_dates=["time"])
        # ensure columns present
        if "lon" not in df.columns and "longitude" in df.columns:
            df["lon"] = df["longitude"]
        if "lat" not in df.columns and "latitude" in df.columns:
            df["lat"] = df["latitude"]
        return _filter_by_bbox_and_time(df, bbox, period_num, period_unit)

    # If all fails return empty DataFrame
    return pd.DataFrame()
