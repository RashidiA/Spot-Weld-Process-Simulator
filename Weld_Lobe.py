# Asari-Rashidi 3-Ply Model (Thermal Analytics Edition)
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components

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

# --- GLOBAL MACROS AND CONSTANTS ---
total_t = t1 + t2
t_min = min(t1, t2)
currents = np.linspace(5000, 13000, 50)  
times = np.linspace(3, 24, 40)
forces = np.linspace(100, 450, 40)

m1_p, m2_p = materials_db[mat1], materials_db[mat2]
k_approx = k_base * ((t1*m1_p["k_mod"] + t2*m2_p["k_mod"])/total_t) * ((t1*m1_p["res_factor"] + t2*m2_p["res_factor"])/total_t)
if is_zinc: k_approx *= 0.82
tip_eff = (6.0 / d_tip)**2
target_min = 4 * np.sqrt(t_min)

# --- STATIC LOBE GENERATION ---
if graph_mode == "Complete 3D Volumetric Lobe":
    I, T, F = np.meshgrid(currents, times, forces)
    nugget_growth = k_approx * ((I * tip_eff)/10000)**2 * (T/10) * (300/F)**0.25 * 5.5
    
    fig = go.Figure(data=go.Isosurface(
        x=I.flatten(), y=T.flatten(), z=F.flatten(), value=nugget_growth.flatten(),
        isomin=target_min, isomax=target_min*2.5, surface_count=4, colorscale='Plasma', opacity=0.4,
        colorbar_title="Dia (mm)"
    ))
    fig.update_layout(
        scene=dict(xaxis_title='Current (A)', yaxis_title='Time (Cycles)', zaxis_title='Force (kg)'),
        margin=dict(l=0, r=0, b=0, t=40), height=850, template="plotly_dark"
    )
    st.plotly_chart(fig, use_container_width=True)

