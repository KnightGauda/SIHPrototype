import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from django.utils.html import format_html

def make_plot(df: pd.DataFrame, variable="temperature"):
    """
    Returns Plotly HTML snippet (div + script) embedding the figure.
    """
    if df is None or df.empty or variable not in df.columns:
        return "<div><em>No timeseries data available for plotting.</em></div>"

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        ts = df.dropna(subset=["time", variable]).sort_values("time")
    else:
        ts = df.reset_index()

    if ts.empty:
        return "<div><em>No valid data to plot.</em></div>"

    fig = px.line(
        ts,
        x="time",
        y=variable,
        title=f"{variable.capitalize()} trend",
        markers=True
    )
    fig.update_traces(line=dict(width=2, color="blue"), marker=dict(size=6, color="red"))
    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        height=360,
        xaxis_title="Time",
        yaxis_title=variable.capitalize(),
        template="plotly_white"
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)

def make_comparison_plot(df: pd.DataFrame, variables=("temperature", "salinity")):
    """
    Returns a clear, styled line chart comparing multiple variables over time.
    """
    if df is None or df.empty:
        return "<div><em>No data available for comparison plot.</em></div>"

    if "time" not in df.columns:
        return "<div><em>No time column found for plotting.</em></div>"

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    ts = df.dropna(subset=["time"]).sort_values("time")

    fig = go.Figure()
    added = False

    # Custom styles per variable
    styles = {
        "temperature": dict(color="blue", dash="solid", marker_symbol="circle"),
        "salinity": dict(color="green", dash="dash", marker_symbol="square"),
        "current": dict(color="orange", dash="dot", marker_symbol="triangle-up")
    }

    for var in variables:
        if var in ts.columns:
            ts_clean = ts.dropna(subset=[var])
            if not ts_clean.empty:
                style = styles.get(var, dict(color=None, dash="solid", marker_symbol="circle"))
                fig.add_trace(go.Scatter(
                    x=ts_clean["time"],
                    y=ts_clean[var],
                    mode="lines+markers",
                    name=var.capitalize(),
                    line=dict(width=2, dash=style["dash"], color=style["color"]),
                    marker=dict(size=7, symbol=style["marker_symbol"], color=style["color"])
                ))
                added = True

    if not added:
        return "<div><em>Requested variables not found in dataset.</em></div>"

    fig.update_layout(
        title="Comparison of variables over time",
        xaxis_title="Time",
        yaxis_title="Value",
        margin=dict(l=10, r=10, t=40, b=10),
        height=450,
        template="plotly_white",
        legend=dict(
            orientation="h",
            y=1.1,
            x=0.5,
            xanchor="center",
            font=dict(size=12, color="black")
        )
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)

def make_map(df: pd.DataFrame):
    """
    Returns HTML snippet containing a small JS block to create a Leaflet map and add markers.
    """
    if df is None or df.empty:
        return "<div><em>No float location data available for map.</em></div>"

    features = []
    for _, row in df.dropna(subset=["lat","lon"]).iterrows():
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except Exception:
            continue
        props = {"float_id": str(row.get("float_id", ""))}
        if "time" in row and pd.notna(row["time"]):
            props["time"] = str(row["time"])
        if "temperature" in row and pd.notna(row["temperature"]):
            props["temperature"] = float(row["temperature"])
        if "salinity" in row and pd.notna(row["salinity"]):
            props["salinity"] = float(row["salinity"])
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })

    geojson = {"type": "FeatureCollection", "features": features}
    geojson_text = json.dumps(geojson)

    lats = [f["geometry"]["coordinates"][1] for f in features] or [0]
    lons = [f["geometry"]["coordinates"][0] for f in features] or [0]
    center_lat = sum(lats)/len(lats)
    center_lon = sum(lons)/len(lons)

    script = f"""
    <div id="embedded-map" style="height:420px;"></div>
    <script>
      (function(){{
        var geo = {geojson_text};
        var map = L.map('embedded-map').setView([{center_lat}, {center_lon}], 3);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 18,
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);

        function onEachFeature(feature, layer) {{
            var props = feature.properties || {{}};
            var html = "";
            if (props.float_id) html += "<b>Float:</b> " + props.float_id + "<br/>";
            if (props.time) html += "<b>Time:</b> " + props.time + "<br/>";
            if (props.temperature) html += "<b>Temp:</b> " + props.temperature + " °C<br/>";
            if (props.salinity) html += "<b>Salinity:</b> " + props.salinity + " PSU<br/>";
            layer.bindPopup(html);
        }}

        L.geoJSON(geo, {{
            onEachFeature: onEachFeature,
            pointToLayer: function(feature, latlng) {{
                return L.circleMarker(latlng, {{radius:6}});
            }}
        }}).addTo(map);
      }})();
    </script>
    """
    return script
