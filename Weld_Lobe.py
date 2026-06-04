# Asari-Rashidi 3-Ply Model (Open Source Hybrid Version)
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import pandas as pd
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
        st.error(f"⚠️ Failed to compile WeldEngine.java on server startup: {e}")
        st.info("Please verify that packages.txt contains 'default-jdk' and is placed at your repository root.")

# --- CONFIGURATION ---
st.set_page_config(page_title="Asari-Rashidi Hybrid Simulator", layout="wide")
st.title("🔬 Asari-Rashidi Lobe Window + SORPAS-Style Cross Section")

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
    st.header("🌐 View Optimization Mode")
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
            st.subheader("💡 Active Operating Point")
            active_current = st.slider("Operating Current (A)", 5000, 13000, 9500, step=100)
            active_time = st.slider("Operating Time (Cycles)", 3, 17, 10, step=1)
            active_force = slice_force
        else:
            slice_time = st.slider("Slice Location: Fixed Time (Cycles)", 3, 17, 10, step=1)
            st.subheader("💡 Active Operating Point")
            active_current = st.slider("Operating Current (A)", 5000, 13000, 9500, step=100)
            active_force = st.slider("Operating Force (kg)", 100, 450, 250, step=10)
            active_time = slice_time

    st.divider()
    st.header("1. Ply 1 (Top)")
    mat1 = st.selectbox("Material 1", list(materials_db.keys()))
    t1 = st.slider("Thickness 1 (mm)", 0.5, 3.0, 1.0)
    
    st.header("2. Ply 2 (Middle/Bottom)")
    mat2 = st.selectbox("Material 2", list(materials_db.keys()), index=2)
    t2 = st.slider("Thickness 2 (mm)", 0.5, 3.0, 1.2)

    st.header("3. Machine Settings")
    is_zinc = st.checkbox("Zinc Coated (GA/GI)?")
    d_tip = st.slider("Tip Diameter (mm)", 4.0, 10.0, 6.0)
    k_base = st.slider("Base k-factor", 0.10, 0.60, 0.35)
    expulsion_sens = st.slider("Expulsion Limit Factor", 1.2, 1.8, 1.4)

# --- CALCULATION PREPARATIONS ---
total_t = t1 + t2
t_min = min(t1, t2)
max_ce = max(materials_db[mat1]['ce'], materials_db[mat2]['ce'])

# Generate coordinate spaces for mapping contour projections
currents = np.linspace(5000, 13000, 50)  
times = np.linspace(3, 17, 40)
forces = np.linspace(100, 450, 40)

# ==============================================================================
# --- JAVA BRIDGE SUBPROCESS INTEROP EXECUTION ---
# Passes dynamic parameters safely to the compiled Java byteclass, listens
# for the standard stream output, and maps values back to Python instantly.
# ==============================================================================
def execute_java_calculation(curr, tm, frc):
    m1_props = materials_db[mat1]
    m2_props = materials_db[mat2]
    
    cmd = [
        "java", "WeldEngine",
        str(t1), str(m1_props["res_factor"]), str(m1_props["k_mod"]),
        str(t2), str(m2_props["res_factor"]), str(m2_props["k_mod"]),
        str(is_zinc).lower(), str(d_tip), str(k_base),
        str(curr), str(tm), str(frc)
    ]
    try:
        output = subprocess.check_output(cmd, text=True).strip()
        dia, target, exp = map(float, output.split("|"))
        return dia, target, exp
    except:
        # Fallback values if Java runtime is interrupted or still booting
        return 0.0, 4.0, 6.0