else:
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

    # --- IN-BROWSER TRANSIENT ENGINE EMBED ---
    canvas_html = """
    <div style="background-color: #111111; padding: 15px; border-radius: 8px; font-family: sans-serif; color: white; display: flex; flex-direction: column; height: 530px; box-sizing: border-box;">
        <h4 style="margin: 0 0 12px 0; color: #E0E0E0; font-size: 15px;">Transient Nugget Thermal Development Map</h4>
        
        <div style="display: flex; gap: 20px; align-items: flex-start; justify-content: center;">
            <canvas id="weldCanvas" width="460" height="340" style="background-color: #1e1e1e; border: 1px solid #333; border-radius: 4px;"></canvas>
            
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 45px; padding-top: 10px;">
                <span style="font-size: 10px; font-weight: bold; color: #ffffff; margin-bottom: 4px;">1530°C</span>
                <div style="width: 16px; height: 280px; background: linear-gradient(to top, #4b0082, #9400d3, #ffcc00, #ff4500, #ffffff); border: 1px solid #555; border-radius: 2px;"></div>
                <span style="font-size: 10px; font-weight: bold; color: #888888; margin-top: 4px;">25°C</span>
                <div style="font-size: 9px; color: #aaaaaa; letter-spacing: 1px; writing-mode: vertical-rl; text-orientation: mixed; margin-top: 8px; text-transform: uppercase;">Temperature</div>
            </div>
        </div>
        
        <div style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; font-size: 11px; color: #BBBBBB;">
            <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 12px; height: 8px; background-color: rgba(100,149,237,0.25); border:1px solid rgba(100,149,237,0.7);"></span> Ply 1</div>
            <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 12px; height: 8px; background-color: rgba(144,238,144,0.25); border:1px solid rgba(144,238,144,0.7);"></span> Ply 2</div>
            <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 12px; height: 8px; background: linear-gradient(to right, #ff4500, #b4b4b4);"></span> Tip Thermal</div>
            <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 12px; height: 8px; background-color: rgba(255,140,0,0.22);"></span> HAZ Boundary</div>
            <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 12px; height: 8px; background: radial-gradient(#fff, #9400d3); border:1px solid #ffff00;"></span> Melt Pool</div>
        </div>

        <div style="margin-top: 15px; display: flex; gap: 12px; align-items: center; justify-content: center;">
            <button onclick="startSimulationPlayback()" style="background-color: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px;">▶ Play Growth</button>
            <button onclick="stopSimulationPlayback()" style="background-color: #6c757d; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px;">⏸ Pause</button>
            <span id="cycleLabel" style="font-size: 14px; color: #00ffff; font-family: monospace; font-weight: bold; min-width: 160px;">Ready</span>
        </div>
    </div>

    <script>
        const t1 = """ + str(t1) + """;
        const t2 = """ + str(t2) + """;
        const dTip = """ + str(d_tip) + """;
        const maxTime = """ + str(active_time) + """;
        const currentI = """ + str(active_current) + """;
        const forceF = """ + str(active_force) + """;
        const kApprox = """ + str(k_approx) + """;
        const targetMin = """ + str(target_min) + """;

        const canvas = document.getElementById('weldCanvas');
        const ctx = canvas.getContext('2d');
        let currentFrameIndex = 0;
        let isPlaying = false;
        let animationTimer = null;
        let simData = [];

        function computeTransientTimeline() {
            simData = [];
            const tipEff = Math.pow(6.0 / dTip, 2);
            const tMin = Math.min(t1, t2);
            const expulsionThreshold = (5.5 * Math.sqrt(tMin)) * Math.pow(forceF / 300, 0.1) * Math.pow(dTip / 6.0, 0.2);

            for (let c = 1; c <= maxTime; c++) {
                let transientDiameter = kApprox * Math.pow((currentI * tipEff) / 10000, 2) * (c / 10) * Math.pow(300 / forceF, 0.25) * 5.5;
                if (transientDiameter < 0.1) transientDiameter = 0.0;
                
                simData.push({
                    cycle: c,
                    diameter: transientDiameter,
                    min_target: targetMin,
                    expulsion: expulsionThreshold
                });
            }
        }

        function drawFrame(index) {
            if (simData.length === 0) return;
            const data = simData[index];
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const scale = 38;
            const wBox = dTip * 2.8 * scale;
            const h1 = t1 * scale;
            const h2 = t2 * scale;
            const tipRadiusX = (dTip / 2) * scale;
            const dia = data.diameter;
            const expulsion = data.expulsion;
            const thermalProgress = data.cycle / maxTime;

            // --- 1. PLY LAYERS ---
            ctx.fillStyle = 'rgba(100, 149, 237, 0.25)';
            ctx.strokeStyle = 'rgba(100, 149, 237, 0.7)';
            ctx.lineWidth = 1.5;
            ctx.fillRect(centerX - wBox/2, centerY - h1, wBox, h1);
            ctx.strokeRect(centerX - wBox/2, centerY - h1, wBox, h1);

            ctx.fillStyle = 'rgba(144, 238, 144, 0.25)';
            ctx.strokeStyle = 'rgba(144, 238, 144, 0.7)';
            ctx.fillRect(centerX - wBox/2, centerY, wBox, h2);
            ctx.strokeRect(centerX - wBox/2, centerY, wBox, h2);

            // --- 2. ELECTRODES HEAT FLUX GRADIENTS ---
            let topGrad = ctx.createLinearGradient(centerX, centerY - h1, centerX, centerY - h1 - 40);
            if (dia > 0) {
                let tipHeatColor = "rgba(" + Math.floor(200 + 55 * thermalProgress) + ", " + Math.floor(69 + 40 * thermalProgress) + ", 0, 0.85)";
                topGrad.addColorStop(0, tipHeatColor);
                topGrad.addColorStop(0.35 * thermalProgress, 'rgba(180, 70, 30, 0.8)');
                topGrad.addColorStop(1, 'rgba(180, 180, 180, 0.85)');
            } else {
                topGrad.addColorStop(0, 'rgba(180, 180, 180, 0.85)');
            }
            ctx.fillStyle = topGrad;
            ctx.beginPath();
            ctx.moveTo(centerX - tipRadiusX, centerY - h1);
            ctx.lineTo(centerX + tipRadiusX, centerY - h1);
            ctx.bezierCurveTo(centerX + tipRadiusX * 1.4, centerY - h1 - 5, centerX + tipRadiusX * 1.6, centerY - h1 - 25, centerX + tipRadiusX * 1.8, centerY - h1 - 40);
            ctx.lineTo(centerX - tipRadiusX * 1.8, centerY - h1 - 40);
            ctx.bezierCurveTo(centerX - tipRadiusX * 1.6, centerY - h1 - 25, centerX - tipRadiusX * 1.4, centerY - h1 - 5, centerX - tipRadiusX, centerY - h1);
            ctx.closePath();
            ctx.fill();

            let botGrad = ctx.createLinearGradient(centerX, centerY + h2, centerX, centerY + h2 + 40);
            if (dia > 0) {
                let tipHeatColor = "rgba(" + Math.floor(200 + 55 * thermalProgress) + ", " + Math.floor(69 + 40 * thermalProgress) + ", 0, 0.85)";
                botGrad.addColorStop(0, tipHeatColor);
                botGrad.addColorStop(0.35 * thermalProgress, 'rgba(180, 70, 30, 0.8)');
                botGrad.addColorStop(1, 'rgba(180, 180, 180, 0.85)');
            } else {
                botGrad.addColorStop(0, 'rgba(180, 180, 180, 0.85)');
            }
            ctx.fillStyle = botGrad;
            ctx.beginPath();
            ctx.moveTo(centerX - tipRadiusX, centerY + h2);
            ctx.lineTo(centerX + tipRadiusX, centerY + h2);
            ctx.bezierCurveTo(centerX + tipRadiusX * 1.4, centerY + h2 + 5, centerX + tipRadiusX * 1.6, centerY + h2 + 25, centerX + tipRadiusX * 1.8, centerY + h2 + 40);
            ctx.lineTo(centerX - tipRadiusX * 1.8, centerY + h2 + 40);
            ctx.bezierCurveTo(centerX - tipRadiusX * 1.6, centerY + h2 + 25, centerX - tipRadiusX * 1.4, centerY + h2 + 5, centerX - tipRadiusX, centerY + h2);
            ctx.closePath();
            ctx.fill();

            // --- 3. DYNAMIC TRANSIENT THERMAL MOLTEN POOL ---
            if (dia > 0.05) {
                const rNugget = (dia / 2) * scale;
                const penetrationProgress = Math.min(1.0, 0.4 + (data.cycle / maxTime) * 0.6);
                const hPenetration = (((t1 + t2) * 0.78) / 2) * scale * penetrationProgress;

                // HAZ Boundary
                ctx.fillStyle = 'rgba(255, 140, 0, 0.22)';
                ctx.beginPath();
                ctx.ellipse(centerX, centerY, rNugget * 1.28, hPenetration * 1.15, 0, 0, 2 * Math.PI);
                ctx.fill();

                // Core Pool Map
                let poolGrad = ctx.createRadialGradient(centerX, centerY, rNugget * 0.1, centerX, centerY, rNugget);
                if (dia >= expulsion) {
                    poolGrad.addColorStop(0, '#ffffff');
                    poolGrad.addColorStop(0.2, '#ffff00');
                    poolGrad.addColorStop(0.6, '#ff0000');
                    poolGrad.addColorStop(1, 'rgba(139, 0, 0, 0.9)');
                    ctx.strokeStyle = '#ff0000';
                } else {
                    poolGrad.addColorStop(0, '#ffffff');
                    poolGrad.addColorStop(0.25, '#ffcc00');
                    poolGrad.addColorStop(0.65, '#9400d3');
                    poolGrad.addColorStop(1, '#4b0082');
                    ctx.strokeStyle = '#ffff00';
                }
                
                ctx.fillStyle = poolGrad;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.ellipse(centerX, centerY, rNugget, hPenetration, 0, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
            }

            document.getElementById('cycleLabel').innerText = "Cycle: " + data.cycle + " / " + maxTime + " (" + dia.toFixed(2) + " mm)";
        }

        function playbackLoop() {
            if (!isPlaying) return;
            currentFrameIndex++;
            
            if (currentFrameIndex >= simData.length) {
                isPlaying = false;
                if (animationTimer) clearTimeout(animationTimer);
                return;
            }
            
            drawFrame(currentFrameIndex);
            animationTimer = setTimeout(playbackLoop, 120);
        }

        function startSimulationPlayback() {
            if (!isPlaying) {
                if (currentFrameIndex >= simData.length - 1) {
                    currentFrameIndex = 0;
                }
                isPlaying = true;
                playbackLoop();
            }
        }

        function stopSimulationPlayback() {
            isPlaying = false;
            if (animationTimer) clearTimeout(animationTimer);
        }

        computeTransientTimeline();
        drawFrame(0);
    </script>
    """

    col1, col2 = st.columns([1, 1])
    with col1: 
        st.plotly_chart(fig, use_container_width=True)
    with col2: 
        components.html(canvas_html, height=590)
        
    st.divider()
    
    # Dashboard Analytics Track
    tip_eff_calc = (6.0 / d_tip)**2
    final_dia_calc = k_approx * ((active_current * tip_eff_calc)/10000)**2 * (active_time/10) * (300/active_force)**0.25 * 5.5
    expulsion_threshold_calc = (5.5 * np.sqrt(t_min)) * (active_force / 300)**0.1 * (d_tip / 6.0)**0.2
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Final Cycle Size", f"{round(final_dia_calc, 3)} mm")
    m2.metric("Target Minimum Bound", f"{round(target_min, 2)} mm")
    m3.metric("Expulsion Threshold Limit", f"{round(expulsion_threshold_calc, 2)} mm")
