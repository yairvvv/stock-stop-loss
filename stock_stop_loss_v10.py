import streamlit as st
import yfinance as yf
import pandas as pd
from ta.volatility import AverageTrueRange
import datetime

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

# ניהול רשימת המעקב (Watchlist) בתוך ה-Session State וסנכרון ל-URL
if "watchlist" not in st.session_state:
    if "watchlist" in st.query_params and st.query_params["watchlist"]:
        st.session_state.watchlist = st.query_params["watchlist"].split(",")
    else:
        st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
        st.query_params["watchlist"] = ",".join(st.session_state.watchlist)

# ======================================================
# FINANCE LOGIC FUNCTIONS
# ======================================================
def get_data(symbol, target_date=None):
    try:
        # אם נבחר תאריך, נוריד נתונים משנתיים לפניו כדי שיהיה מספיק מידע לממוצעים
        if target_date:
            end_dt = pd.to_datetime(target_date) + pd.Timedelta(days=1)
            start_dt = end_dt - pd.Timedelta(days=365 * 2)
            df = yf.download(
                symbol, 
                start=start_dt.strftime('%Y-%m-%d'), 
                end=end_dt.strftime('%Y-%m-%d'), 
                interval="1d", 
                progress=False
            )
        else:
            df = yf.download(symbol, period="2y", interval="1d", progress=False)
            
        if df.empty:
            return pd.DataFrame()
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # הסרת אזורי זמן כדי למנוע התנגשויות בחיתוך
        df.index = df.index.tz_localize(None)
        
        # חיתוך מדויק עד לתאריך הנבחר
        if target_date:
            target_datetime = pd.to_datetime(target_date)
            df = df.loc[:target_datetime]
            
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

def market_regime(target_date):
    try:
        spy_raw = get_data("SPY", target_date)
        qqq_raw = get_data("QQQ", target_date)
        if spy_raw.empty or qqq_raw.empty: 
            return "NEUTRAL"
        
        spy = add_indicators(spy_raw)
        qqq = add_indicators(qqq_raw)
        
        # פיצול לשורות קצרות כדי למנוע שגיאות חיתוך קוד
        spy_close = float(spy["Close"].iloc[-1])
        qqq_close = float(qqq["Close"].iloc[-1])
        spy_ma50 = float(spy["MA50"].iloc[-1])
        qqq_ma50 = float(qqq["MA50"].iloc[-1])
        
        if spy_close > spy_ma50 and qqq_close > qqq_ma50: 
            return "BULL"
        elif spy_close > spy_ma50 or qqq_close > qqq_ma50: 
            return "NEUTRAL"
        return "CORRECTION"
    except:
        return "NEUTRAL (DATA ERR)"

def relative_strength(symbol, target_date):
    try:
        stock_df = get_data(symbol, target_date)
        spy_df = get_data("SPY", target_date)
        if stock_df.empty or spy_df.empty or len(stock_df) < 21: 
            return 0
        
        stock_return = float(stock_df["Close"].pct_change(20).iloc[-1])
        spy_return = float(spy_df["Close"].pct_change(20).iloc[-1])
        return round(stock_return / spy_return, 2) if spy_return != 0 else 0
    except:
        return 0

def trade_quality(df, symbol, regime, rs):
    if df.empty or len(df) < 20: 
        return 0
    last = df.iloc[-1]
    score = 0
    if float(last["Close"]) > float(last["MA50"]): score += 25
    if float(last["Close"]) > float(last["High20"]): score += 25
    vol_ratio = float(last["Volume"]) / float(last["AvgVolume20
