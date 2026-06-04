# Asari-Rashidi 3-Ply Model (Transient Simulation Hybrid Version)
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import subprocess
import os

# ==============================================================================
# --- AUTOMATIC JAVA COMPILATION ON CLOUD RUNTIME ---
# This ensures that when GitHub deploys to Streamlit Cloud, the Java engine
# compiles successfully on the Linux server without manual compilation steps.
# ==============================================================================
if not os.path.exists("WeldEngine.class"):
    try:
        # Runs the Linux system Java compiler in the background
        subprocess.check_call(["javac", "WeldEngine.java"])
    except Exception as e:
        st.error(f"⚠️ Failed to compile WeldEngine.java: {e}")
        st.info("Please verify that packages.txt contains 'default-jdk' and is placed at your repository root.")

# --- CONFIGURATION ---
st.set_page_config(page_title="Asari-Rashidi SORPAS Time-Sim", layout="wide")
st.title("🔬 Real-Time Transient Nugget Growth Simulator (SORPAS Mode)")

# --- MATERIAL DATABASE ---
materials_db = {
    "Mild Steel (JSC270)": {"res_factor": 1.0, "k_mod": 1.0, "ce": 0.08},
    "High Strength (JSC440)": {"res_factor": 1.15, "k_mod": 1.05, "ce": 0.14},
    "DP600 (Dual Phase)": {"res_factor": 1.35, "k_mod": 1.12, "ce": 0.18},
    "DP980 (Ultra High Strength)": {"res_factor": 1.50, "k_mod": 1.20, "ce": 0.24},
    "Boron Steel (Usibor 1500)": {"res_factor": 1.65, "k_mod": 1.25, "ce": 0.35},
    "Trip Steel (TRIP780)": {"res_factor": 1.40, "k_mod": 1.15, "ce": 0.22}
}

# --- USER INPUT PANEL ---
with st.sidebar:
    st.header("🌐 Simulation Mode Selection")
    graph_mode = st.radio(
        "Select Visualization Type",
        options=["Complete 3D Volumetric Lobe", "2D Plane Slice Cross-Section"]
    )
    
    if graph_mode == "2D Plane Slice Cross-Section":
        slice_plane = st.selectbox(
            "Target Orientation Plane",
            options=["X-Y Plane (Current vs. Time at Fixed Force)", 
                     "X-Z Plane (Current vs. Force at Fixed Time)"]
        )
        if "X-Y Plane" in slice_plane:
            slice_force = st.slider("Slice Location: Fixed Force (kg)", 100, 450, 250, step=10)
            st.subheader("💡 Dynamic Operating Point")
            active_current = st.slider("Operating Current (A)", 5000, 13000, 9500, step=100)
            active_time = st.slider("Max Weld Time (Cycles)", 3, 24, 16, step=1)
            active_force = slice_force
        else:
            slice_time = st.slider("Slice Location: Fixed Time (Cycles)", 3, 24, 12, step=1)
            st.subheader("💡 Dynamic Operating Point")
            active_current = st.slider("Operating Current (A)", 5000, 13000, 9500, step=100)
            active_force = st.slider("Operating Force (kg)", 100, 450, 250, step=10)
            active_time = slice_time

    st.divider()
    st.header("1. Sheet Geometry Layers")
    mat1 = st.selectbox("Ply 1 Material (Top)", list(materials_db.keys()))
    t1 = st.slider("Thickness 1 (mm)", 0.5, 3.0, 1.0)
    
    mat2 = st.selectbox("Ply 2 Material (Bottom)", list(materials_db.keys()), index=2)
    t2 = st.slider("Thickness 2 (mm)", 0.5, 3.0, 1.2)

    st.header("2. Electrodes & Scalers")
    is_zinc = st.checkbox("Zinc Coated (GA/GI)?")
    d_tip = st.slider("Tip Diameter (mm)", 4.0, 10.0, 6.0)
    k_base = st.slider("Base k-factor", 0.10, 0.60, 0.35)

