import os
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from storage import StorageManager

st.set_page_config(
    page_title="WT901C Vibration & Inclinometer Tracker",
    page_icon="📈",
    layout="wide"
)

# Initialize storage manager instance
DB_DIR = os.getenv("DB_DIR", "data")
storage = StorageManager(db_dir=DB_DIR)

st.title("WT901C 9-Axis Vibration & Tilt Tracking Dashboard")
st.caption("Continuous Long-Term Monitoring for Acceleration, Gyroscope, Angle Inclinometer, and Vibration RMS")

# Sidebar settings
st.sidebar.header("Dashboard Settings")
auto_refresh = st.sidebar.checkbox("Auto-Refresh Live Data", value=True)
refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", min_value=1, max_value=10, value=2)
live_sample_limit = st.sidebar.select_slider("Live Graph Window (readings)", options=[100, 300, 500, 1000, 2000], value=500)

# Sidebar Database Stats
st.sidebar.markdown("---")
st.sidebar.subheader("Storage Status")
try:
    stats = storage.get_db_stats()
    st.sidebar.metric("DB Size", f"{stats['file_size_mb']} MB")
    st.sidebar.metric("Total Raw Records", f"{stats['total_raw_rows']:,}")
    st.sidebar.metric("Hourly Rollup Records", f"{stats['total_hourly_rows']:,}")
except Exception as e:
    st.sidebar.error(f"Error reading DB stats: {e}")

# Navigation tabs
tab_live, tab_longterm, tab_export = st.tabs(["🔴 Live Monitoring", "📅 Long-Term Trends", "📥 Data Exporter"])

# ---------------------------- TAB 1: LIVE MONITORING ----------------------------
with tab_live:
    raw_data = storage.get_latest_readings(limit=live_sample_limit)
    
    if not raw_data:
        st.warning("No data found in database yet. Ensure `collector.py` is running and sensor is plugged in.")
    else:
        df = pd.DataFrame(raw_data)
        # Reverse to chronological order for charts
        df = df.iloc[::-1].reset_index(drop=True)
        latest = df.iloc[-1]

        # Top key metric indicators
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Roll (X Tilt)", f"{latest['roll']:.2f}°", help="XY 0.05° High-Precision Inclinometer")
        col2.metric("Pitch (Y Tilt)", f"{latest['pitch']:.2f}°")
        col3.metric("Yaw (Compass)", f"{latest['yaw']:.2f}°")
        col4.metric("Vibration RMS", f"{latest['rms_accel']:.3f} g")
        col5.metric("Temperature", f"{latest['temp']:.1f} °F")

        st.markdown("---")

        # Row 1: Inclinometer Angle Graph
        fig_angle = go.Figure()
        fig_angle.add_trace(go.Scatter(x=df['datetime'], y=df['roll'], mode='lines', name='Roll (°)'))
        fig_angle.add_trace(go.Scatter(x=df['datetime'], y=df['pitch'], mode='lines', name='Pitch (°)'))
        fig_angle.add_trace(go.Scatter(x=df['datetime'], y=df['yaw'], mode='lines', name='Yaw (°)'))
        fig_angle.update_layout(
            title="Inclinometer Tilt Angles (Roll, Pitch, Yaw)",
            xaxis_title="Time",
            yaxis_title="Angle (Degrees)",
            height=380,
            hovermode="x unified"
        )
        st.plotly_chart(fig_angle, use_container_width=True)

        # Row 2: 3-Axis Acceleration & Vibration RMS Graph
        col_left, col_right = st.columns(2)
        with col_left:
            fig_acc = go.Figure()
            fig_acc.add_trace(go.Scatter(x=df['datetime'], y=df['ax'], mode='lines', name='Ax (g)'))
            fig_acc.add_trace(go.Scatter(x=df['datetime'], y=df['ay'], mode='lines', name='Ay (g)'))
            fig_acc.add_trace(go.Scatter(x=df['datetime'], y=df['az'], mode='lines', name='Az (g)'))
            fig_acc.update_layout(
                title="Triaxial Acceleration",
                xaxis_title="Time",
                yaxis_title="Acceleration (g)",
                height=350
            )
            st.plotly_chart(fig_acc, use_container_width=True)

        with col_right:
            fig_rms = px.line(df, x='datetime', y='rms_accel', title="RMS Vibration Magnitude")
            fig_rms.update_traces(line_color="#E74C3C")
            fig_rms.update_layout(xaxis_title="Time", yaxis_title="RMS Acceleration (g)", height=350)
            st.plotly_chart(fig_rms, use_container_width=True)

