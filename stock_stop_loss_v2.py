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

# ניהול רשימת המעקב (Watchlist) בתוך ה-Session State של Streamlit
if "watchlist" not in st.session_state:
    st.session_state.watchlist = DEFAULT_WATCHLIST.copy()

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
            "Trend": "YES" if price > float(last["MA50"]) else "NO",
            "Stop": round(stop, 2), "Trail": round(trailing_stop, 2),
            "Risk%": round(((price - stop) / price) * 100, 2), "RS": rs,
            "Score": trade_quality(df, symbol, regime, rs), "Shares": shares
        }
    except:
        return None

# ======================================================
# INTERFACE & LAYOUT (STREAMLIT UI)
# ======================================================

st.title("📊 Momentum Breakout Scanner")
st.subheader("מערכת סריקה, דירוג וניהול סיכונים כמותי")

# סרגל צדי להגדרות וניהול מניות
st.sidebar.header("⚙️ הגדרות חשבון וניהול")
account_size = st.sidebar.number_input("גודל תיק כולל ($)", value=100000, step=5000)
risk_pct = st.sidebar.slider("סיכון מקסימלי לעסקה (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)

st.sidebar.write("---")
st.sidebar.subheader("📈 ניהול רשימת מעקב")

# הוספת מניה חדשה
new_sym = st.sidebar.text_input("הוסף סימול (לדוגמה: AAPL):").upper().strip()
if st.sidebar.button("➕ הוסף לרשימה"):
    if new_sym and new_sym not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_sym)
        st.success(f"הסימול {new_sym} התווסף בהצלחה!")
        st.rerun()

# הסרת מניה קיימת
if st.session_state.watchlist:
    sym_to_remove = st.sidebar.selectbox("בחר סימול להסרה:", [""] + st.session_state.watchlist)
    if st.sidebar.button("❌ הסר מהרשימה"):
        if sym_to_remove in st.session_state.watchlist:
            st.session_state.watchlist.remove(sym_to_remove)
            st.toast(f"הסימול {sym_to_remove} הוסר.")
            st.rerun()

# כפתור רענון ידני (מעבר לרענון האוטומטי של השרת)
if st.button("🔄 רענן נתונים עכשיו"):
    st.cache_data.clear()

# טעינת נתוני השוק הכלליים (Regime)
with st.spinner("מנתח תנאי שוק גלובליים (SPY & QQQ)..."):
    regime = market_regime()

# הצגת מצב השוק בצורה בולטת
if "BULL" in regime:
    st.success(f"🚦 מצב שוק נוכחי: **{regime}** (שוק שורי - סריקה אגרסיבית מופעלת)")
elif "CORRECTION" in regime:
    st.error(f"🚦 מצב שוק נוכחי: **{regime}** (שוק בתיקון - הגנת הון מחמירה, סטופים קרובים)")
else:
    st.warning(f"🚦 מצב שוק נוכחי: **{regime}** (שוק נייטרלי / דשדוש)")

# הרצת הסורק על כל רשימת המעקב
results = []
progress_bar = st.progress(0)
status_text = st.empty()

for idx, sym in enumerate(st.session_state.watchlist):
    status_text.text(f"סורק את מניית {sym}...")
    res = scan_stock(sym, regime, account_size, risk_pct)
    if res:
        results.append(res)
    progress_bar.progress((idx + 1) / len(st.session_state.watchlist))

status_text.empty()
progress_bar.empty()

# הצגת הטבלה הדינמית
if results:
    df_results = pd.DataFrame(results)
    # מיון ראשוני לפי הציון (Score) מהגבוה לנמוך
    df_results = df_results.sort_values(by="Score", ascending=False).reset_index(drop=True)
    
    st.write("### 📋 תוצאות הסריקה בזמן אמת")
    st.info("💡 ניתן ללחוץ על כותרת כל עמודה בטבלה כדי למיין מהגבוה לנמוך ולהפך באופן מיידי!")
    
    # הצגת הטבלה האינטראקטיבית המובנית של Streamlit
    st.dataframe(
        df_results, 
        use_container_width=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "ATR": st.column_config.NumberColumn(format="$%.2f"),
            "Stop": st.column_config.NumberColumn(format="$%.2f"),
            "Trail": st.column_config.NumberColumn(format="$%.2f"),
            "Risk%": st.column_config.NumberColumn(format="%.2f%%"),
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d pts"),
            "Shares": st.column_config.NumberColumn(format="%d יחידות")
        }
    )
else:
    st.warning("לא נמצאו נתונים תקינים עבור רשימת המעקב הנוכחית.")