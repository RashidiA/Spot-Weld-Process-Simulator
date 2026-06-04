# Asari-Rashidi 3-Ply Model (Transient Simulation WebGL/Canvas Hybrid Edition)
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components
import subprocess
import os
import json

# --- AUTOMATIC JAVA COMPILATION ON CLOUD RUNTIME ---
if not os.path.exists("WeldEngine.class"):
    try:
        subprocess.check_call(["javac", "WeldEngine.java"])
    except Exception as e:
        st.error(f"⚠️ Failed to compile WeldEngine.java: {e}")

# --- CONFIGURATION ---
st.set_page_config(page_title="Asari-Rashidi SORPAS Time-Sim", layout="wide")
st.title("🔬 Real-Time Transient Nugget Growth Simulator (SORPAS WebGL/Canvas Mode)")

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
        isomin=target_min, isomax=target_min*2.5, surface_count=4, colorscale='Plasma', opacity=0.4,
        colorbar_title="Dia (mm)"
    ))
    fig.update_layout(
        scene=dict(xaxis_title='Current (A)', yaxis_title='Time (Cycles)', zaxis_title='Force (kg)'),
        margin=dict(l=0, r=0, b=0, t=40), height=850, template="plotly_dark"
    )
    
    col1, col2 = st.columns([3, 1])
    with col1: st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Weldability Matrix")
        st.metric("Total Stack", f"{round(total_t,2)}mm")
        st.metric("Min Target Dia", f"{round(target_min,2)}mm")