# ---------------------------- TAB 2: LONG-TERM TRENDS ----------------------------
with tab_longterm:
    st.subheader("Multi-Day & Multi-Month Aggregated Trends")
    st.caption("Visualizing hourly rollup metrics computed by the background downsampler worker.")

    rollups = storage.get_hourly_rollups(limit=5000)
    if not rollups:
        st.info("Hourly rollups are currently building or no records logged yet. Run `python3 downsampler.py --once` to build rollups instantly.")
    else:
        df_roll = pd.DataFrame(rollups)
        
        # Inclinometer Min/Max/Mean Envelope Chart
        fig_envelope = go.Figure()
        fig_envelope.add_trace(go.Scatter(
            x=df_roll['timestamp_hour'], y=df_roll['roll_max'],
            mode='lines', line=dict(width=0), showlegend=False, name='Roll Max'
        ))
        fig_envelope.add_trace(go.Scatter(
            x=df_roll['timestamp_hour'], y=df_roll['roll_min'],
            mode='lines', line=dict(width=0), fill='tonexty',
            fillcolor='rgba(31, 119, 180, 0.2)', name='Roll Range (Min/Max)'
        ))
        fig_envelope.add_trace(go.Scatter(
            x=df_roll['timestamp_hour'], y=df_roll['roll_mean'],
            mode='lines', line=dict(color='#1F77B4', width=2), name='Roll Mean (°)'
        ))
        fig_envelope.update_layout(
            title="Long-Term Roll Angle Trend with Hourly Min/Max Range",
            xaxis_title="Hour",
            yaxis_title="Roll Angle (°)",
            height=400
        )
        st.plotly_chart(fig_envelope, use_container_width=True)

        # Vibration Peak & RMS Trend Chart
        fig_vib_trend = go.Figure()
        fig_vib_trend.add_trace(go.Scatter(
            x=df_roll['timestamp_hour'], y=df_roll['rms_accel_mean'],
            mode='lines', name='Mean RMS Vibration (g)', line=dict(color='#2ECC71')
        ))
        fig_vib_trend.add_trace(go.Scatter(
            x=df_roll['timestamp_hour'], y=df_roll['peak_accel_max'],
            mode='lines', name='Peak Max Acceleration (g)', line=dict(color='#E74C3C')
        ))
        fig_vib_trend.update_layout(
            title="Long-Term Vibration Intensity & Peak Max Acceleration Trend",
            xaxis_title="Hour",
            yaxis_title="Acceleration (g)",
            height=400
        )
        st.plotly_chart(fig_vib_trend, use_container_width=True)

# ---------------------------- TAB 3: DATA EXPORTER ----------------------------
with tab_export:
    st.subheader("Export Sensor Logs")
    st.markdown("Filter and download data directly as CSV format for analysis in Excel, Python, or MATLAB.")

    export_type = st.radio("Export Dataset Type", options=["Hourly Summary Rollups", "Raw High-Frequency Readings"])
    
    if export_type == "Hourly Summary Rollups":
        data_to_export = storage.get_hourly_rollups(limit=100000)
    else:
        limit_export = st.number_input("Maximum Raw Records to Export", min_value=100, max_value=500000, value=10000, step=5000)
        data_to_export = storage.get_latest_readings(limit=limit_export)

    if data_to_export:
        export_df = pd.DataFrame(data_to_export)
        st.dataframe(export_df.head(50))
        csv_bytes = export_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label=f"⬇️ Download {export_type} (CSV)",
            data=csv_bytes,
            file_name=f"wt901c_{export_type.lower().replace(' ', '_')}_{int(time.time())}.csv",
            mime="text/csv"
        )
    else:
        st.info("No data available to export.")

# Auto-refresh loop
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
