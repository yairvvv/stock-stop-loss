import datetime
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# ==========================================
# 1. הגדרות בסיס וניהול סיכונים
# ==========================================
PORTFOLIO_SIZE = 100000  # גודל התיק הכללי
RISK_PERCENT = 0.01  # 1% סיכון לעסקה
RISK_AMOUNT = PORTFOLIO_SIZE * RISK_PERCENT  # $1,000 סיכון קבוע

ATR_WINDOW = 14  # חלון זמן לחישוב ה-ATR
DEFAULT_STOCKS = ["SOXL", "NVDA", "MSFT", "GOOGL", "SPMO"]

# מילון מכפילים סקטוריאליים (אופי המניה)
SECTOR_MULTIPLIERS = {
    "SOXL": 2.8,
    "NVDA": 2.5,
    "MSFT": 1.8,
    "GOOGL": 1.7,
    "SOXX": 2.5,
    "SPMO": 2.0,
}


# ==========================================
# 2. ניהול זיכרון ושמירה ל-URL (ללא קבצים)
# ==========================================
if "stocks" not in st.session_state:
    if "stocks" in st.query_params:
        # טעינת המניות הקיימות מתוך הלינק של הדפדפן
        st.session_state.stocks = st.query_params["stocks"].split(",")
    else:
        # רשימת ברירת מחדל ראשונית אם הלינק נקי
        st.session_state.stocks = DEFAULT_STOCKS.copy()
        st.query_params["stocks"] = ",".join(st.session_state.stocks)


# ==========================================
# 3. פונקציות חישוב ואינדיקטורים
# ==========================================
def calculate_atr(df, window=14):
    """חישוב מדד ה-ATR לתנודתיות"""
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift(1))
    low_close = np.abs(df["Low"] - df["Close"].shift(1))

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=window).mean()
    return atr


def get_market_regime():
    """בדיקת מצב השוק הכללי לפי ממוצע 50 של SPY ו-QQQ"""
    try:
        data = yf.download(["SPY", "QQQ"], period="3mo", progress=False)[
            "Close"
        ]
        spy_close = data["SPY"].iloc[-1]
        qqq_close = data["QQQ"].iloc[-1]

        spy_ma50 = data["SPY"].rolling(50).mean().iloc[-1]
        qqq_ma50 = data["QQQ"].rolling(50).mean().iloc[-1]

        if spy_close > spy_ma50 and qqq_close > qqq_ma50:
            return "BULL", 2.5, 15
        elif spy_close < spy_ma50 and qqq_close < qqq_ma50:
            return "CORRECTION", 1.2, 0
        else:
            return "NEUTRAL", 1.8, 5
    except:
        # גיבוי במקרה של שגיאת תקשורת
        return "NEUTRAL", 1.8, 5


def calculate_rs_alpha(ticker_df):
    """חישוב חוזק יחסי (RS) מול השוק ב-3 החודשים האחרונים"""
    try:
        spy_df = yf.download("SPY", period="6mo", progress=False)
        # סינכרון תאריכים
        common_dates = ticker_df.index.intersection(spy_df.index)
        if len(common_dates) < 63:
            return 0

        # תשואה ב-63 ימי מסחר (כ-3 חודשים)
        stock_perf = (
            ticker_df["Close"].loc[common_dates[-1]]
            / ticker_df["Close"].loc[common_dates[-63]]
        ) - 1
        spy_perf = (
            spy_df["Close"].loc[common_dates[-1]]
            / spy_df["Close"].loc[common_dates[-63]]
        ) - 1

        return float(stock_perf - spy_perf)
    except:
        return 0


# ==========================================
# 4. ממשק המשתמש (Streamlit UI)
# ==========================================
st.set_page_config(page_title="סורק מומנטום חכם", layout="wide")
st.title("📈 סורק מומנטום וניהול סיכונים")

# זיהוי מצב השוק הנוכחי
regime_name, base_multiplier, regime_points = get_market_regime()

# הצגת נתוני השוק בריבוע עליון
st.sidebar.markdown(f"### 🌐 מצב שוק כללי: **{regime_name}**")
st.sidebar.info(f"מכפיל בסיס לשוק: {base_multiplier}")

# --- ניהול רשימת המעקב (הוספה ומחיקה) ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ ניהול רשימת מעקב")

new_ticker = st.sidebar.text_input("הוסף סימול מניה:").upper().strip()
if st.sidebar.button("➕ הוסף לרשימה"):
    if new_ticker and new_ticker not in st.session_state.stocks:
        st.session_state.stocks.append(new_ticker)
        st.query_params["stocks"] = ",".join(st.session_state.stocks)
        st.success(f"{new_ticker} נוספה!")
        st.rerun()

ticker_to_remove = st.sidebar.selectbox(
    "בחר מניה להסרה:", [""] + st.session_state.stocks
)
if st.sidebar.button("🗑️ מחק מהרשימה"):
    if ticker_to_remove in st.session_state.stocks:
        st.session_state.stocks.remove(ticker_to_remove)
        st.query_params["stocks"] = ",".join(st.session_state.stocks)
        st.warning(f"{ticker_to_remove} הוסרה.")
        st.rerun()

