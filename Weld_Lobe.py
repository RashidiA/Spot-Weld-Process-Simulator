# Asari-Rashidi Spot Welding Model (Special Edition - Strength Prediction Mode)
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components

# --- CONFIGURATION ---
st.set_page_config(page_title="Spot Welding Lobe Simulator", layout="wide")
st.title("🔬 Real-Time Transient Nugget Growth & Strength Simulator")

# --- MATERIAL DATABASE WITH MECHANICAL PROPERTIES ---
materials_db = {
    "Mild Steel (JSC270)": {"res_factor": 1.0, "k_mod": 1.0, "ce": 0.08, "uts": 270},
    "High Strength (JSC440)": {"res_factor": 1.15, "k_mod": 1.05, "ce": 0.14, "uts": 440},
    "DP600 (Dual Phase)": {"res_factor": 1.35, "k_mod": 1.12, "ce": 0.18, "uts": 600},
    "DP980 (Ultra High Strength)": {"res_factor": 1.50, "k_mod": 1.20, "ce": 0.24, "uts": 980},
    "Boron Steel (Usibor 1500)": {"res_factor": 1.65, "k_mod": 1.25, "ce": 0.35, "uts": 1500},
    "Trip Steel (TRIP780)": {"res_factor": 1.40, "k_mod": 1.15, "ce": 0.22, "uts": 780}
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
    
    # Ply 1 (Top)
    mat1 = st.selectbox("Ply 1 Material (Top)", list(materials_db.keys()))
    t1 = st.slider("Thickness 1 (mm)", 0.5, 3.0, 1.0)
    
    # Ply 2 (Middle/Bottom)
    mat2 = st.selectbox("Ply 2 Material (Middle)", list(materials_db.keys()), index=2)
    t2 = st.slider("Thickness 2 (mm)", 0.5, 3.0, 1.2)

    # Ply 3 (Optional Bottom Layer)
    ply3_options = ["None (Revert to 2-Ply)"] + list(materials_db.keys())
    mat3_selection = st.selectbox("Ply 3 Material (Bottom)", ply3_options, index=0)
    
    use_ply3 = mat3_selection != "None (Revert to 2-Ply)"
    if use_ply3:
        t3 = st.slider("Thickness 3 (mm)", 0.5, 3.0, 0.8)
    else:
        t3 = 0.0

    st.header("2. Electrodes & Scalers")
    is_zinc = st.checkbox("Zinc Coated (GA/GI)?")
    d_tip = st.slider("Tip Diameter (mm)", 4.0, 10.0, 6.0)
    k_base = st.slider("Base k-factor", 0.10, 0.60, 0.35)

# --- MATHEMATICAL COMPILATION ENGINE ---
m1_p = materials_db[mat1]
m2_p = materials_db[mat2]

if use_ply3:
    m3_p = materials_db[mat3_selection]
    total_t = t1 + t2 + t3
    t_min = min(t1, t2, t3)
    
    k_mod_weighted = (t1 * m1_p["k_mod"] + t2 * m2_p["k_mod"] + t3 * m3_p["k_mod"]) / total_t
    res_weighted = (t1 * m1_p["res_factor"] + t2 * m2_p["res_factor"] + t3 * m3_p["res_factor"]) / total_t
    # Thickness-weighted ultimate tensile strength calculation
    uts_weighted = (t1 * m1_p["uts"] + t2 * m2_p["uts"] + t3 * m3_p["uts"]) / total_t
else:
    total_t = t1 + t2
    t_min = min(t1, t2)
    k_mod_weighted = (t1 * m1_p["k_mod"] + t2 * m2_p["k_mod"]) / total_t
    res_weighted = (t1 * m1_p["res_factor"] + t2 * m2_p["res_factor"]) / total_t
    uts_weighted = (t1 * m1_p["uts"] + t2 * m2_p["uts"]) / total_t

k_approx = k_base * k_mod_weighted * res_weighted
if is_zinc: 
    k_approx *= 0.82

tip_eff = (6.0 / d_tip)**2
target_min = 4 * np.sqrt(t_min)

# --- GRID CONTROLLER AXES ---
currents = np.linspace(5000, 13000, 50)  
times = np.linspace(3, 24, 40)
forces = np.linspace(100, 450, 40)

# --- 3D ISOSURFACE LOOPS ---
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
        margin=dict(l=0, r=0, b=0, t=40), height=700, template="plotly_dark"
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 2D CROSS-SECTION PLANE INTERACTIVE VIEW ---
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
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Weld Time (Cycles)", template="plotly_dark", height=460, margin=dict(l=40, r=40, b=40, t=40), legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
    
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
        fig.update_layout(xaxis_title="Current (A)", yaxis_title="Force (kg)", template="plotly_dark", height=460, margin=dict(l=40, r=40, b=40, t=40), legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))

    # --- SANITIZED TRANSIENT 3-PLY CANVAS EMULATOR ---
    ply3_legend_html = "<div style='display: flex; align-items: center; gap: 4px;'><span style='width: 10px; height: 7px; background-color: rgba(220,160,220,0.25); border:1px solid rgba(220,160,220,0.7);'></span> Ply 3</div>" if use_ply3 else ""
    
    canvas_html = """
    <div style="background-color: #111111; padding: 12px 15px; border-radius: 8px; font-family: sans-serif; color: white; display: flex; flex-direction: column; height: 460px; box-sizing: border-box; justify-content: space-between;">
        <h4 style="margin: 0; color: #E0E0E0; font-size: 14px; font-weight: 600;">Transient Nugget Thermal Development Map (Multi-Ply Mode)</h4>
        
        <div style="display: flex; gap: 15px; align-items: center; justify-content: center; flex-grow: 1; margin: 5px 0;">
            <canvas id="weldCanvas" width="440" height="270" style="background-color: #1e1e1e; border: 1px solid #333; border-radius: 4px;"></canvas>
            
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 40px;">
                <span style="font-size: 10px; font-weight: bold; color: #ffffff; margin-bottom: 3px;">1530°C</span>
                <div style="width: 14px; height: 210px; background: linear-gradient(to top, #4b0082, #9400d3, #ffcc00, #ff4500, #ffffff); border: 1px solid #555; border-radius: 2px;"></div>
                <span style="font-size: 10px; font-weight: bold; color: #888888; margin-top: 3px;">25°C</span>
                <div style="font-size: 8px; color: #aaaaaa; letter-spacing: 0.5px; writing-mode: vertical-rl; text-orientation: mixed; margin-top: 6px; text-transform: uppercase;">Temperature</div>
            </div>
        </div>
        
        <div>
            <div style="display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; font-size: 10px; color: #BBBBBB; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 7px; background-color: rgba(100,149,237,0.25); border:1px solid rgba(100,149,237,0.7);"></span> Ply 1</div>
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 7px; background-color: rgba(144,238,144,0.25); border:1px solid rgba(144,238,144,0.7);"></span> Ply 2</div>
                """ + ply3_legend_html + """
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 7px; background: linear-gradient(to right, #ff4500, #b4b4b4);"></span> Tip Thermal</div>
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 7px; background-color: rgba(255,140,0,0.22);"></span> HAZ</div>
                <div style="display: flex; align-items: center; gap: 4px;"><span style="width: 10px; height: 7px; background: radial-gradient(#fff, #9400d3); border:1px solid #ffff00;"></span> Melt Pool</div>
            </div>

            <div style="display: flex; gap: 12px; align-items: center; justify-content: center; height: 32px;">
                <button onclick="startSimulationPlayback()" style="background-color: #007bff; color: white; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 12px;">▶ Play Growth</button>
                <button onclick="stopSimulationPlayback()" style="background-color: #6c757d; color: white; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 12px;">⏸ Pause</button>
                <span id="cycleLabel" style="font-size: 13px; color: #00ffff; font-family: monospace; font-weight: bold; min-width: 150px;">Ready</span>
            </div>
        </div>
    </div>

    <script>
        const t1 = """ + str(t1) + """;
        const t2 = """ + str(t2) + """;
        const t3 = """ + str(t3) + """;
        const usePly3 = """ + str(use_ply3).lower() + """;
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
            const tMin = usePly3 ? Math.min(t1, t2, t3) : Math.min(t1, t2);
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
            const scale = 32; 
            const wBox = dTip * 2.8 * scale;
            
            const h1 = t1 * scale;
            const h2 = t2 * scale;
            const h3 = t3 * scale;
            
            const tipRadiusX = (dTip / 2) * scale;
            const dia = data.diameter;
            const expulsion = data.expulsion;
            const thermalProgress = data.cycle / maxTime;

            const totalStackH = usePly3 ? (h1 + h2 + h3) : (h1 + h2);
            let currentYCursor = centerY - (totalStackH / 2);

            // --- 1. MATERIAL PLY STRUCTURES ---
            ctx.fillStyle = 'rgba(100, 149, 237, 0.25)';
            ctx.strokeStyle = 'rgba(100, 149, 237, 0.7)';
            ctx.lineWidth = 1.5;
            ctx.fillRect(centerX - wBox/2, currentYCursor, wBox, h1);
            ctx.strokeRect(centerX - wBox/2, currentYCursor, wBox, h1);
            const topTipY = currentYCursor;
            currentYCursor += h1;

            ctx.fillStyle = 'rgba(144, 238, 144, 0.25)';
            ctx.strokeStyle = 'rgba(144, 238, 144, 0.7)';
            ctx.fillRect(centerX - wBox/2, currentYCursor, wBox, h2);
            ctx.strokeRect(centerX - wBox/2, currentYCursor, wBox, h2);
            const nuggetCenterY = currentYCursor + (usePly3 ? (h2 / 2) : 0);
            currentYCursor += h2;

            if (usePly3) {
                ctx.fillStyle = 'rgba(220, 160, 220, 0.25)';
                ctx.strokeStyle = 'rgba(220, 160, 220, 0.7)';
                ctx.fillRect(centerX - wBox/2, currentYCursor, wBox, h3);
                ctx.strokeRect(centerX - wBox/2, currentYCursor, wBox, h3);
                currentYCursor += h3;
            }
            const botTipY = currentYCursor;

            // --- 2. ELECTRODES TRANSIENT THERMAL FOOTPRINTS ---
            let topGrad = ctx.createLinearGradient(centerX, topTipY, centerX, topTipY - 30);
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
            ctx.moveTo(centerX - tipRadiusX, topTipY);
            ctx.lineTo(centerX + tipRadiusX, topTipY);
            ctx.lineTo(centerX + tipRadiusX * 1.4, topTipY - 30);
            ctx.lineTo(centerX - tipRadiusX * 1.4, topTipY - 30);
            ctx.closePath();
            ctx.fill();

            let botGrad = ctx.createLinearGradient(centerX, botTipY, centerX, botTipY + 30);
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
            ctx.moveTo(centerX - tipRadiusX, botTipY);
            ctx.lineTo(centerX + tipRadiusX, botTipY);
            ctx.lineTo(centerX + tipRadiusX * 1.4, botTipY + 30);
            ctx.lineTo(centerX - tipRadiusX * 1.4, botTipY + 30);
            ctx.closePath();
            ctx.fill();

            // --- 3. DYNAMIC METRIC NUGGET & HAZ SHIFT ---
            if (dia > 0.05) {
                const rNugget = (dia / 2) * scale;
                const penetrationProgress = Math.min(1.0, 0.4 + (data.cycle / maxTime) * 0.6);
                const hPenetration = ((totalStackH * 0.76) / 2) * penetrationProgress;

                ctx.fillStyle = 'rgba(255, 140, 0, 0.22)';
                ctx.beginPath();
                ctx.ellipse(centerX, nuggetCenterY, rNugget * 1.28, hPenetration * 1.15, 0, 0, 2 * Math.PI);
                ctx.fill();

                let poolGrad = ctx.createRadialGradient(centerX, nuggetCenterY, rNugget * 0.1, centerX, nuggetCenterY, rNugget);
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
                ctx.ellipse(centerX, nuggetCenterY, rNugget, hPenetration, 0, 0, 2 * Math.PI);
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

    # --- PERFECT ALIGNED LAYOUT COLUMNS ---
    col1, col2 = st.columns([1, 1])
    with col1: 
        st.plotly_chart(fig, use_container_width=True)
    with col2: 
        components.html(canvas_html, height=460)
        
    st.divider()
    
    # Bottom Analytic Metrics Cards
    tip_eff_calc = (6.0 / d_tip)**2
    final_dia_calc = k_approx * ((active_current * tip_eff_calc)/10000)**2 * (active_time/10) * (300/active_force)**0.25 * 5.5
    expulsion_threshold_calc = (5.5 * np.sqrt(t_min)) * (active_force / 300)**0.1 * (d_tip / 6.0)**0.2
    
    # Calculate Predicted Tensile Shear Strength (kN)
    # Area = (pi * d^2) / 4. Force = Area * UTS. Divide by 1000 for kN.
    predicted_shear_force = (np.pi * (final_dia_calc ** 2) / 4.0) * uts_weighted / 1000.0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Final Cycle Size", f"{round(final_dia_calc, 3)} mm")
    m2.metric("Target Minimum Bound", f"{round(target_min, 2)} mm")
    m3.metric("Expulsion Threshold Limit", f"{round(expulsion_threshold_calc, 2)} mm")
    m4.metric("Est. Shear Strength (TSS)", f"{round(predicted_shear_force, 2)} kN")
