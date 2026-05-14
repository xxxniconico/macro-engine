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

# Inject data before the loadData() call — replace the fetch with inline data
injection = f"""
<script>
// Injected by Streamlit wrapper — replaces fetch('data.json')
window._DALIO_DATA = {json.dumps(data)};
</script>
"""
# Replace the loadData function to use injected data instead of fetch
old_fetch = '    const resp = await fetch(\'data.json?\' + Date.now());'
new_fetch = 'const resp = { json: () => Promise.resolve(window._DALIO_DATA) };'
html = html.replace(old_fetch, new_fetch)

# Insert injection before </head>
html = html.replace('</head>', injection + '\n</head>')

st.components.v1.html(html, height=2200, scrolling=True)
