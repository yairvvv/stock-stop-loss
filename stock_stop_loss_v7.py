import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# הגדרת תצורת עמוד ראשית
st.set_page_config(page_title="סורק מניות ומומנטום", layout="wide", initial_sidebar_state="expanded")

# =====================================================================
# 1. ניהול ואתחול ה-State וה-URL (שמירה אוטומטית ללינק של הפלאפון)
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
    df['Vol_MA'] = df['Volume'].rolling(window=20).mean()
    
    # חילוץ נתונים ליום האחרון
    current_close = float(df['Close'].iloc[-1])
    twenty_day_high = float(df['20_High'].iloc[-1])
    twenty_day_low = float(df['20_Low'].iloc[-1])
    current_vol = float(df['Volume'].iloc[-1])
    avg_vol = float(df['Vol_MA'].iloc[-1])
    
    # חישוב קרבה לשיא (בתוך הטווח)
    price_range = twenty_day_high - twenty_day_low
    if price_range == 0:
        price_score = 50
    else:
        price_score = ((current_close - twenty_day_low) / price_range) * 100
        
    # מדד עוצמת ווליום (Volume Ratio)
    vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
    
    # שקלול ציון פריצה סופי: אם פרצנו את שיא 20 יום, נוסיף בונוס מבוסס ווליום
    breakout_score = price_score
    if current_close >= twenty_day_high:
        breakout_score += min(vol_ratio * 12, 35) # בונוס נפח מסחר לפריצה חזקה
        
    return {
        "Price": round(current_close, 2),
        "ATR": round(df['ATR'].iloc[-1], 2),
        "Breakout_Score": round(min(breakout_score, 100), 1),
        "Volume_Ratio": round(vol_ratio, 2)
    }

# =====================================================================
# 3. תפריט צד (Sidebar) - ניהול מניות עם עדכון URL חי
# =====================================================================
st.sidebar.title("🛠️ הגדרות וניהול רשימה")

st.sidebar.subheader("הוספת מניה חדשה")
with st.sidebar.form(key="add_stock_form", clear_on_submit=True):
    new_stock = st.text_input("הכנס סימול (למשל: AAPL, TSLA):").upper().strip()
    submit_button = st.form_submit_button(label="➕ הוסף לרשימה")
    
    if submit_button and new_stock:
        if new_stock not in st.session_state.stocks:
            st.session_state.stocks.append(new_stock)
            # עדכון מיידי של ה-URL
            st.query_params["stocks"] = ",".join(st.session_state.stocks)
            st.sidebar.success(f"הסימול {new_stock} נוסף בהצלחה!")
            st.rerun()
        else:
            st.sidebar.warning("הסימול כבר קיים ברשימה שלך.")

st.sidebar.markdown("---")

st.sidebar.subheader("הסרת מניה מהרשימה")
if st.session_state.stocks:
    stock_to_remove = st.sidebar.selectbox("בחר מניה למחיקה:", st.session_state.stocks)
    if st.sidebar.button("🗑️ מחק מניה נבחרת"):
        st.session_state.stocks.remove(stock_to_remove)
        # עדכון מיידי של ה-URL לאחר מחיקה
        st.query_params["stocks"] = ",".join(st.session_state.stocks)
        st.sidebar.error(f"הסימול {stock_to_remove} הוסר מהרשימה.")
        st.rerun()
else:
    st.sidebar.info("הרשימה ריקה.")

# =====================================================================
# 4. עמוד ראשי - תצוגת נתונים, סריקה וגרפים
# =====================================================================
st.title("📈 סורק מניות מתקדם ומדדי מומנטום")
st.write