else:
    simulation_timeline = fetch_transient_java_data(active_current, active_time, active_force)
    m1_p, m2_p = materials_db[mat1], materials_db[mat2]
    k_approx = k_base * ((t1*m1_p["k_mod"] + t2*m2_p["k_mod"])/total_t) * ((t1*m1_p["res_factor"] + t2*m2_p["res_factor"])/total_t)
    if is_zinc: k_approx *= 0.82
    tip_eff = (6.0 / d_tip)**2
    target_min = 4 * np.sqrt(t_min)
    
    if "X-Y Plane" in slice_plane:
        I_2d, T_2d = np.meshgrid(currents, times)
        nugget_growth_2d = k_approx * ((I_2d * tip_eff)/10000)**2 * (T_2d/10) * (300/slice_force)**0.25 * 5.5
        exp_limit_2d = (5.5 * np.sqrt(t_min)) * (slice_force / 300)**0.1 * (d_tip / 6.0)**0.2

        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, colorscale='Plasma', colorbar=dict(title="Dia (mm)")))
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, showscale=False, contours_coloring='none',
                                 contours=dict(start=target_min, end=target_min), line=dict(color='cyan', width=4), name='Min Target'))
        fig.add_trace(go.Contour(x=currents, y=times, z=nugget_growth_2d, showscale=False, contours_coloring='none',
                                 contours=dict(start=exp_limit_2d, end=exp_limit_2d), line=dict(color='red', width=4, dash='dash'), name='Expulsion Limit'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_time], mode='markers', marker=dict(color='white', size=12, symbol='cross'), name='Operating Point'))
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Weld Time (Cycles)", template="plotly_dark", height=500, legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
    else:
        I_2d, F_2d = np.meshgrid(currents, forces)
        nugget_growth_2d = k_approx * ((I_2d * tip_eff)/10000)**2 * (slice_time/10) * (300/F_2d)**0.25 * 5.5
        exp_limit_2d = (5.5 * np.sqrt(t_min)) * (F_2d / 300)**0.1 * (d_tip / 6.0)**0.2

        fig = go.Figure()
        fig.add_trace(go.Contour(x=currents, y=forces, z=nugget_growth_2d, colorscale='Plasma', colorbar=dict(title="Dia (mm)")))
        fig.add_trace(go.Contour(x=currents, y=forces, z=nugget_growth_2d, showscale=False, contours_coloring='none',
                                 contours=dict(start=target_min, end=target_min), line=dict(color='cyan', width=4), name='Min Target'))
        fig.add_trace(go.Contour(x=currents, y=forces, z=(nugget_growth_2d - exp_limit_2d), showscale=False, contours_coloring='none',
                                 contours=dict(start=0, end=0), line=dict(color='red', width=4, dash='dash'), name='Expulsion Limit'))
        fig.add_trace(go.Scatter(x=[active_current], y=[active_force], mode='markers', marker=dict(color='white', size=12, symbol='cross'), name='Operating Point'))
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Force (kg)", template="plotly_dark", height=500, legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))

    # --- ADVANCED NATIVE HTML5 CANVAS EMBED (STABLE PARSING SETUP) ---
    canvas_html = """
    <div style="background-color: #111111; padding: 15px; border-radius: 8px; font-family: sans-serif; color: white; box-sizing: border-box; height: 490px;">
        <h4 style="margin-top: 0; margin-bottom: 12px; color: #E0E0E0; font-size: 15px;">Transient Nugget Thermal Development Map</h4>
        <canvas id="weldCanvas" width="540" height="360" style="background-color: #1e1e1e; border: 1px solid #333; display: block; margin: 0 auto; border-radius: 4px;"></canvas>
        
        <div style="margin-top: 15px; display: flex; gap: 12px; align-items: center; justify-content: center; height: 45px;">
            <button onclick="startSimulationPlayback()" style="background-color: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px;">▶ Play Growth</button>
            <button onclick="stopSimulationPlayback()" style="background-color: #6c757d; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px;">⏸ Pause</button>
            <span id="cycleLabel" style="font-size: 14px; color: #00ffff; margin-left: 10px; font-family: monospace; font-weight: bold; min-width: 180px;">Loading engine...</span>
        </div>
    </div>

    <script>
        const simData = """ + json.dumps(simulation_timeline) + """;
        const t1 = """ + str(t1) + """;
        const t2 = """ + str(t2) + """;
        const dTip = """ + str(d_tip) + """;
        const maxTime = """ + str(active_time) + """;
        
        const canvas = document.getElementById('weldCanvas');
        const ctx = canvas.getContext('2d');
        
        let currentFrameIndex = 0;
        let isPlaying = false;
        let animationTimer = null;

        function drawFrame(index) {
            if (index < 0) index = 0;
            if (index >= simData.length) index = simData.length - 1;
            const data = simData[index];
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const scale = 38; 
            
            const wBox = dTip * 2.5 * scale;
            const h1 = t1 * scale;
            const h2 = t2 * scale;
            const tipW = (dTip / 2) * scale;

            // Sheet 1 (Top Layer)
            ctx.fillStyle = 'rgba(100, 149, 237, 0.25)';
            ctx.strokeStyle = 'rgba(100, 149, 237, 0.7)';
            ctx.lineWidth = 1.5;
            ctx.fillRect(centerX - wBox/2, centerY - h1, wBox, h1);
            ctx.strokeRect(centerX - wBox/2, centerY - h1, wBox, h1);

            // Sheet 2 (Bottom Layer)
            ctx.fillStyle = 'rgba(144, 238, 144, 0.25)';
            ctx.strokeStyle = 'rgba(144, 238, 144, 0.7)';
            ctx.fillRect(centerX - wBox/2, centerY, wBox, h2);
            ctx.strokeRect(centerX - wBox/2, centerY, wBox, h2);

            // Curved Electrode Profile - Genuine SORPAS Geometry Mapping
            ctx.fillStyle = 'rgba(180, 180, 180, 0.7)';
            
            // Top Electrode
            ctx.beginPath();
            ctx.moveTo(centerX - tipW, centerY - h1);
            ctx.arc(centerX, centerY - h1 - tipW * 1.5, tipW * 1.8, 0.6 * Math.PI, 0.4 * Math.PI, true);
            ctx.lineTo(centerX + tipW * 1.25, centerY - h1 - 35);
            ctx.lineTo(centerX - tipW * 1.25, centerY - h1 - 35);
            ctx.closePath();
            ctx.fill();

            // Bottom Electrode
            ctx.beginPath();
            ctx.moveTo(centerX - tipW, centerY + h2);
            ctx.arc(centerX, centerY + h2 + tipW * 1.5, tipW * 1.8, 1.4 * Math.PI, 1.6 * Math.PI, false);
            ctx.lineTo(centerX + tipW * 1.25, centerY + h2 + 35);
            ctx.lineTo(centerX - tipW * 1.25, centerY + h2 + 35);
            ctx.closePath();
            ctx.fill();

            // Dynamic Core Weld Computation Layer
            const dia = data.diameter;
            const expulsion = data.expulsion;

            if (dia > 0.05) {
                const rNugget = (dia / 2) * scale;
                const penetrationProgress = Math.min(1.0, 0.4 + (data.cycle / maxTime) * 0.6);
                const hPenetration = (((t1 + t2) * 0.75) / 2) * scale * penetrationProgress;

                // Heat Affected Zone (HAZ Boundary)
                ctx.fillStyle = 'rgba(255, 140, 0, 0.25)';
                ctx.beginPath();
                ctx.ellipse(centerX, centerY, rNugget * 1.25, hPenetration * 1.15, 0, 0, 2 * Math.PI);
                ctx.fill();

                // Core Molten Metal Pool 
                ctx.fillStyle = (dia >= expulsion) ? 'rgba(255, 0, 0, 0.85)' : 'rgba(148, 0, 211, 0.85)';
                ctx.strokeStyle = '#ffff00';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.ellipse(centerX, centerY, rNugget, hPenetration, 0, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
            }

            // Standard JS Concatenation ensures Python never raises formatting errors here
            document.getElementById('cycleLabel').innerText = "Cycle: " + data.cycle + " / " + maxTime + " (" + dia.toFixed(2) + " mm)";
        }

        function playbackLoop() {
            if (!isPlaying) return;
            currentFrameIndex++;
            if (currentFrameIndex >= simData.length) {
                currentFrameIndex = 0; 
            }
            drawFrame(currentFrameIndex);
            animationTimer = setTimeout(playbackLoop, 110);
        }

        function startSimulationPlayback() {
            if (!isPlaying) {
                isPlaying = true;
                playbackLoop();
            }
        }

        function stopSimulationPlayback() {
            isPlaying = false;
            if (animationTimer) clearTimeout(animationTimer);
        }

        drawFrame(0);
    </script>
    """

    col1, col2 = st.columns([1, 1])
    with col1: 
        st.plotly_chart(fig, use_container_width=True)
    with col2: 
        # Generous frame display window allocation to avoid any button clipping
        components.html(canvas_html, height=560)
        
    st.divider()
    last_res = simulation_timeline[-1]
    m1, m2, m3 = st.columns(3)
    m1.metric("Final Cycle Size", f"{round(last_res['diameter'], 3)} mm")
    m2.metric("Target Minimum Bound", f"{round(last_res['min_target'], 2)} mm")
    m3.metric("Expulsion Threshold Limit", f"{round(last_res['expulsion'], 2)} mm")
