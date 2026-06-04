# Asari-Rashidi 3-Ply Model (Transient Simulation Hybrid Version)
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import subprocess
import os

# --- AUTOMATIC JAVA COMPILATION ON CLOUD RUNTIME ---
if not os.path.exists("WeldEngine.class"):
    try:
        subprocess.check_call(["javac", "WeldEngine.java"])
    except Exception as e:
        st.error(f"⚠️ Failed to compile WeldEngine.java: {e}")

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
        # Fallback values
        return [{"cycle": 1, "diameter": 0.0, "min_target": 4.0, "expulsion": 6.0}]

# --- PROCESS CALCULATIONS & VISUALIZATION ---
total_t = t1 + t2
t_min = min(t1, t2)
currents = np.linspace(5000, 13000, 50)  
times = np.linspace(3, 24, 40)
forces = np.linspace(100, 450, 40)

if graph_mode == "Complete 3D Volumetric Lobe":
    # (Standard static 3D code stays intact for macroscopic view analysis)
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
        exp_limit_2d = (5.5 * np.sqrt(t_min)) * (slice_force / 300)**0.1 * (d_tip / 6.0)**0.2
        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, colorscale='Plasma'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_time], mode='markers', marker=dict(color='white', size=12, symbol='cross'), name='Operating Point'))
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Weld Time (Cycles)", template="plotly_dark", height=500)
    else:
        I_2d, F_2d = np.meshgrid(currents, forces)
        nugget_growth_2d = k_approx * ((I_2d * tip_eff)/10000)**2 * (slice_time/10) * (300/F_2d)**0.25 * 5.5
        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=forces, z=nugget_growth_2d, colorscale='Plasma'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_force], mode='markers', marker=dict(color='white', size=12, symbol='cross'), name='Operating Point'))
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Force (kg)", template="plotly_dark", height=500)

    # --- TRANSIENT SORPAS ANIMATED COUPLING SYSTEM ---
    sorpas_fig = go.Figure()
    width_box = d_tip * 2.5
    mid_y = (t1 - t2) / 2.0
    theta = np.linspace(0, 2*np.pi, 100)

    # Base Base Frame Traces (Static Metal Plates and Copper Terminals)
    base_traces = [
        go.Scatter(x=[-width_box, width_box, width_box, -width_box, -width_box], y=[0.0, 0.0, t1, t1, 0.0], fill="toself", fillcolor='rgba(100, 149, 237, 0.25)', line=dict(color='royalblue'), name=mat1),
        go.Scatter(x=[-width_box, width_box, width_box, -width_box, -width_box], y=[-t2, -t2, 0.0, 0.0, -t2], fill="toself", fillcolor='rgba(144, 238, 144, 0.25)', line=dict(color='forestgreen'), name=mat2),
        go.Scatter(x=[-d_tip/2, d_tip/2, d_tip/2*1.3, -d_tip/2*1.3, -d_tip/2], y=[t1, t1, t1+1.5, t1+1.5, t1], fill="toself", fillcolor='rgba(180,180,180,0.6)', name="Top Tip"),
        go.Scatter(x=[-d_tip/2, d_tip/2, d_tip/2*1.3, -d_tip/2*1.3, -d_tip/2], y=[-t2, -t2, -t2-1.5, -t2-1.5, -t2], fill="toself", fillcolor='rgba(180,180,180,0.6)', name="Bottom Tip")
    ]
    
    # Define animation frames array structure
    frames = []
    for step in simulation_timeline:
        frame_data = list(base_traces)
        dia = step["diameter"]
        exp_limit = step["expulsion"]
        
        if dia > 0.1:
            r_nugget = dia / 2.0
            # Dynamic height penetration directly linked to current timestep development
            h_penetration = (total_t * 0.75) / 2.0 * min(1.0, 0.4 + (step["cycle"] / active_time) * 0.6)
            
            n_color = 'rgba(255, 0, 0, 0.9)' if dia >= exp_limit else 'rgba(148, 0, 211, 0.85)'
            
            # HAZ expansion shell trace
            frame_data.append(go.Scatter(x=r_nugget * 1.25 * np.cos(theta), y=mid_y + h_penetration * 1.15 * np.sin(theta), fill="toself", fillcolor='rgba(255,140,0,0.25)', name="HAZ Zone"))
            # Inner core molten trace pool
            frame_data.append(go.Scatter(x=r_nugget * np.cos(theta), y=mid_y + h_penetration * np.sin(theta), fill="toself", fillcolor=n_color, line=dict(color='yellow', width=1.5), name=f"Liquid Pool ({round(dia,2)}mm)"))
        else:
            # Empty placeholders to keep frame index synchronization consistent
            frame_data.append(go.Scatter(x=[0], y=[0], mode='markers', opacity=0, name="HAZ Zone"))
            frame_data.append(go.Scatter(x=[0], y=[0], mode='markers', opacity=0, name="Liquid Pool"))

        frames.append(go.Frame(data=frame_data, name=f"cycle_{step['cycle']}"))

    # Add initial starting frame trace objects to load canvas base layer
    for trace in base_traces:
        sorpas_fig.add_trace(trace)
    
    # Append dynamic calculated sequence arrays to drawing container
    final_step = simulation_timeline[-1]
    r_n = final_step["diameter"] / 2.0
    h_p = (total_t * 0.75) / 2.0
    col_n = 'rgba(255, 0, 0, 0.9)' if final_step["diameter"] >= final_step["expulsion"] else 'rgba(148, 0, 211, 0.85)'
    
    sorpas_fig.add_trace(go.Scatter(x=r_n * 1.25 * np.cos(theta), y=mid_y + h_p * 1.15 * np.sin(theta), fill="toself", fillcolor='rgba(255,140,0,0.25)', name="HAZ Zone"))
    sorpas_fig.add_trace(go.Scatter(x=r_n * np.cos(theta), y=mid_y + h_p * np.sin(theta), fill="toself", fillcolor=col_n, line=dict(color='yellow'), name="Liquid Pool"))

    sorpas_fig.frames = frames

    # --- VIDEO PLAYER CONTROLLERS LAYOUT ---
    sorpas_fig.update_layout(
        title="Transient Nugget Thermal Development Map",
        template="plotly_dark", height=500,
        yaxis=dict(scaleanchor="x", scaleratio=1, range=[-t2 - 2, t1 + 2]),
        xaxis=dict(range=[-width_box, width_box]),
        updatemenus=[dict(
            type="buttons", showactive=False, direction="right",
            x=0.1, y=-0.15, xanchor="left", yanchor="top",
            buttons=[
                dict(label="▶ Play Growth", method="animate", args=[None, dict(frame=dict(duration=80, redraw=True), fromcurrent=True, transition=dict(duration=0))]),
                dict(label="⏸ Pause", method="animate", args=[[null], dict(frame=dict(duration=0, redraw=False), mode="immediate", transition=dict(duration=0))])
            ]
        )],
        sliders=[dict(
            steps=[dict(method="animate", args=[[f"cycle_{s['cycle']}"], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))], label=f"Cy:{s['cycle']}") for s in simulation_timeline],
            x=0.4, y=-0.12, currentvalue=dict(font=dict(size=12, color="cyan"), prefix="Time Progress: ", visible=True)
        )]
    )

    # --- SCREEN PRESENTATION LAYOUT ---
    col1, col2 = st.columns([1, 1])
    with col1:
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.plotly_chart(sorpas_fig, use_container_width=True)
        
    st.divider()
    last_res = simulation_timeline[-1]
    m1, m2, m3 = st.columns(3)
    m1.metric("Final Cycle Size", f"{round(last_res['diameter'], 3)} mm")
    m2.metric("Target Minimum Bound", f"{round(last_res['min_target'], 2)} mm")
    m3.metric("Expulsion Threshold Limit", f"{round(last_res['expulsion'], 2)} mm")
