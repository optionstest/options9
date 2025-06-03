import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

def fmt(x):
    return f"{x:.2f}" if isinstance(x, (float, int)) else x

def get_weekly_expirations(n=10):
    today = datetime.today()
    expirations = []
    for i in range(n):
        friday = today + timedelta((4 - today.weekday()) % 7 + i * 7)
        expirations.append(friday.strftime("%Y-%m-%d"))
    return expirations

# Page configuration
st.set_page_config(layout="wide", page_title="Options Analyzer")

# Add disclaimer at the top of the app
with st.expander("📌 Disclaimer", expanded=True):
    st.markdown("""
    **This tool does not provide financial advice.**

    It is not intended to offer personalized investment recommendations, predict market movements, or suggest specific actions like buying or selling securities. 

    The data and insights presented are based on public sources (e.g., Yahoo Finance) and are provided for **educational and analytical purposes only**.

    Always conduct your own research or consult with a licensed financial advisor before making investment decisions.
    """)

st.title("📊 Options Analyzer for Cash Secured Puts & Covered Calls")

tab1, tab2 = st.tabs(["💰 Cash Secured Put", "📈 Covered Call"])

def render_tab(strategy, tab, unique_key_suffix):
    with tab:
        # Row 1: Inputs
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            min_price = st.number_input("Min Price", min_value=0.0, value=20.0, key=f"min_price_{unique_key_suffix}")
        with col2:
            max_price = st.number_input("Max Price", min_value=min_price, value=500.0, key=f"max_price_{unique_key_suffix}")
        with col3:
            moneyness_pct = st.slider("Moneyness %", min_value=1, max_value=100, value=10, key=f"moneyness_{unique_key_suffix}")
        with col4:
            expiration_list = get_weekly_expirations(8)
        with col5:
            additional_tickers = st.text_input("Add tickers (comma separated)", "", key=f"additional_{unique_key_suffix}")
        with col6:
            #magnificent7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
            magnificent7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOG", "META", "TSLA","RIVN", "WSM", "CRM", "SOUN", "LEN", "TGT", "PLTR", "VZ", "BABA", "FIVE", "ULTA", "WMT", "ELF", "LLY", "JD", "POWL", "NVO", "LULU", "MRVL", "SNOW", "MDB", "SOFI", "IBIT", "SMCI", "AMD", "MU"]
            etfs = ["SPY", "QQQ"]
            all_stocks = magnificent7 + etfs
            if additional_tickers:
                all_stocks.extend([t.strip().upper() for t in additional_tickers.split(",")])
            unique_stocks = sorted(set(all_stocks))
            tickers_list = ["ALL"] + unique_stocks
            selected_stock = st.selectbox("Select Ticker or 'ALL'", tickers_list, key=f"ticker_{unique_key_suffix}")

        @st.cache_data(show_spinner=False)
        def analyze_options(ticker, expirations, strategy, moneyness_pct, min_price, max_price):
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period="5d")
                #current_price = hist["Close"].iloc[-1]
                current_price = stock.history(period="1d")['Close'].iloc[-1]
                if current_price < min_price or current_price > max_price:
                    return []

                options_data = []
                for expiration in expirations:
                    try:
                        opt_chain = stock.option_chain(expiration)
                        options = opt_chain.puts if strategy == "Cash Secured Put" else opt_chain.calls
                        if options.empty:
                            continue
                        target_strike = round(current_price * (1 - moneyness_pct / 100) if strategy == "Cash Secured Put" else current_price * (1 + moneyness_pct / 100), 2)
                        options_filtered = options[options["strike"] <= target_strike] if strategy == "Cash Secured Put" else options[options["strike"] >= target_strike]
                        if options_filtered.empty:
                            continue
                        selected = options_filtered.iloc[-1] if strategy == "Cash Secured Put" else options_filtered.iloc[0]
                        strike_price = selected["strike"]
                        premium = (selected["bid"] + selected["ask"]) / 2 if selected["bid"] and selected["ask"] else selected["lastPrice"]
                        days_to_exp = (datetime.strptime(expiration, "%Y-%m-%d") - datetime.today()).days
                        abs_roi = premium / strike_price * 100
                        ann_roi = (abs_roi / days_to_exp) * 365 if days_to_exp > 0 else 0

                        row = {
                            "Ticker": ticker,
                            "Strategy": strategy,
                            "Current Price": fmt(current_price),
                            "Strike Price": fmt(strike_price),
                            "Analyst Target": fmt(info.get("targetMeanPrice", 0.0)),
                            "Premium": fmt(premium),
                            "Days to Exp": days_to_exp,
                            "Expiration": expiration,
                            "Ann ROI (%)": fmt(ann_roi),
                            "Abs ROI (%)": fmt(abs_roi),
                            "Div Yield": fmt(info.get("dividendYield", 0.0) * 100),
                            "Next Earnings": info.get("earningsDate", "N/A"),
                            "Recommendation": info.get("recommendationKey", "N/A"),
                            "EPS (TTM)": fmt(info.get("trailingEps", 0.0)),
                            "EPS Trend": "Beat" if info.get("earningsQuarterlyGrowth", 0) > 0 else "Miss",
                            "Overall Score": fmt(info.get("recommendationMean", 0.0)),
                            "Sector": info.get("sector", "N/A"),
                            "Industry": info.get("industry", "N/A")
                        }
                        options_data.append(row)
                    except:
                        continue
                return options_data
            except:
                return []

        tickers_to_process = unique_stocks if selected_stock == "ALL" else [selected_stock]
        all_results = []
        for tkr in tickers_to_process:
            results = analyze_options(tkr, expiration_list, strategy, moneyness_pct, min_price, max_price)
            all_results.extend(results)

        if all_results:
            df = pd.DataFrame(all_results)
            df = df.sort_values(by="Ann ROI (%)", ascending=False)

            st.dataframe(df, use_container_width=True)

            st.subheader("📊 ROI Trend by Expiration (Bar Chart)")
            fig = px.bar(df, x="Expiration", y="Ann ROI (%)", color="Ticker", barmode="group")
            fig.update_layout(xaxis_title="Expiration Date", yaxis_title="Annualized ROI (%)")
            st.plotly_chart(fig, use_container_width=True)

            #st.download_button("📥 Download CSV", df.to_csv(index=False), "options_analysis.csv", "text/csv")
        else:
            st.warning("No data found for selected filters or strategy.")

# Render both tabs with unique keys
render_tab("Cash Secured Put", tab1, "put")
render_tab("Covered Call", tab2, "call")