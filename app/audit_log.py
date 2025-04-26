# app/Audit Log.py

import streamlit as st
import pandas as pd
from backend.audit_logger import fetch_recent_audit_logs

def main():
    st.title("📊 SQL Chatbot - Audit Log")

    st.markdown("This page displays the most recent SQL query events captured by the chatbot system.")

    # --- Settings ---
    log_limit = st.slider("How many recent queries to show?", min_value=10, max_value=200, value=50)

    # --- Load audit data ---
    logs = fetch_recent_audit_logs(limit=log_limit)

    if not logs:
        st.warning("No audit entries found yet.")
    else:
        df = pd.DataFrame(logs, columns=[
            "Timestamp",
            "User Prompt",
            "Generated SQL",
            "Success",
            "Error Message",
            "Duration (ms)"
        ])

        df["Success"] = df["Success"].map({1: "✅", 0: "❌"})

        st.dataframe(df, use_container_width=True, height=600)

        with st.expander("📥 Download CSV"):
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download Audit Log as CSV", data=csv, file_name="chat_audit_log.csv", mime="text/csv")
