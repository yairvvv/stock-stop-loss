import streamlit as st
import yfinance as yf
import pandas as pd
from ta.volatility import AverageTrueRange

# הגדרות עמוד ראשוניות של האפליקציה
st.set_page_config(page_title="Momentum Breakout Scanner", layout="wide")

# עיצוב כיוון תצוגה כללי לעברית בחלק מהאלמנטים
st.markdown("""
    <style>
    .reportview-container .main .block-container { direction: rtl; }
    </style>
""", unsafe_allow_html=True)

# ======================================================
# CONFIG & CONSTANTS
# ======================================================
DEFAULT_WATCHLIST = ["MSFT", "META", "NVDA", "GOOGL", "SOXX", "SOXL", "SPMO", "DRAM"]
BREAKOUT_LOOKBACK = 20
ATR_WINDOW = 14
MA_WINDOW = 50

SECTOR_MULTIPLIER = {
    "SOXL": 2.8, "SOXX": 2.3, "NVDA": 2.5,
    "META": 2.1, "MSFT": 1.8, "GOOGL": 1.7,
    "SPMO": 2.0, "DRAM": 2.4
}

# ניהול רשימת המעקב (Watchlist) בתוך ה-Session State של Streamlit וסנכרון ל-URL
if "watchlist" not in st.session_state:
    # בדיקה אם יש נתונים שמורים ב-URL
    if "watchlist" in st.query_params and st.query_params["watchlist"]:
        st.session_state.watchlist = st.query_params["watchlist"].split(",")
    else:
        # אתחול עם ברירת מחדל אם אין נתונים שמורים ב-URL
        st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
        st.query_params["watchlist"] = ",".join(st.session_state.watchlist)

# ======================================================
# FINANCE LOGIC FUNCTIONS
# ======================================================
def get_data(symbol, period="6mo"):
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except:
        return pd.DataFrame()

def add_indicators(df):
    if df.empty or len(df) < MA_WINDOW:
        return df
    df["MA50"] = df["Close"].rolling(MA_WINDOW).mean()
    atr = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=ATR_WINDOW)
    df["ATR"] = atr.average_true_range()
    df["High20"] = df["High"].rolling(BREAKOUT_LOOKBACK).max().shift(1)
    df["AvgVolume20"] = df["Volume"].rolling(20).mean()
    return df

def market_regime():
    try:
        spy_raw = get_data("SPY")
        qqq_raw = get_data("QQQ")
        if spy_raw.empty or qqq_raw.empty: return "NEUTRAL"
        
        spy = add_indicators(spy_raw)
        qqq = add_indicators(qqq_raw)
        
        spy_close, qqq_close = float(spy["Close"].iloc[-1]), float(qqq["Close"].iloc[-1])
        spy_ma50, qqq_ma50 = float(spy["MA50"].iloc[-1]), float(qqq["MA50"].iloc[-1])
        
        if spy_close > spy_ma50 and qqq_close > qqq_ma50: return "BULL"
        elif spy_close > spy_ma50 or qqq_close > qqq_ma50: return "NEUTRAL"
        return "CORRECTION"
    except:
        return "NEUTRAL (DATA ERR)"

def relative_strength(symbol):
    try:
        stock_df = get_data(symbol)
        spy_df = get_data("SPY")
        if stock_df.empty or spy_df.empty or len(stock_df) < 21: return 0
        
        stock_return = float(stock_df["Close"].pct_change(20).iloc[-1])
        spy_return = float(spy_df["Close"].pct_change(20).iloc[-1])
        return round(stock_return / spy_return, 2) if spy_return != 0 else 0
    except:
        return 0

def trade_quality(df, symbol, regime, rs):
    if df.empty or len(df) < 20: return 0
    last = df.iloc[-1]
    score = 0
    if float(last["Close"]) > float(last["MA50"]): score += 25
    if float(last["Close"]) > float(last["High20"]): score += 25
    vol_ratio = float(last["Volume"]) / float(last["AvgVolume20"]) if float(last["AvgVolume20"]) > 0 else 0
    if vol_ratio > 1.3: score += 20
    if "BULL" in regime: score += 15
    elif "NEUTRAL" in regime: score += 5
    if rs > 1: score += 15
    if symbol in ["SOXX", "SPMO", "SOXL"]: score += 5
    return min(score, 100)

def scan_stock(symbol, regime, account_size, risk_pct):
    try:
        df_raw = get_data(symbol)
        if df_raw.empty or len(df_raw) < MA_WINDOW: return None
        
        df = add_indicators(df_raw)
        last = df.iloc[-1]
        price, atr = float(last["Close"]), float(last["ATR"])
        
        base_mult = 2.5 if "BULL" in regime else (1.8 if "NEUTRAL" in regime else 1.2)
        final_mult = (base_mult + SECTOR_MULTIPLIER.get(symbol, 2.0)) / 2
        
        stop = price - (atr * final_mult)
        risk_money = account_size * (risk_pct / 100)
        shares = int(risk_money / (price - stop)) if (price - stop) > 0 else 0
        
        trailing_stop = float(df["High"].rolling(10).max().iloc[-1]) - (atr * final_mult)
        rs = relative_strength(symbol)
        
        return {
            "Symbol": symbol, "Price": round(price, 2), "ATR": round(atr, 2),
            "Breakout": "YES" if price > float(last["High20"]) else "NO",
            "Trend": "YES" if price > float(last["MA5