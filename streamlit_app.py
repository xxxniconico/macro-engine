#!/usr/bin/env python3
"""Dalio Macro Engine — Streamlit Cloud wrapper.
Embeds the pure-HTML dashboard with data.json injected directly.
"""
import streamlit as st
import json
from pathlib import Path

st.set_page_config(
    page_title="Dalio 宏观引擎",
    page_icon="🌐",
    layout="wide",
)

# Load data and HTML
data_path = Path(__file__).parent / "dashboard" / "data.json"
html_path = Path(__file__).parent / "dashboard" / "index.html"

with open(data_path) as f:
    data = json.load(f)

with open(html_path) as f:
    html = f.read()

# Inject data as a complete mock Response object
data_json = json.dumps(data, ensure_ascii=False)
injection = f"""<script>
window._DALIO_DATA_JSON = {json.dumps(data_json)};
</script>
"""

# Replace fetch('data.json?...') with a complete mock that has .status, .ok, .text()
old_fetch = "fetch('data.json?' + Date.now())"
new_fetch = """{
    status: 200,
    ok: true,
    json: function() { return Promise.resolve(window._DALIO_DATA); },
    text: function() { return Promise.resolve(window._DALIO_DATA_JSON); }
}"""
html = html.replace(old_fetch, new_fetch)

# Also inject the parsed data (for json() calls)
# We need to store the full object AND the JSON string
html = html.replace('</head>',
    injection + '\n<script>window._DALIO_DATA = ' + json.dumps(data, ensure_ascii=False) + ';</script>\n</head>')

st.components.v1.html(html, height=2200, scrolling=True)