# ==========================================
# 5. ריצה על המניות ואיסוף הנתונים
# ==========================================
results = []

if st.session_state.stocks:
    with st.spinner("מושך נתונים ומחשב אינדיקטורים..."):
        # משיכת נתונים קבוצתית לחסכון בזמן
        all_data = yf.download(
            st.session_state.stocks, period="1y", progress=False
        )

        for ticker in st.session_state.stocks:
            try:
                # סינון הדאטה למניה הספציפית
                if len(st.session_state.stocks) > 1:
                    df = pd.DataFrame(
                        {
                            "Open": all_data["Open"][ticker],
                            "High": all_data["High"][ticker],
                            "Low": all_data["Low"][ticker],
                            "Close": all_data["Close"][ticker],
                            "Volume": all_data["Volume"][ticker],
                        }
                    ).dropna()
                else:
                    df = all_data.dropna()

                if df.empty:
                    continue

                # חישוב אינדיקטורים בסיסיים
                price = float(df["Close"].iloc[-1])
                atr = float(calculate_atr(df, ATR_WINDOW).iloc[-1])
                ma50 = float(df["Close"].rolling(50).mean().iloc[-1])

                # 10-day High ו-20-day High (מוסטים ביום אחד כדי לא לכלול את היום)
                high20 = float(df["High"].shift(1).rolling(20).max().iloc[-1])
                high10 = float(df["High"].shift(1).rolling(10).max().iloc[-1])

                # ווליום וממוצע ווליום
                current_vol = float(df["Volume"].iloc[-1])
                avg_vol20 = float(df["Volume"].rolling(20).mean().iloc[-1])

                # חישוב אלפא (RS)
                rs_alpha = calculate_rs_alpha(df)

                # --- חישוב המכפיל הדינמי ---
                sector_mult = SECTOR_MULTIPLIERS.get(ticker, 2.0)
                final_multiplier = (base_multiplier + sector_mult) / 2

                # --- חישוב סטופים ---
                stop_loss = price - (atr * final_multiplier)
                # הסטופ הנגרר מבוסס על השיא של 10 הימים האחרונים
                trail_stop = high10 - (atr * final_multiplier)

                # פקודת הטרייל לא יכולה לרדת מתחת לסטופ הראשוני
                if trail_stop < stop_loss:
                    trail_stop = stop_loss

                # --- ניהול סיכונים וכמות מניות ---
                risk_per_share = price - stop_loss
                shares_to_buy = (
                    int(RISK_AMOUNT / risk_per_share)
                    if risk_per_share > 0
                    else 0
                )

                # --- חישוב מערכת הניקוד (SCORE) ---
                score = 0
                # 1. מגמה ארוכת טווח (25 נק')
                if price > ma50:
                    score += 25
                # 2. איתות פריצה (25 נק')
                breakout_status = "YES" if price > high20 else "NO"
                if breakout_status == "YES":
                    score += 25
                # 3. אישור מחזור מסחר (20 נק')
                vol_ratio = current_vol / avg_vol20
                if vol_ratio >= 1.3:
                    score += 20
                # 4. חוזק יחסי (15 נק')
                if rs_alpha > 0:
                    score += 15
                # 5. רוח גבית מהשוק (15, 5, או 0 נק')
                score += regime_points
                # 6. בונוס סקטוריאלי מיוחד (5 נק')
                if ticker in ["SOXX", "SOXL", "SPMO"]:
                    score += 5

                # חסימת הציון למקסימום 100
                final_score = min(score, 100)

                # איסוף התוצאה לשורה בטבלה
                results.append(
                    {
                        "Ticker": ticker,
                        "Price": f"${price:,.2f}",
                        "Breakout": breakout_status,
                        "Score": final_score,
                        "Initial Stop": f"${stop_loss:,.2f}",
                        "Trailing Stop": f"${trail_stop:,.2f}",
                        "Shares (for $1k Risk)": f"{shares_to_buy:,}",
                        "RS vs SPY (Alpha)": f"{rs_alpha * 100:+.1f}%",
                        "Vol Ratio": f"{vol_ratio:.2f}x",
                    }
                )
            except Exception as e:
                # במקרה שמניה ספציפית נכשלה בטעינה, נדלג עליה ולא נרסק את האפליקציה
                continue

# ==========================================
# 6. הצגת הטבלה הסופית למשתמש
# ==========================================
if results:
    df_results = pd.DataFrame(results)
    # מיון אוטומטי מהציון הגבוה לנמוך
    df_results = df_results.sort_values(by="Score", ascending=False)

    # עיצוב ויזואלי קל לטבלה ב-Streamlit
    st.dataframe(
        df_results,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"* חישוב המניות מבוסס על גודל תיק של ${PORTFOLIO_SIZE:,} וסיכון מקסימלי של 1% (${RISK_AMOUNT:,}) לעסקה."
    )
else:
    st.info(
        "רשימת המעקב ריקה או שלא נמצאו נתונים. השתמש בתפריט הצד כדי להוסיף סימולי מניות (למשל: AAPL, TSLA)."
    )