import json
import os
from django.shortcuts import render, redirect
from django.conf import settings
from .models import QueryLog
from argo.utils import fetch_argo_data
from visualization.utils import make_plot, make_map, make_comparison_plot
import pandas as pd

OPENAI_API_KEY = settings.OPENAI_API_KEY
try:
    import openai
    openai.api_key = OPENAI_API_KEY or None
except Exception:
    openai = None

# Region presets
REGION_PRESETS = {
    "pacific": [-180, 180, -60, 60],
    "indian ocean": [20, 120, -40, 30],
    "near india": [68, 98, 6, 30],
    "arabian sea": [52, 68, 5, 24],
}

def parse_query_offline(q):
    """Heuristic parser: variable(s), region, time, query_type"""
    ql = q.lower()
    params = {
        "variables": ["temperature"],
        "region": "pacific",
        "years": 5,
        "query_type": "trend",
    }

    # variable detection
    if "salin" in ql:
        params["variables"] = ["salinity"]
    if "current" in ql:
        params["variables"] = ["current"]
    if "compare" in ql or ("temperature" in ql and "salinity" in ql):
        params["variables"] = ["temperature", "salinity"]
        params["query_type"] = "comparison"

    # region
    for name in REGION_PRESETS:
        if name in ql:
            params["region"] = name
            break

    # query type
    if "map" in ql or "location" in ql:
        params["query_type"] = "map"
    elif "summary" in ql or "average" in ql:
        params["query_type"] = "summary"

    # time horizon
    import re
    m = re.search(r"last (\d+) (year|years|month|months)", ql)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        params["period_num"] = num
        params["period_unit"] = unit
    else:
        # explicit years like 2010–2020
        m2 = re.search(r"(\d{4})\s*[-to]+\s*(\d{4})", ql)
        if m2:
            params["start_year"] = int(m2.group(1))
            params["end_year"] = int(m2.group(2))

    return params

def parse_query_with_openai(q):
    if not openai:
        return None
    try:
        prompt = f"""Parse this ocean query into JSON object with keys:
- variables: list like ['temperature'] or ['temperature','salinity']
- region: free text region name
- query_type: 'trend'|'map'|'summary'|'comparison'
- period_num, period_unit (optional)
- start_year, end_year (optional)

Query: \"\"\"{q}\"\"\""""
        resp = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=200,
            temperature=0,
        )
        txt = resp.choices[0].text.strip()
        import re
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            j = json.loads(m.group(0))
            return j
    except Exception:
        return None

def chat_view(request):
    if request.method == "POST":
        user_query = request.POST.get("query", "").strip()
        if not user_query:
            return redirect("chat")

        # Save query
        qlog = QueryLog.objects.create(query=user_query)

        # Parse query
        params = parse_query_with_openai(user_query) or parse_query_offline(user_query)

        # Resolve region
        region_name = params.get("region", "pacific")
        bbox = REGION_PRESETS.get(region_name, REGION_PRESETS["pacific"])
        params["bbox"] = bbox

        # Fetch ARGO data
        try:
            df = fetch_argo_data(params)
        except Exception:
            df = pd.DataFrame()

        # Fallback demo CSV
        if df is None or df.empty:
            demo_path = os.path.join(os.path.dirname(__file__), "..", "demo_data", "argo_sample.csv")
            try:
                df = pd.read_csv(os.path.abspath(demo_path), parse_dates=["time"])
            except Exception:
                df = pd.DataFrame()

        # Ensure variable columns exist
        for v in params.get("variables", []):
            if v not in df.columns:
                if v == "temperature" and "temp" in df.columns:
                    df[v] = df["temp"]
                elif v == "salinity" and "sal" in df.columns:
                    df[v] = df["sal"]

        # Build response
        summary_text = "No data found for the requested region/time."
        plot_html, map_html = "", ""

        if not df.empty:
            if params["query_type"] == "comparison" and len(params["variables"]) > 1:
                summary_text = f"Comparison of {', '.join(params['variables'])}."
                plot_html = make_comparison_plot(df)

            elif params["query_type"] == "map":
                summary_text = "Showing float locations on the map."
                map_html = make_map(df)

            elif params["query_type"] == "summary":
                v = params["variables"][0]
                if v in df.columns:
                    meanv = float(df[v].mean())
                    summary_text = f"Average {v}: {meanv:.2f} (from {len(df)} data points)."

            else:  # default trend
                v = params["variables"][0]
                if v in df.columns:
                    meanv = float(df[v].mean())
                    summary_text = f"Average {v}: {meanv:.2f} (from {len(df)} data points)."
                plot_html = make_plot(df, v)
                map_html = make_map(df)

        # Update log
        qlog.response_text = summary_text
        qlog.save()

        # Flags for UI rendering
        map_only = (params["query_type"] == "map")
        comparison_only = (params["query_type"] == "comparison")

        return render(request, "results.html", {
            "query": user_query,
            "summary": summary_text,
            "plot_html": plot_html,
            "map_html": map_html,
            "map_only": map_only,
            "comparison_only": comparison_only,
        })

    return render(request, "chat.html")

def results_view(request):
    return redirect("chat")
