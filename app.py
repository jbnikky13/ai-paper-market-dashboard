import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timezone, timedelta

st.set_page_config(
    page_title="AI Market Intelligence v4",
    page_icon="🤖",
    layout="wide",
)

# ============================================================
# CONFIG
# ============================================================

COINCAP_BASE = "https://rest.coincap.io/v3"
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