# --- CORE VISUALIZATION LOGIC LAYER ---
if graph_mode == "Complete 3D Volumetric Lobe":
    I, T, F = np.meshgrid(currents, times, forces)
    m1_p = materials_db[mat1]
    m2_p = materials_db[mat2]
    
    # Mathematical approximation matching background calculation loops
    k_approx = k_base * ((t1*m1_p["k_mod"] + t2*m2_p["k_mod"])/total_t) * ((t1*m1_p["res_factor"] + t2*m2_p["res_factor"])/total_t)
    if is_zinc: k_approx *= 0.82
    
    tip_eff = (6.0 / d_tip)**2 
    nugget_growth = k_approx * ((I * tip_eff)/10000)**2 * (T/10) * (300/F)**0.25 * 5.5
    target_min = 4 * np.sqrt(t_min)
    exp_limit_mesh = (5.5 * np.sqrt(t_min)) * (F / 300)**0.1 * (d_tip / 6.0)**0.2 * (expulsion_sens / 1.4)

    fig = go.Figure(data=go.Isosurface(
        x=I.flatten(), y=T.flatten(), z=F.flatten(),
        value=nugget_growth.flatten(),
        isomin=target_min, isomax=exp_limit_mesh.max(),
        surface_count=3, colorscale='Plasma', opacity=0.5,
        caps=dict(x_show=False, y_show=False),
        colorbar_title="Dia (mm)"
    ))
    fig.update_layout(
        scene=dict(xaxis_title='Current (A)', yaxis_title='Time (Cycles)', zaxis_title='Force (kg)'),
        margin=dict(l=0, r=0, b=0, t=40), height=700
    )