# --- ENGINE DATA EXTRACTION BRIDGE ---
def fetch_transient_java_data(curr, max_tm, frc):
    m1_props = materials_db[mat1]
    m2_props = materials_db[mat2]
    
    cmd = [
        "java", "WeldEngine",
        str(t1), str(m1_props["res_factor"]), str(m1_props["k_mod"]),
        str(t2), str(m2_props["res_factor"]), str(m2_props["k_mod"]),
        str(is_zinc).lower(), str(d_tip), str(k_base),
        str(curr), str(max_tm), str(frc)
    ]
    try:
        output = subprocess.check_output(cmd, text=True).strip()
        time_steps = []
        # Parse the data matrix pipeline string sent from Java
        for step in output.split("|"):
            t_step, dia, target, exp = step.split(",")
            time_steps.append({
                "cycle": int(t_step),
                "diameter": float(dia),
                "min_target": float(target),
                "expulsion": float(exp)
            })
        return time_steps
    except Exception as e:
        # Fallback dataset if process is initialising
        return [{"cycle": 1, "diameter": 0.0, "min_target": 4.0, "expulsion": 6.0}]

# --- PROCESS CALCULATIONS & VISUALIZATION ---
total_t = t1 + t2
t_min = min(t1, t2)
currents = np.linspace(5000, 13000, 50)  
times = np.linspace(3, 24, 40)
forces = np.linspace(100, 450, 40)

if graph_mode == "Complete 3D Volumetric Lobe":
    I, T, F = np.meshgrid(currents, times, forces)
    m1_p, m2_p = materials_db[mat1], materials_db[mat2]
    k_approx = k_base * ((t1*m1_p["k_mod"] + t2*m2_p["k_mod"])/total_t) * ((t1*m1_p["res_factor"] + t2*m2_p["res_factor"])/total_t)
    if is_zinc: k_approx *= 0.82
    nugget_growth = k_approx * ((I * (6.0/d_tip)**2)/10000)**2 * (T/10) * (300/F)**0.25 * 5.5
    target_min = 4 * np.sqrt(t_min)
    
    fig = go.Figure(data=go.Isosurface(
        x=I.flatten(), y=T.flatten(), z=F.flatten(), value=nugget_growth.flatten(),
        isomin=target_min, isomax=target_min*2.5, surface_count=3, colorscale='Plasma', opacity=0.4
    ))
    st.plotly_chart(fig, use_container_width=True)

else:
    # Fetch time-series sequence array completely from Java engine
    simulation_timeline = fetch_transient_java_data(active_current, active_time, active_force)
    
    # Static Background Window Process Map
    m1_p, m2_p = materials_db[mat1], materials_db[mat2]
    k_approx = k_base * ((t1*m1_p["k_mod"] + t2*m2_p["k_mod"])/total_t) * ((t1*m1_p["res_factor"] + t2*m2_p["res_factor"])/total_t)
    if is_zinc: k_approx *= 0.82
    tip_eff = (6.0 / d_tip)**2
    
    if "X-Y Plane" in slice_plane:
        I_2d, T_2d = np.meshgrid(currents, times)
        nugget_growth_2d = k_approx * ((I_2d * tip_eff)/10000)**2 * (T_2d/10) * (300/slice_force)**0.25 * 5.5
        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, colorscale='Plasma'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_time], mode='markers', marker=dict(color='white', size=12, symbol='cross'), name='Operating Point'))
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Weld Time (Cycles)", template="plotly_dark", height=500)
    else:
        I_2d, F_2d = np.meshgrid(currents, forces)
        nugget_growth_2d = k_approx * ((I_2d * tip_eff)/10000)**2 * (slice_time/10) * (300/F_2d)**0.25 * 5.5
        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=forces, z=nugget_growth_2d, colorscale='Plasma'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_force], mode='markers', marker=dict(color='white', size=1
