import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# הגדרת תצורת עמוד ראשית
st.set_page_config(page_title="סורק מניות ומומנטום", layout="wide", initial_sidebar_state="expanded")

# =====================================================================
# 1. ניהול ואתחול ה-State וה-URL (הפיצ'ר החדש שביקשת)
# =====================================================================
DEFAULT_STOCKS = ["SOXL", "NVDA", "MSFT", "GOOGL", "SPMO"]

# אם ה-State עדיין לא מאותחל, נבדוק אם יש מידע שמור בכתובת ה-URL (הדפדפן)
if "stocks" not in st.session_state:
    if "stocks" in st.query_params and st.query_params["stocks"]:
        # טעינת המניות השמורות מה-URL
        st.session_state.stocks = st.query_params["stocks"].split(",")
    else:
        # אם ה-URL ריק, נשתמש ברשימת ברירת המחדל ונרשום אותה ל-URL
        st.session_state.stocks = DEFAULT_STOCKS.copy()
        st.query_params["stocks"] = ",".join(st.session_state.stocks)

# =====================================================================
# 2. פונקציית ליבה: חישוב אינדיקטורים טכניים (ATR וציון פריצה)
# =====================================================================
def calculate_momentum_metrics(df, period=14):
    if len(df) < period + 5:
        return None
    
    # הבטחה שהעמודות שטוחות (למקרה של שינויי פורמט ב-yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # --- חישוב ATR (Average True Range) ---
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=period).mean()
    
    # --- חישוב מדדי פריצה ומומנטום (Breakout Score) ---
    # בדיקת מיקום המחיר ביחס לטווח הגבוה/נמוך של 20 הימים האחרונים
    df['20_High'] = df['High'].rolling(window=20).max()
    df['20_Low'] = df['Low'].rolling(window=20).min()
    df['Vol_MA'] =