else:
    # 2D cross section calculation loops calling the Java Core Engine
    calc_dia, target_min, calc_expulsion = execute_java_calculation(active_current, active_time, active_force)
    tip_eff = (6.0 / d_tip)**2
    m1_p, m2_p = materials_db[mat1], materials_db[mat2]
    k_approx = k_base * ((t1*m1_p["k_mod"] + t2*m2_p["k_mod"])/total_t) * ((t1*m1_p["res_factor"] + t2*m2_p["res_factor"])/total_t)
    if is_zinc: k_approx *= 0.82
    
    if "X-Y Plane" in slice_plane:
        I_2d, T_2d = np.meshgrid(currents, times)
        nugget_growth_2d = k_approx * ((I_2d * tip_eff)/10000)**2 * (T_2d/10) * (300/slice_force)**0.25 * 5.5
        exp_limit_2d = (5.5 * np.sqrt(t_min)) * (slice_force / 300)**0.1 * (d_tip / 6.0)**0.2 * (expulsion_sens / 1.4)
        
        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, colorscale='Plasma', colorbar=dict(title='Dia (mm)')))
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, showscale=False, contours_coloring='none',
                                 contours=dict(start=target_min, end=target_min, coloring='none'), line=dict(color='cyan', width=4), name='Min Target'))
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, showscale=False, contours_coloring='none',
                                 contours=dict(start=exp_limit_2d, end=exp_limit_2d, coloring='none'), line=dict(color='red', width=4, dash='dash'), name='Expulsion'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_time], mode='markers', marker=dict(color='white', size=12, symbol='cross'), name='Operating Point'))
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Time (Cycles)", height=500, legend=dict(font=dict(color="white", size=12), bgcolor="rgba(0,0,0,0.65)"))
    else:
        I_2d, F_2d = np.meshgrid(currents, forces)
        nugget_growth_2d = k_approx * ((I_2d * tip_eff)/10000)**2 * (slice_time/10) * (300/F_2d)**0.25 * 5.5
        exp_limit_2d = (5.5 * np.sqrt(t_min)) * (F_2d / 300)**0.1 * (d_tip / 6.0)**0.2 * (expulsion_sens / 1.4)
        
        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=forces, z=nugget_growth_2d, colorscale='Plasma', colorbar=dict(title='Dia (mm)')))
        fig.add_trace(go.Contour(x=currents, y=forces, z=nugget_growth_2d, showscale=False, contours_coloring='none',
                                 contours=dict(start=target_min, end=target_min, coloring='none'), line=dict(color='cyan', width=4), name='Min Target'))
        fig.add_trace(go.Contour(x=currents, y=forces, z=(nugget_growth_2d - exp_limit_2d), showscale=False, contours_coloring='none',
                                 contours=dict(start=0, end=0, coloring='none'), line=dict(color='red', width=4, dash='dash'), name='Expulsion'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_force], mode='markers', marker=dict(color='white', size=12, symbol='cross'), name='Operating Point'))
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Force (kg)", height=500, legend=dict(font=dict(color="white", size=12), bgcolor="rgba(0,0,0,0.65)"))

    # --- SORPAS-STYLE GEOMETRIC ENGINE MAP ---
    sorpas_fig = go.Figure()
    width_box = d_tip * 2.5
    
    # Ply Stacks
    sorpas_fig.add_trace(go.Scatter(x=[-width_box, width_box, width_box, -width_box, -width_box], y=[0.0, 0.0, t1, t1, 0.0], fill="toself", fillcolor='rgba(100, 149, 237, 0.3)', line=dict(color='royalblue'), name=mat1))
    sorpas_fig.add_trace(go.Scatter(x=[-width_box, width_box, width_box, -width_box, -width_box], y=[-t2, -t2, 0.0, 0.0, -t2], fill="toself", fillcolor='rgba(144, 238, 144, 0.3)', line=dict(color='forestgreen'), name=mat2))
    
    # Electrode Tips
    ew = d_tip / 2.0
    sorpas_fig.add_trace(go.Scatter(x=[-ew, ew, ew*1.3, -ew*1.3, -ew], y=[t1, t1, t1+2, t1+2, t1], fill="toself", fillcolor='rgba(200,200,200,0.6)', name="Top Tip"))
    sorpas_fig.add_trace(go.Scatter(x=[-ew, ew, ew*1.3, -ew*1.3, -ew], y=[-t2, -t2, -t2-2, -t2-2, -t2], fill="toself", fillcolor='rgba(200,200,200,0.6)', name="Bottom Tip"))

    if calc_dia > 0.1:
        r_nugget = calc_dia / 2.0
        h_penetration = (total_t * 0.75) / 2.0
        mid_y = (t1 - t2) / 2.0
        theta = np.linspace(0, 2*np.pi, 100)
        
        n_color = 'rgba(255, 0, 0, 0.85)' if calc_dia >= calc_expulsion else 'rgba(148, 0, 211, 0.85)'
        # Heat Affected Zone Mapping
        sorpas_fig.add_trace(go.Scatter(x=r_nugget*1.25*np.cos(theta), y=mid_y + h_penetration*1.15*np.sin(theta), fill="toself", fillcolor='rgba(255,140,0,0.3)', name="HAZ"))
        # Core Liquid Pool Fusion Zone
        sorpas_fig.add_trace(go.Scatter(x=r_nugget*np.cos(theta), y=mid_y + h_penetration*np.sin(theta), fill="toself", fillcolor=n_color, line=dict(color='yellow'), name="Weld Pool"))

    sorpas_fig.update_layout(title=f"SORPAS Simulation (Java Core Engine)", template="plotly_dark", height=500, yaxis=dict(scaleanchor="x", scaleratio=1))

# --- SCREEN PACKAGING ---
if graph_mode == "Complete 3D Volumetric Lobe":
    col1, col2 = st.columns([3, 1])
    with col1: st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Weldability Matrix")
        st.metric("Total Stack", f"{round(total_t,2)}mm")
        st.metric("Min Target Dia", f"{round(target_min,2)}mm")
else:
    col1, col2 = st.columns([1, 1])
    with col1: st.plotly_chart(fig, use_container_width=True)
    with col2: st.plotly_chart(sorpas_fig, use_container_width=True)
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Java Nugget Size", f"{round(calc_dia,3)} mm")
    m2.metric("Min Limit", f"{round(target_min,2)} mm")
    m3.metric("Expulsion Bound", f"{round(calc_expulsion,2)} mm")
