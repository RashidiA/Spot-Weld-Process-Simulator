# Asari-Rashidi Spot Welding Simulator v2
# Weld-lobe explorer (3D lobe + adjustable slice plane -> live 2D lobe) and
# SORPAS-style 2D axisymmetric transient process simulation (temperature field, nugget growth, dynamic resistance).
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import traceback
st.set_page_config(page_title="Spot Welding Lobe & Process Simulator", layout="wide")

def _show_error(where, exc):
    st.error(f"⚠️ {where} failed: {exc}")
    st.code(traceback.format_exc())

st.title("🔬 Spot Welding Lobe & 2D Process Simulator")
st.caption("3D weld lobe with an adjustable slice plane • 2D axisymmetric thermal simulation of nugget growth • learning tool (indicative results, not a replacement for validated FEA such as SORPAS)")

# ---------------- 2D thermal solver ----------------

DX = 0.2e-3           # grid size (m)
R_DOM = 10.0e-3       # simulated radius (m)
EL_H = 6.0e-3         # electrode height simulated (m)
EL_R = 8.0e-3         # electrode body radius (m)
T_AMB = 25.0
T_LIQ = 1500.0
T_HAZ = 727.0

_TT = np.arange(0, 2001, dtype=float)
# mild-steel properties vs temperature
_K_STEEL = np.interp(_TT, [0, 300, 600, 800, 1000, 1500, 2000], [52, 44, 34, 27, 28, 32, 34])
_RHO_STEEL = np.interp(_TT, [0, 200, 500, 800, 1000, 1500, 2000], [0.16, 0.26, 0.58, 1.05, 1.15, 1.25, 1.30]) * 1e-6
_C_STEEL = np.interp(_TT, [0, 500, 727, 800, 1500, 2000], [3.7e6, 4.6e6, 6.2e6, 5.2e6, 5.6e6, 5.6e6])
_C_STEEL = _C_STEEL + np.where((_TT > 1450) & (_TT < 1520), 2.1e9 / 70.0, 0.0)  # latent heat of fusion
_K_CU = np.full_like(_TT, 360.0)
_C_CU = np.full_like(_TT, 3.45e6)
_RHO_CU = np.interp(_TT, [0, 500, 1000], [0.017, 0.045, 0.08]) * 1e-6


def simulate_weld(layers, zinc, d_tip, force_kg, current, weld_cyc, pulses, cool_cyc, hold_cyc,
                  freq=50.0, heat_scale=1.0, contact_scale=1.0, stop_dia=0.0):
    """Axisymmetric transient electro-thermal model of a resistance spot weld.
    layers: tuple of (thickness_mm, resistivity_factor). Returns dict of results."""
    n_r = int(round(R_DOM / DX))
    n_el = int(round(EL_H / DX))
    rows = []   # material id per row: 1 = copper, 2.. = sheets
    resf = []
    for _ in range(n_el):
        rows.append(1); resf.append(1.0)
    iface = []  # row index where an interface starts (between row-1 and row)
    iface.append(('el', len(rows)))
    for li, (t_mm, rf) in enumerate(layers):
        n = max(2, int(round(t_mm * 1e-3 / DX)))
        for _ in range(n):
            rows.append(2 + li); resf.append(rf)
        if li < len(layers) - 1:
            iface.append(('fay', len(rows)))
    iface.append(('el', len(rows)))
    for _ in range(n_el):
        rows.append(1); resf.append(1.0)
    n_z = len(rows)
    mat = np.array(rows)[:, None] * np.ones((1, n_r), dtype=int)
    rf2 = np.array(resf)[:, None] * np.ones((1, n_r))
    r_c = (np.arange(n_r) + 0.5) * DX
    r_f = (np.arange(n_r + 1)) * DX

    a = d_tip * 1e-3 / 2.0
    top_sheet = n_el
    bot_sheet = n_z - n_el          # first electrode row below
    # electrode cone shape: radius grows 30 deg from face until body radius
    tan30 = np.tan(np.radians(30.0))
    active = np.ones((n_z, n_r), dtype=bool)
    el_rad = np.zeros(n_z)
    for z in range(n_z):
        if z < top_sheet:
            h = (top_sheet - 1 - z + 0.5) * DX
            rad = a + (EL_R - a) * (1.0 - np.exp(-h / 2.0e-3))
            active[z] = r_c <= rad
            el_rad[z] = rad
        elif z >= bot_sheet:
            h = (z - bot_sheet + 0.5) * DX
            rad = a + (EL_R - a) * (1.0 - np.exp(-h / 2.0e-3))
            active[z] = r_c <= rad
            el_rad[z] = rad
        else:
            el_rad[z] = R_DOM
    isCu = (mat == 1)
    kT_st, cT_st, rT_st = _K_STEEL, _C_STEEL, _RHO_STEEL

    T = np.full((n_z, n_r), T_AMB)
    force_N = force_kg * 9.81
    dt = 0.9 * DX * DX / (4.0 * 360.0 / 3.45e6)
    dt = min(dt, 1.0 / freq / 160.0)

    cycle = 1.0 / freq
    sched = []
    for p in range(int(pulses)):
        sched.append((current, weld_cyc * cycle))
        if p < pulses - 1 and cool_cyc > 0:
            sched.append((0.0, cool_cyc * cycle))
    if hold_cyc > 0:
        sched.append((0.0, hold_cyc * cycle))
    total_t = sum(d for _, d in sched)

    fay_scale = (0.7 if zinc else 1.0) * contact_scale
    el_scale = contact_scale
    rc_fay0 = 4.0e-9 * fay_scale
    rc_el0 = 1.6e-9 * el_scale
    F_ref = 2500.0
    a_cur = a * 1.05
    snap_every = max(1, int(round(1e-3 / dt)))
    rec_every = max(1, int(round(1e-3 / dt)))

    cond_mask = (active & (mat > 0)).astype(float)
    # precompute radial geometry factors
    rf_ = r_f[1:-1]
    vol_fac = (r_c * DX)
    snaps, snap_t = [T.astype(np.float32).copy()], [0.0]
    rec = {'t': [], 'dia': [], 'pen': [], 'tmax': [], 'rdyn': [], 'I': []}
    t = 0.0
    step = 0
    zeros0 = np.zeros_like(T)
    stopped, stop_t = False, None
    J2 = None
    Ji2 = None
    for I, dur in sched:
        n_steps = max(1, int(round(dur / dt)))
        for _ in range(n_steps):
            idx = np.clip(T, 0, 2000).astype(np.int32)
            k = np.where(isCu, _K_CU[idx], kT_st[idx]) * active
            C = np.where(isCu, _C_CU[idx], cT_st[idx])
            # harmonic face conductivities
            kz = 2 * k[1:] * k[:-1] / (k[1:] + k[:-1] + 1e-12)
            kr = 2 * k[:, 1:] * k[:, :-1] / (k[:, 1:] + k[:, :-1] + 1e-12)
            dTz = T[1:] - T[:-1]
            Fz = kz * dTz / DX
            div = np.zeros_like(T)
            div[:-1] += Fz / DX
            div[1:] -= Fz / DX
            Fr = kr * (T[:, 1:] - T[:, :-1]) / DX * rf_
            divr = np.zeros_like(T)
            divr[:, :-1] += Fr
            divr[:, 1:] -= Fr
            div += divr / (vol_fac)
            q = None
            if I > 0:
                # current-carrying radius grows with the molten nugget
                if (step % 40) == 0 or J2 is None:
                    sh = T[top_sheet:bot_sheet] >= T_LIQ
                    rn = (sh.any(axis=0).nonzero()[0].max() + 1) * DX if sh.any() else 0.0
                    a_new = max(a * 1.05, rn * 0.95)
                    if J2 is None or abs(a_new - a_cur) > 1e-9:
                        a_cur = a_new
                        J2, Ji2 = current_density_maps(a_cur, el_rad, top_sheet, bot_sheet, n_z, r_c)
                rho = np.where(isCu, _RHO_CU[idx], _RHO_STEEL[idx] * rf2)
                q = rho * J2 * (I * I)
                for (typ, zi), Jz in zip(iface, Ji2):
                    Ti = 0.5 * (T[zi] + T[zi - 1])
                    rc0 = rc_fay0 if typ == 'fay' else rc_el0
                    Rc = rc0 * np.sqrt(F_ref / max(force_N, 1.0)) * np.exp(-(Ti / 650.0) ** 2)
                    qs = Rc * Jz * (I * I) / DX / 2.0
                    q[zi] += qs
                    q[zi - 1] += qs
                q *= heat_scale
            else:
                q = zeros0
            Tn = T + dt * (div + q) / C
            Tn[0, :] = T_AMB
            Tn[-1, :] = T_AMB
            Tn = np.where(active, Tn, T)
            T = Tn
            t += dt
            step += 1
            if step % rec_every == 0:
                sh = T[top_sheet:bot_sheet] >= T_LIQ
                if sh.any():
                    cols = sh.any(axis=0).nonzero()[0]
                    jj = int(cols.max())
                    zz = top_sheet + int(sh[:, jj].nonzero()[0][0])
                    Tj = T[zz, jj]
                    Tn_ = T[zz, jj + 1] if jj + 1 < n_r else Tj - 1.0
                    frac = min(1.0, max(0.0, (Tj - T_LIQ) / max(Tj - Tn_, 1e-9)))
                    dia = 2 * (jj + 0.5 + frac) * DX * 1e3
                    pen = sh[:, 0].sum() * DX / ((bot_sheet - top_sheet) * DX) * 100.0
                else:
                    dia, pen = 0.0, 0.0
                P = float((q * vol_fac * 2 * np.pi * DX).sum()) / max(heat_scale, 1e-9) if I > 0 else 0.0
                rec['t'].append(t); rec['dia'].append(dia); rec['pen'].append(pen)
                rec['tmax'].append(float(T[top_sheet:bot_sheet].max()))
                rec['rdyn'].append(P / (I * I) * 1e6 if I > 0 else 0.0)
                rec['I'].append(I)
            if stop_dia > 0 and I > 0 and step % rec_every == 0 and rec['dia'] and rec['dia'][-1] >= stop_dia:
                stopped, stop_t = True, t
            if step % snap_every == 0 or stopped:
                snaps.append(T.astype(np.float32).copy()); snap_t.append(t)
            if stopped:
                break
        if stopped:
            break
    snaps.append(T.astype(np.float32).copy()); snap_t.append(t)
    if len(snaps) > 120:                                   # keep the animation light: at most 120 frames
        keep = np.unique(np.linspace(0, len(snaps) - 1, 120).round().astype(int))
        snaps = [snaps[i] for i in keep]; snap_t = [snap_t[i] for i in keep]
    for kk in rec: rec[kk] = np.array(rec[kk])
    sheet_haz = (T[top_sheet:bot_sheet] >= T_HAZ)
    haz_r = (sheet_haz.any(axis=0).nonzero()[0].max() + 1) * DX * 1e3 if sheet_haz.any() else 0.0
    return dict(rec=rec, snaps=np.array(snaps), snap_t=np.array(snap_t), n_el=n_el, top=top_sheet,
                bot=bot_sheet, n_z=n_z, n_r=n_r, active=active, haz_r=haz_r,
                iface=[z for _, z in iface], stopped=stopped, stop_t=(stop_t if stop_t is not None else t), final_dia=float(rec['dia'].max() if len(rec['dia']) else 0),
                max_pen=float(rec['pen'].max() if len(rec['pen']) else 0), peak=float(rec['tmax'].max()))


def current_density_maps(a_cur, el_rad, top, bot, n_z, r_c):
    """Squared current density (for 1 A total) per cell, and per sheet-interface row."""
    n_r = len(r_c)
    J2 = np.zeros((n_z, n_r))
    shape_s = np.exp(-(np.maximum(r_c - a_cur, 0.0) / (0.12 * a_cur)) ** 2)
    for z in range(n_z):
        if z < top or z >= bot:
            ar = el_rad[z]
            sh = np.exp(-(np.maximum(r_c - ar, 0.0) / (0.12 * ar)) ** 2) * (r_c <= ar * 1.6)
        else:
            sh = shape_s
        norm = (sh * 2 * np.pi * r_c * DX).sum()
        J2[z] = (sh / norm) ** 2
    Jn2 = (shape_s / (shape_s * 2 * np.pi * r_c * DX).sum()) ** 2
    return J2, [Jn2] * 8

# ======================================================================================
# MATERIAL DATABASE (unchanged)
# ======================================================================================
materials_db = {
    "Mild Steel (JSC270)": {"res_factor": 1.0, "k_mod": 1.0, "ce": 0.08, "uts": 270},
    "High Strength (JSC440)": {"res_factor": 1.15, "k_mod": 1.05, "ce": 0.14, "uts": 440},
    "DP600 (Dual Phase)": {"res_factor": 1.35, "k_mod": 1.12, "ce": 0.18, "uts": 600},
    "DP980 (Ultra High Strength)": {"res_factor": 1.50, "k_mod": 1.20, "ce": 0.24, "uts": 980},
    "Boron Steel (Usibor 1500)": {"res_factor": 1.65, "k_mod": 1.25, "ce": 0.35, "uts": 1500},
    "Trip Steel (TRIP780)": {"res_factor": 1.40, "k_mod": 1.15, "ce": 0.22, "uts": 780},
}

# ======================================================================================
# SIDEBAR INPUTS
# ======================================================================================
with st.sidebar:
    st.caption("Weld_Lobe v3.4")
    transformer = st.radio("⚡ Transformer type", ["AC transformer", "MFDC transformer"],
                           help="Factory equations differ between AC and MFDC transformers (efficiency constant 0.241 for AC, 0.37 for MFDC). Applies to the Factory model and to every material.")
    mfdc = transformer.startswith("MFDC")
    basis = st.radio("Calculation basis", ["Factory Excel model (mild steel, 2-ply, Ø4 mm tip)", "Generic model (any material, 2–3 ply)"],
                     help="Factory model = the equations tuned from factory experiments (mild steel, 2 panels, Ø4 mm tip). Generic model = the earlier formula for other materials.")
    factory = basis.startswith("Factory")

    st.header("1. Sheet stack")
    if factory:
        npan = st.radio("Number of panels", ["2 panels", "3 panels"], horizontal=True, key="f_np",
                        help="3 panels: the equations and the WCCT chart use the MEDIUM thickness as t1 and the SUM of the other two sheets as t2 (factory rule).")
        st.caption("The factory equations are tuned on mild steel; other grades are scaled from it (see Model notes). AHSS = DP600 / TRIP780 • UHSS = DP980 • HPF = Boron (Usibor 1500).")
        mat1 = st.selectbox("Ply 1 Material (Top)", list(materials_db.keys()), key="f_m1")
        mat2 = st.selectbox("Ply 2 Material (" + ("Middle" if npan.startswith("3") else "Bottom") + ")", list(materials_db.keys()), key="f_m2")
        t1 = st.slider("Thickness 1 (mm)", 0.5, 3.0, 0.65, step=0.05)
        t2 = st.slider("Thickness 2 (mm)", 0.5, 3.0, 0.65, step=0.05)
        if npan.startswith("3"):
            mat3_selection = st.selectbox("Ply 3 Material (Bottom)", list(materials_db.keys()), key="f_m3")
            t3 = st.slider("Thickness 3 (mm)", 0.5, 3.0, 0.65, step=0.05)
            use_ply3 = True
        else:
            mat3_selection, use_ply3, t3 = "None (Revert to 2-Ply)", False, 0.0
    else:
        mat1 = st.selectbox("Ply 1 Material (Top)", list(materials_db.keys()))
        t1 = st.slider("Thickness 1 (mm)", 0.5, 3.0, 1.0, step=0.1)
        mat2 = st.selectbox("Ply 2 Material (Middle)", list(materials_db.keys()), index=2)
        t2 = st.slider("Thickness 2 (mm)", 0.5, 3.0, 1.2, step=0.1)
        mat3_selection = st.selectbox("Ply 3 Material (Bottom)", ["None (Revert to 2-Ply)"] + list(materials_db.keys()), index=0)
        use_ply3 = mat3_selection != "None (Revert to 2-Ply)"
        t3 = st.slider("Thickness 3 (mm)", 0.5, 3.0, 0.8, step=0.1) if use_ply3 else 0.0

    st.header("2. Electrodes")
    is_zinc = st.checkbox("Zinc Coated (GA/GI)?", help="Factory rule: increase welding current by 20 % for zinc-coated sheet.")
    if factory:
        d_tip, k_base = 4.0, 0.35
        st.caption("Electrode tip Ø 4.0 mm (fixed by the factory equations).")
    else:
        d_tip = st.slider("Tip Diameter (mm)", 4.0, 10.0, 6.0, step=0.5)
        k_base = st.slider("Base k-factor (lobe model)", 0.10, 0.60, 0.35)

# --------------------------------------------------------------------------------------
# stack properties
# --------------------------------------------------------------------------------------
layers_p = [materials_db[mat1], materials_db[mat2]] + ([materials_db[mat3_selection]] if use_ply3 else [])
layers_t = [t1, t2] + ([t3] if use_ply3 else [])
total_t = sum(layers_t)
t_min = min(layers_t)
if factory and use_ply3:
    t_min = sorted(layers_t)[1]          # factory rule for 3 panels: medium thickness plays the role of t1
if len(layers_t) == 3:
    _ts = sorted(layers_t); w_t1, w_t2 = _ts[1], _ts[0] + _ts[2]      # WCCT input: medium thickness, sum of the others
else:
    w_t1, w_t2 = t1, t2
with st.sidebar:
    if len(layers_t) == 3:
        st.info(f"WCCT input (3 panels): t1 = medium = {w_t1:.2f} mm, t2 = sum of the other two = {w_t2:.2f} mm" +
                ("  \nThe factory equations use the same rule (t_min = medium sheet)." if factory else ""))
k_mod_weighted = sum(t * p["k_mod"] for t, p in zip(layers_t, layers_p)) / total_t
res_weighted = sum(t * p["res_factor"] for t, p in zip(layers_t, layers_p)) / total_t
uts_weighted = sum(t * p["uts"] for t, p in zip(layers_t, layers_p)) / total_t
ce_weighted = sum(t * p["ce"] for t, p in zip(layers_t, layers_p)) / total_t

# --------------------------------------------------------------------------------------
# FACTORY EQUATIONS (Excel "WCCT Initial Condition Approximation", mild steel, 2 panels, Ø4 mm tip)
#   recommended force  F  = ((0.3428 t² + 1.327 t + 0.5865) * 1000) / 9.81         [kg]   t = t_min (mm)
#   recommended time   c  = 10 * t_min                                              [cycles]
#   recommended current I = f * sqrt( 9.7*3.14*(d²/4)*t_total / (0.24*(1e-4*c*0.02)) ) / 1000   [kA]
#                           f = 1.2 if t_min >= 1 else 1.16 ; d = general-spot nugget
#   nugget diameter    d = sqrt( 4*1.2*I²*0.241e-4*(0.02*cycles) / ((F/F_rec)*9.7*t_total*3.14) )
# --------------------------------------------------------------------------------------
F_REC_MILD = ((0.3428 * t_min ** 2 + 1.327 * t_min + 0.5865) * 1000.0) / 9.81
C_REC = 10.0 * t_min
m_heat, f_force = 1.0, 1.0
with st.sidebar:
    if factory:
        with st.expander("Material correction (non-mild steel)"):
            m_heat = st.number_input("Heat factor m  (nugget Ø ∝ √m)", value=round(res_weighted * k_mod_weighted, 3), step=0.01,
                                     help="Default = weighted resistivity factor × weighted k-modifier from the material table. Mild steel = 1.0.")
            f_force = st.number_input("Force factor", value=round(float(np.sqrt(uts_weighted / 270.0)), 3), step=0.01,
                                      help="Recommended force = mild-steel force × this factor. Default = √(UTS / 270 MPa). Assumption — tune with your own trials.")
            st.caption("Mild steel = 1.0 / 1.0. These two numbers are assumptions for grades the factory equations were not tuned on.")
F_REC = F_REC_MILD * f_force
with st.sidebar:
    with st.expander("Nugget size criteria (× √t_min)"):
        k_gen = st.number_input("General spot  (Ø = k·√t)", value=4.1, step=0.1, help="0.65 + 0.65 mm gives 3.3 mm, as in the factory sheet.")
        k_imp = st.number_input("Important spot  (Ø = k·√t)", value=5.0, step=0.1, help="0.65 + 0.65 mm gives 4.0 mm, as in the factory sheet.")
        k_hi = st.number_input("Upper edge of 'important' band (k·√t)", value=6.0, step=0.1)
        k_exp = st.number_input("Expulsion limit (k·√t)", value=9.0, step=0.1)
        st.caption("These factors were inferred from your Excel lobe table (colour boundaries). Edit them to match your factory standard.")
GEN_D, IMP_D, HI_D, EXP_D = k_gen * np.sqrt(t_min), k_imp * np.sqrt(t_min), k_hi * np.sqrt(t_min), k_exp * np.sqrt(t_min)
K_NUG, K_REC = (0.37, 0.37) if mfdc else (0.241, 0.24)      # transformer constants (AC / MFDC)
I_REC_KA = (1.2 if t_min >= 1 else 1.16) * np.sqrt((9.7 * 3.14 * (GEN_D ** 2 / 4.0) * total_t) / (K_REC * (0.0001 * C_REC * 0.02))) / 1000.0 / np.sqrt(m_heat)
if is_zinc:
    I_REC_KA *= 1.2
I_REC = I_REC_KA * 1000.0

if factory:
    I_MIN, I_MAX = int(round(0.5 * I_REC / 100) * 100), int(round(1.8 * I_REC / 100) * 100)
    T_MIN, T_MAX = 3, max(24, int(np.ceil(2.5 * C_REC)))
    F_MIN, F_MAX = int(round(0.5 * F_REC / 10) * 10), int(round(2.0 * F_REC / 10) * 10)
    I_DEF, T_DEF, F_DEF = int(min(max(round(I_REC / 100) * 100, I_MIN), I_MAX)), int(min(max(round(C_REC), T_MIN), T_MAX)), int(min(max(round(F_REC), F_MIN), F_MAX))
    I_STEP, F_STEP = 100, 1
else:
    I_MIN, I_MAX, T_MIN, T_MAX, F_MIN, F_MAX = 5000, 13000, 3, 24, 100, 450
    I_DEF, T_DEF, F_DEF, I_STEP, F_STEP = 9500, 16, 250, 100, 10

tab_lobe, tab_sim, tab_report, tab_wcct, tab_notes = st.tabs(["🧊 3D Lobe + Slice Plane", "🔥 2D Process Simulation", "📊 Strength & Metallurgy", "📈 WCCT Chart", "ℹ️ Model notes"])

# operating point + schedule live at the top of the 2D process-simulation tab
with tab_sim:
    with st.container(border=True):
        st.markdown("##### ⚙️ Operating point & weld schedule" + (f"   —   {transformer}" if factory else ""))
        oc1, oc2, oc3 = st.columns(3)
        active_current = oc1.slider("Weld current (A)", I_MIN, I_MAX, I_DEF, step=I_STEP)
        active_time = oc2.slider("Weld time (cycles)", T_MIN, T_MAX, T_DEF, step=1)
        active_force = oc3.slider("Electrode force (kg)", F_MIN, F_MAX, F_DEF, step=F_STEP)
        oq1, oq2, oq3, oq4 = st.columns(4)
        if factory:
            quality = oq1.radio("Required nugget level", ["General spot", "Important spot"], horizontal=True)
        freq = oq2.radio("Mains frequency (Hz)", [50, 60], horizontal=True)
        n_pulses = oq3.slider("Number of pulses", 1, 3, 1)
        hold_cyc = oq4.slider("Hold time (cycles)", 0, 10, 4)
        cool_cyc = st.slider("Cool time between pulses (cycles)", 0, 10, 4) if n_pulses > 1 else 0
        with st.expander("Advanced thermal model"):
            heat_scale = st.slider("Heat-input factor", 0.3, 1.5, 0.75, step=0.05, help="Scales all Joule heating in the 2D model.")
            contact_scale = st.slider("Contact resistance factor", 0.2, 3.0, 1.0, step=0.1)
            calibrate = st.checkbox("Calibrate 2D model to the lobe equation at the operating point", value=factory,
                                    help="Adjusts the heat-input factor automatically so the 2D nugget equals the lobe-equation nugget at this operating point.")

# --------------------------------------------------------------------------------------
# nugget / expulsion functions used by every tab
# --------------------------------------------------------------------------------------
k_approx = k_base * k_mod_weighted * res_weighted * (0.82 if is_zinc else 1.0)
tip_eff = (6.0 / d_tip) ** 2
if factory:
    target_min = GEN_D if quality == "General spot" else IMP_D
else:
    target_min = 4.0 * np.sqrt(t_min)
    GEN_D = IMP_D = target_min
    HI_D = 1e9

def nugget(I, T, F):
    if factory:
        I_eff = np.asarray(I, dtype=float) / (1.2 if is_zinc else 1.0)   # zinc sheet needs +20 % current for the same nugget
        return np.sqrt((4 * 1.2 * m_heat * I_eff ** 2 * K_NUG * 0.0001 * (0.02 * np.asarray(T, dtype=float))) /
                       ((np.asarray(F, dtype=float) / F_REC) * 9.7 * total_t * 3.14))
    return k_approx * ((I * tip_eff) / 10000.0) ** 2 * (T / 10.0) * (300.0 / F) ** 0.25 * 5.5

def expulsion(F):
    if factory:
        return EXP_D + 0.0 * np.asarray(F, dtype=float)
    return (5.5 * np.sqrt(t_min)) * (F / 300.0) ** 0.1 * (d_tip / 6.0) ** 0.2

currents = np.linspace(I_MIN, I_MAX, 50)
times = np.linspace(T_MIN, T_MAX, 40)
forces = np.linspace(F_MIN, F_MAX, 40)


ZONE_COLORS = ["#cfd8dc", "#9ccc65", "#42a5f5", "#f48fb1", "#ff6d00"] if factory else ["#cfd8dc", "#66bb6a", "#ff6d00"]
N_ZONE = len(ZONE_COLORS)
ZONE_SCALE = []
for _i, _c in enumerate(ZONE_COLORS):
    ZONE_SCALE += [[_i / N_ZONE, _c], [(_i + 1) / N_ZONE, _c]]

def zone_index(D, EX):
    """Zone number of every nugget value. Factory: 0 below general, 1 general, 2 important, 3 large, 4 expulsion.
    Generic: 0 too small, 1 acceptable, 2 expulsion."""
    D = np.asarray(D, dtype=float); EX = EX + 0.0 * D
    if factory:
        return np.select([D > EX, D >= HI_D, D >= IMP_D, D >= GEN_D], [4, 3, 2, 1], 0)
    return np.select([D > EX, D >= target_min], [2, 1], 0)

# ======================================================================================
# TAB 1 : 3D LOBE WITH ADJUSTABLE PLANE  ->  LIVE 2D LOBE
# ======================================================================================
with tab_lobe:
    try:
        if factory:
            d_target = float(nugget(I_REC, C_REC, F_REC))
            st.markdown(f"#### Recommended setting (factory equations — {transformer})")
            r1, r2, r3, r4, r5 = st.columns(5)
            r1.metric("Weld force", f"{F_REC:.0f} kg")
            r2.metric("Weld time", f"{C_REC:.1f} cycles")
            r3.metric("Weld current", f"{I_REC_KA:.2f} kA", "+20 % zinc" if is_zinc else None, delta_color="off")
            r4.metric("Target nugget", f"{d_target:.2f} mm")
            r5.metric("General / Important", f"{GEN_D:.1f} / {IMP_D:.1f} mm")

    except Exception as _e:
        _show_error('Recommended-setting panel', _e)

    c_ctrl, _ = st.columns([2, 1])
    with c_ctrl:
        plane = st.radio("Slice plane (fixed variable)", ["Force (kg)", "Time (cycles)", "Current (A)"], horizontal=True,
                         help="The plane is drawn inside the 3D lobe. The 2D weld lobe on the right is exactly the cut along this plane.")
        if plane == "Force (kg)":
            pos = st.slider("Plane position: Force (kg)", F_MIN, F_MAX, int(active_force), step=F_STEP)
        elif plane == "Time (cycles)":
            pos = st.slider("Plane position: Time (cycles)", T_MIN, T_MAX, int(active_time), step=1)
        else:
            pos = st.slider("Plane position: Current (A)", I_MIN, I_MAX, int(active_current), step=I_STEP)

    try:
        # --- 3D volumetric lobe: the whole acceptable volume (target_min <= nugget <= expulsion) is filled with colour
        ci = np.linspace(I_MIN, I_MAX, 40); ti = np.linspace(T_MIN, T_MAX, 30); fi = np.linspace(F_MIN, F_MAX, 30)
        I3, T3, F3 = np.meshgrid(ci, ti, fi, indexing="ij")
        D3 = nugget(I3, T3, F3); EX3 = expulsion(F3) + 0.0 * D3
        # continuous fields only (no masking) so every surface is interpolated smoothly
        if factory:
            c_lo, c_hi = float(target_min), float(EXP_D)
            val3 = D3
            vol_scale, edges = [], [e for e in [GEN_D, IMP_D, HI_D, EXP_D] if e > target_min + 1e-9]
            pts = [c_lo] + [e for e in edges if e < c_hi] + [c_hi]
            for lo_, hi_ in zip(pts[:-1], pts[1:]):
                col = ZONE_COLORS[int(zone_index((lo_ + hi_) / 2.0, EXP_D + 1.0))]
                vol_scale += [[(lo_ - c_lo) / (c_hi - c_lo), col], [(hi_ - c_lo) / (c_hi - c_lo), col]]
            cbar_title = "Nugget Ø (mm)"
        else:
            c_lo, c_hi = 0.0, 1.0
            val3 = (D3 - target_min) / np.maximum(EX3 - target_min, 1e-9)      # 0 = minimum nugget, 1 = expulsion
            vol_scale = [[0, "#2e7d32"], [0.5, "#9ccc65"], [1, "#f9a825"]]
            cbar_title = "Position in weld window"
        NOCAP = dict(x=dict(show=False), y=dict(show=False), z=dict(show=False))
        fig3 = go.Figure()
        fig3.add_trace(go.Isosurface(x=I3.flatten(), y=T3.flatten(), z=F3.flatten(), value=val3.flatten(),
                                     isomin=c_lo + 0.01 * (c_hi - c_lo), isomax=c_hi - 0.01 * (c_hi - c_lo), surface_count=40,
                                     cmin=c_lo, cmax=c_hi, colorscale=vol_scale, opacity=0.14, caps=NOCAP,
                                     colorbar=dict(title=cbar_title, len=0.6), name="Acceptable weld lobe"))
        # smooth limit borders (single continuous iso-surface each)
        fig3.add_trace(go.Isosurface(x=I3.flatten(), y=T3.flatten(), z=F3.flatten(), value=(D3 - target_min).flatten(), isomin=0, isomax=0, surface_count=1,
                                     colorscale=[[0, "#0d47a1"], [1, "#0d47a1"]], opacity=0.55, showscale=False, caps=NOCAP,
                                     name="Minimum nugget limit", showlegend=True))
        fig3.add_trace(go.Isosurface(x=I3.flatten(), y=T3.flatten(), z=F3.flatten(), value=(D3 - EX3).flatten(), isomin=0, isomax=0, surface_count=1,
                                     colorscale=[[0, "#b71c1c"], [1, "#b71c1c"]], opacity=0.55, showscale=False, caps=NOCAP,
                                     name="Expulsion limit", showlegend=True))
        # the adjustable plane
        if plane == "Force (kg)":
            gx, gy = np.meshgrid([I_MIN, I_MAX], [T_MIN, T_MAX]); gz = np.full_like(gx, pos, dtype=float)
        elif plane == "Time (cycles)":
            gx, gz = np.meshgrid([I_MIN, I_MAX], [F_MIN, F_MAX]); gy = np.full_like(gx, pos, dtype=float)
        else:
            gy, gz = np.meshgrid([T_MIN, T_MAX], [F_MIN, F_MAX]); gx = np.full_like(gy, pos, dtype=float)
        fig3.add_trace(go.Surface(x=gx, y=gy, z=gz, showscale=False, opacity=0.28, colorscale=[[0, "#263238"], [1, "#263238"]], name="Slice plane", showlegend=True))
        fig3.add_trace(go.Scatter3d(x=[active_current], y=[active_time], z=[active_force], mode="markers",
                                    marker=dict(size=7, color="black", symbol="diamond"), name="Operating point"))
        AX = dict(backgroundcolor="#eceff1", gridcolor="#90a4ae", showbackground=True, zerolinecolor="#546e7a", linecolor="#37474f", tickfont=dict(color="#263238"))
        fig3.update_layout(scene=dict(xaxis=dict(title="Current (A)", range=[I_MIN, I_MAX], **AX), yaxis=dict(title="Time (cycles)", range=[T_MIN, T_MAX], **AX),
                                      zaxis=dict(title="Force (kg)", range=[F_MIN, F_MAX], **AX)),
                           margin=dict(l=0, r=0, b=0, t=30), height=620, template="plotly_white", paper_bgcolor="white",
                           legend=dict(orientation="h", y=1.04), title="3D weld lobe (coloured volume = acceptable nugget, coloured by nugget size)")

    except Exception as _e:
        _show_error('3D lobe figure', _e)

    try:
        # --- 2D weld lobe cut along the plane (fine grid -> smooth zone edges) + matching Excel-style table
        NG = 180
        NC = 70
        if plane == "Force (kg)":
            xs, ys = np.linspace(I_MIN, I_MAX, NG), np.linspace(T_MIN, T_MAX, NG)
            fD = lambda X, Y: nugget(X, Y, pos); fE = lambda X, Y: expulsion(0.0 * X + pos)
            xlab, ylab = "Current (A)", "Weld time (cycles)"; op = (active_current, active_time)
            ttl = f"2D weld lobe at Force = {pos} kg"
            tx = np.linspace(I_MIN, I_MAX, 15); ty = np.arange(T_MAX, T_MIN - 1, -1, dtype=float)
            xfmt, yfmt = (lambda v: f"{v / 1000:.1f} kA"), (lambda v: f"{int(v)} cyc")
        elif plane == "Time (cycles)":
            xs, ys = np.linspace(I_MIN, I_MAX, NG), np.linspace(F_MIN, F_MAX, NG)
            fD = lambda X, Y: nugget(X, pos, Y); fE = lambda X, Y: expulsion(Y)
            xlab, ylab = "Current (A)", "Force (kg)"; op = (active_current, active_force)
            ttl = f"2D weld lobe at Time = {pos} cycles"
            tx = np.linspace(I_MIN, I_MAX, 15); ty = np.unique(np.round(np.linspace(F_MIN, F_MAX, 16)))[::-1]
            xfmt, yfmt = (lambda v: f"{v / 1000:.1f} kA"), (lambda v: f"{int(v)} kg")
        else:
            xs, ys = np.linspace(T_MIN, T_MAX, NG), np.linspace(F_MIN, F_MAX, NG)
            fD = lambda X, Y: nugget(pos, X, Y); fE = lambda X, Y: expulsion(Y)
            xlab, ylab = "Weld time (cycles)", "Force (kg)"; op = (active_time, active_force)
            ttl = f"2D weld lobe at Current = {pos} A"
            tx = np.unique(np.round(np.linspace(T_MIN, T_MAX, 16))); ty = np.unique(np.round(np.linspace(F_MIN, F_MAX, 16)))[::-1]
            xfmt, yfmt = (lambda v: f"{int(v)} cyc"), (lambda v: f"{int(v)} kg")
        X, Y = np.meshgrid(xs, ys); D = fD(X, Y); EX = fE(X, Y) + 0.0 * D
        xc, yc = np.linspace(xs[0], xs[-1], NC), np.linspace(ys[0], ys[-1], NC)
        Xc, Yc = np.meshgrid(xc, yc); Dc = fD(Xc, Yc); EXc = fE(Xc, Yc) + 0.0 * Dc
        fig2 = go.Figure()
        fig2.add_trace(go.Heatmap(x=xs, y=ys, z=zone_index(D, EX), zmin=0, zmax=N_ZONE - 0.001, showscale=False, hoverinfo="skip", colorscale=ZONE_SCALE))
        fig2.add_trace(go.Contour(x=xc, y=yc, z=Dc, showscale=False, contours_coloring="none", contours=dict(showlabels=True, labelfont=dict(size=10, color="#263238")),
                                  line=dict(color="rgba(38,50,56,0.55)", width=1), name="Nugget Ø (mm)", hovertemplate="Ø %{z:.2f} mm<extra></extra>"))
        fig2.add_trace(go.Contour(x=xc, y=yc, z=Dc, showscale=False, contours_coloring="none", contours=dict(start=target_min, end=target_min, size=1),
                                  line=dict(color="#0d47a1", width=4), name="Minimum nugget", showlegend=True))
        fig2.add_trace(go.Contour(x=xc, y=yc, z=Dc - EXc, showscale=False, contours_coloring="none", contours=dict(start=0, end=0, size=1),
                                  line=dict(color="#b71c1c", width=4, dash="dash"), name="Expulsion limit", showlegend=True))
        fig2.add_trace(go.Scatter(x=[op[0]], y=[op[1]], mode="markers", marker=dict(color="black", size=14, symbol="cross", line=dict(color="white", width=1)), name="Operating point"))
        fig2.update_layout(title=ttl, xaxis_title=xlab, yaxis_title=ylab, template="plotly_white", height=620,
                           margin=dict(l=40, r=20, b=40, t=50), legend=dict(orientation="h", y=-0.15))

    except Exception as _e:
        _show_error('2D lobe figure', _e)

    col3d, col2d = st.columns([1.15, 1])
    with col3d:
        st.plotly_chart(fig3, use_container_width=True)
    with col2d:
        st.plotly_chart(fig2, use_container_width=True)
    if factory:
        st.markdown("<span style='background:#cfd8dc;padding:2px 8px'>below general</span> "
                    "<span style='background:#9ccc65;padding:2px 8px'>General spot</span> "
                    "<span style='background:#42a5f5;padding:2px 8px'>Important spot</span> "
                    "<span style='background:#f48fb1;padding:2px 8px'>large nugget</span> "
                    "<span style='background:#ff6d00;padding:2px 8px;color:white'>expulsion</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='background:#cfd8dc;padding:2px 8px'>too small</span> "
                    "<span style='background:#66bb6a;padding:2px 8px'>acceptable</span> "
                    "<span style='background:#ff6d00;padding:2px 8px;color:white'>expulsion</span>", unsafe_allow_html=True)
    d_op = float(nugget(active_current, active_time, active_force))
    in_window = target_min <= d_op <= float(expulsion(active_force))
    st.caption(f"Operating point nugget Ø {d_op:.2f} mm. " + ("✅ Inside the weld window." if in_window else "⚠️ Outside the weld window.") +
               "  Rotate the 3D lobe with the mouse; the dark plane is the cut shown at right.")

    # ---- Excel-style table = the same cross-section as the 2D lobe
    st.markdown(f"#### Lobe table — {ttl.replace('2D weld lobe at ', '')}  (nugget Ø in mm)")
    try:
        TX, TY = np.meshgrid(tx, ty)
        Dt = fD(TX, TY); Et = fE(TX, TY) + 0.0 * Dt
        df = pd.DataFrame(Dt, index=[yfmt(v) for v in ty], columns=[xfmt(v) for v in tx])
        Zt = zone_index(Dt, Et)
        def _paint(_):
            return pd.DataFrame([[f"background-color:{ZONE_COLORS[int(z)]};color:{'white' if int(z) == N_ZONE - 1 else '#212121'}" for z in row] for row in Zt], index=df.index, columns=df.columns)
        st.dataframe(df.style.apply(_paint, axis=None).format("{:.1f}"), use_container_width=True, height=min(740, 38 + 35 * len(ty)))

    except Exception as _e:
        _show_error('Lobe table', _e)

    # ---- nugget growth with weld time
    try:
        cyc = np.linspace(0.2, max(12.0, T_MAX / 2.0), 60)
        figG = go.Figure()
        figG.add_trace(go.Scatter(x=cyc, y=nugget(active_current, cyc, active_force), mode="lines", line=dict(color="#0d47a1", width=3), name="Nugget Ø"))
        for val, nm, col in [(GEN_D, "General", "#7cb342"), (IMP_D, "Important", "#1e88e5"), (float(expulsion(active_force)), "Expulsion", "#d84315")]:
            figG.add_hline(y=val, line=dict(color=col, dash="dash"), annotation_text=nm)
        figG.update_layout(title=f"Nugget growth at {active_current} A, {active_force} kg", xaxis_title="Weld time (cycles)", yaxis_title="Ø (mm)",
                           template="plotly_white", height=320, margin=dict(l=40, r=20, b=40, t=50))
        st.plotly_chart(figG, use_container_width=True)

    except Exception as _e:
        _show_error('Nugget growth chart', _e)

# ======================================================================================
# TAB 2 : 2D AXISYMMETRIC PROCESS SIMULATION
# ======================================================================================
@st.cache_data(show_spinner=False, max_entries=24)
def run_sim(layers, zinc, d_tip, force, current, wcyc, pulses, ccyc, hcyc, freq, hs, cs, stop_dia=0.0):
    return simulate_weld(layers, zinc, d_tip, force, current, wcyc, pulses, ccyc, hcyc, freq, hs, cs, stop_dia)

sim_layers = tuple((t, p["res_factor"]) for t, p in zip(layers_t, layers_p))
base_args = (sim_layers, bool(is_zinc), float(d_tip), float(active_force), float(active_current), int(active_time),
             int(n_pulses), int(cool_cyc), int(hold_cyc), float(freq))

with tab_sim:
    rc1, rc2, rc3 = st.columns([1, 2, 2])
    run_it = rc1.toggle("▶ Run simulation", value=True, key="run2d_v2", help="Solves the 2D thermal model for the settings above (cached, so repeated runs are instant).")
    frame_ms = rc3.slider("Animation delay per frame (ms)  — larger = slower motion", 20, 1500, 300, step=10,
                          help="Slow-motion control for ▶ Play. Each frame is 1 ms of weld time.")
    stop_at_target = rc2.checkbox("Stop the simulation when the target nugget diameter is reached", value=True,
                                 help="The weld current is cut as soon as the molten nugget reaches the required minimum diameter (sidebar: General / Important spot).")
    dia = 0.0
    if not run_it:
        st.info("Switch on **▶ Run simulation** to solve nugget growth for the current settings (sidebar). Results are cached, so moving the lobe plane is not slowed down.")
    else:
        hs_used = heat_scale
        with st.spinner("Solving transient heat-conduction / Joule-heating model..."):
            if calibrate:
                goal = float(nugget(active_current, active_time, active_force))
                lo, hi = 0.2, 2.5
                for _ in range(7):
                    mid = 0.5 * (lo + hi)
                    d_mid = run_sim(*base_args, round(mid, 4), float(contact_scale), 0.0)["final_dia"]
                    if d_mid < goal: lo = mid
                    else: hi = mid
                hs_used = round(0.5 * (lo + hi), 4)
            res = run_sim(*base_args, float(hs_used), float(contact_scale), float(target_min) if stop_at_target else 0.0)

        rec = res["rec"]; dia = res["final_dia"]; E = float(expulsion(active_force))
        pen = res["max_pen"]
        if res["stopped"]:
            verdict = f"✅ Target nugget Ø {target_min:.2f} mm reached at {res['stop_t'] * 1000:.0f} ms ({res['stop_t'] * freq:.1f} cycles) — simulation stopped"
        elif dia < 0.5:
            verdict = "❌ No nugget formed (cold weld)"
        elif dia < target_min:
            verdict = "❌ Undersized nugget (below minimum)"
        elif dia > E or res["peak"] > 2300 or pen > 90:
            verdict = "🔥 Expulsion / overheating risk"
        else:
            verdict = "✅ Good weld (inside weld window)"
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Nugget diameter (2D sim)", f"{dia:.2f} mm", f"lobe model: {nugget(active_current, active_time, active_force):.2f} mm", delta_color="off")
        m2.metric("Required minimum", f"{target_min:.2f} mm")
        m3.metric("Penetration", f"{pen:.0f} %")
        m4.metric("Peak temperature", f"{res['peak']:.0f} °C")
        m5.metric("HAZ radius (727 °C)", f"{res['haz_r']:.1f} mm")
        st.info(f"**2D simulation result:** {verdict}" + (f"   •   heat-input factor auto-calibrated to {hs_used:.2f}" if calibrate else ""))

        # ---- animated cross-section (SORPAS-style: electrodes + sheets, rainbow temperature scale, molten nugget in purple)
        top, bot, n_el, n_z, n_r = res["top"], res["bot"], res["n_el"], res["n_z"], res["n_r"]
        DXmm = 0.2
        act = res["active"]
        xs_half = (np.arange(n_r) + 0.5) * DXmm
        xs = np.concatenate([-xs_half[::-1], xs_half])
        ys = (np.arange(n_z) - top) * DXmm + DXmm / 2
        JET = [[0.00, "#0000ff"], [0.14, "#0080ff"], [0.28, "#00ffff"], [0.42, "#00ff40"], [0.56, "#ffff00"],
               [0.70, "#ff8000"], [0.85, "#ff1500"], [0.915, "#d0007a"], [1.00, "#800080"]]
        TMIN, TMAX = 20.0, 1500.0
        tick_v = np.linspace(TMIN, TMAX, 8)
        cbar = dict(title="Temperature (°C)", tickvals=list(tick_v), ticktext=[f"{v:.3E}" for v in tick_v], thickness=18, len=0.95)

        def field(Tm):
            return np.round(np.concatenate([Tm[:, ::-1], Tm], axis=1))

        snaps = res["snaps"]; times_s = res["snap_t"]
        def tlabel(i):
            return f"Temperature field   t = {times_s[i] * 1000:.0f} ms  ({times_s[i] * freq:.1f} cycles)" + ("   — target nugget reached, stopped" if (res["stopped"] and i == len(snaps) - 1) else "")
        frames = [go.Frame(name=str(i), traces=[0], data=[go.Heatmap(x=xs, y=ys, z=field(snaps[i]), zmin=TMIN, zmax=TMAX, colorscale=JET, zsmooth="best", colorbar=cbar)],
                           layout=go.Layout(title_text=tlabel(i))) for i in range(len(snaps))]
        figA = go.Figure(data=[go.Heatmap(x=xs, y=ys, z=field(snaps[-1]), zmin=TMIN, zmax=TMAX, colorscale=JET, zsmooth="best", colorbar=cbar,
                                          hovertemplate="r %{x:.1f} mm, z %{y:.1f} mm: %{z:.0f} °C<extra></extra>")], frames=frames)
        shapes = []
        for zi in [z for z in res["iface"] if top < z < bot]:
            yy = (zi - top) * DXmm
            shapes.append(dict(type="line", x0=xs[0], x1=xs[-1], y0=yy, y1=yy, line=dict(color="rgba(255,255,255,0.9)", width=1)))
        # smooth electrode silhouette: white polygons hide everything outside the analytic cap profile, plus a thin outline
        a_mm = d_tip / 2.0
        hh = np.linspace(0.0, EL_H * 1e3, 70)
        rr = a_mm + (EL_R * 1e3 - a_mm) * (1.0 - np.exp(-hh / 2.0))
        y_bot_sheet = (bot - top) * DXmm
        XL = float(xs[0]); XR = float(xs[-1])
        for sgn, y_face, ydir in ((1, 0.0, -1.0), (2, y_bot_sheet, 1.0)):
            yy_ = y_face + ydir * hh
            y_far = float(yy_[-1])
            for side in (-1.0, 1.0):
                outer_x = XL if side < 0 else XR
                pts = [(outer_x, y_face), (outer_x, y_far)] + [(side * float(rr[i]), float(yy_[i])) for i in range(len(hh) - 1, -1, -1)]
                path = "M " + " L ".join(f"{px:.3f},{py:.3f}" for px, py in pts) + " Z"
                shapes.append(dict(type="path", path=path, fillcolor="white", line=dict(width=0), layer="above"))
                line_path = "M " + " L ".join(f"{side * float(rr[i]):.3f},{float(yy_[i]):.3f}" for i in range(len(hh)))
                shapes.append(dict(type="path", path=line_path, line=dict(color="#455a64", width=1.5), layer="above"))
        _k = max(1, len(snaps) // 8)
        steps = [dict(method="animate", label=(f"{times_s[i]*1000:.0f}" if (i % _k == 0 or i == len(snaps) - 1) else ""), args=[[str(i)], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))]) for i in range(len(snaps))]
        figA.update_layout(
            title=tlabel(len(snaps) - 1), template="plotly_white", plot_bgcolor="white", paper_bgcolor="white", height=560, margin=dict(l=40, r=20, b=60, t=60),
            xaxis=dict(title="Radius (mm)", scaleanchor="y", scaleratio=1, showgrid=False, zeroline=False, range=[xs[0], xs[-1]]),
            yaxis=dict(title="Depth (mm)", autorange="reversed", showgrid=False, zeroline=False), shapes=shapes,
            updatemenus=[dict(type="buttons", direction="left", x=0.0, y=-0.1, buttons=[
                dict(label="▶ Play", method="animate", args=[None, dict(frame=dict(duration=int(frame_ms), redraw=True), fromcurrent=True, transition=dict(duration=0))]),
                dict(label="⏸ Pause", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])])],
            sliders=[dict(active=len(snaps) - 1, x=0.15, len=0.85, y=-0.03, currentvalue=dict(prefix="Time (ms): "), steps=steps)])

        # ---- curves
        tms = rec["t"] * 1000
        figC = go.Figure()
        figC.add_trace(go.Scatter(x=tms, y=rec["dia"], name="Nugget dia (mm)", line=dict(color="#ffb300", width=3)))
        figC.add_hline(y=target_min, line=dict(color="#0d47a1", dash="dash"), annotation_text="min target")
        figC.add_hline(y=E, line=dict(color="#b71c1c", dash="dash"), annotation_text="expulsion limit")
        figC.update_layout(title="Nugget growth", xaxis_title="Time (ms)", yaxis_title="Diameter (mm)", template="plotly_white", height=330, margin=dict(l=40, r=20, b=40, t=50))
        figR = go.Figure()
        mask = rec["I"] > 0
        figR.add_trace(go.Scatter(x=tms[mask], y=rec["rdyn"][mask], name="Dynamic resistance", line=dict(color="#69f0ae", width=3), mode="lines"))
        figR.update_layout(title="Dynamic resistance (µΩ)", xaxis_title="Time (ms)", yaxis_title="R (µΩ)", template="plotly_white", height=330, margin=dict(l=40, r=20, b=40, t=50))
        figT = go.Figure()
        figT.add_trace(go.Scatter(x=tms, y=rec["tmax"], name="Peak temperature in sheets", line=dict(color="#ff7043", width=3)))
        figT.add_hline(y=1500, line=dict(color="#37474f", dash="dot"), annotation_text="melting")
        figT.update_layout(title="Peak temperature (°C)", xaxis_title="Time (ms)", yaxis_title="°C", template="plotly_white", height=330, margin=dict(l=40, r=20, b=40, t=50))

        st.plotly_chart(figA, use_container_width=True)
        ca, cb, cc = st.columns(3)
        ca.plotly_chart(figC, use_container_width=True)
        cb.plotly_chart(figR, use_container_width=True)
        cc.plotly_chart(figT, use_container_width=True)
        st.caption("Press ▶ Play (or drag the time slider) to watch the nugget grow (purple = molten, above 1500 °C). The animation runs in your browser, so playback does not re-run the server. "
                   "Dynamic resistance falls as contact resistance collapses and the sheets heat — the typical shape seen in SORPAS and in real weld monitors.")

# ======================================================================================
# TAB 3 : STRENGTH & METALLURGY
# ======================================================================================
with tab_report:
    src = st.radio("Nugget size used for strength estimate", ["Lobe model", "2D simulation"], horizontal=True)
    if src == "2D simulation" and not run_it:
        st.warning("Switch on ▶ Run simulation (tab 2) first. Using the lobe model for now.")
        src = "Lobe model"
    d_use = float(nugget(active_current, active_time, active_force)) if src == "Lobe model" else float(dia)
    expulsion_calc = float(expulsion(active_force))
    predicted_tss = (np.pi * d_use ** 2 / 4.0) * uts_weighted / 1000.0
    predicted_cts = predicted_tss * (0.24 + 0.36 * (1.0 - ce_weighted))
    ductility_ratio = predicted_cts / predicted_tss if predicted_tss > 0 else 0
    peak_fz_hardness = 120 + 720 * ce_weighted
    min_haz_hardness = peak_fz_hardness * (0.84 if ce_weighted > 0.18 else 0.96)
    if d_use < target_min:
        mode = "❌ Interfacial Shear Failure (Brittle Weld)"
    elif (uts_weighted > 780) and (ce_weighted > 0.20):
        mode = "⚠️ Partial Plug / HAZ Necking Failure (Borderline High Strength)"
    else:
        mode = "✅ Full Button Pullout Failure (Ductile Base Material Overload)"
    st.subheader("📊 Geometric, Mechanical & Metallurgical Performance")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Nugget size used", f"{d_use:.2f} mm")
    a2.metric("Target min bound", f"{target_min:.2f} mm")
    a3.metric("Expulsion threshold", f"{expulsion_calc:.2f} mm")
    a4.metric("Tensile shear (TSS)", f"{predicted_tss:.2f} kN")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Cross-tension (CTS)", f"{predicted_cts:.2f} kN")
    b2.metric("Ductility ratio (CTS/TSS)", f"{ductility_ratio:.3f}")
    b3.metric("Peak fusion hardness", f"{peak_fz_hardness:.1f} HV")
    b4.metric("Minimum HAZ hardness", f"{min_haz_hardness:.1f} HV")
    st.info(f"**Predicted failure mechanism:** {mode}")

# ======================================================================================
# TAB 4 : WCCT CHART  (weld current - weld time chart, calibrated on the Mitsubishi A/B/C table)
# ======================================================================================
# Mitsubishi welding-parameter table, mild steel, AC transformer, 2 equal sheets (transcribed from the factory Excel "Reference 1").
# columns per class: weld time (cycles, 50 Hz), force (kg), current (kA), strength (kg)
_MIT_T = np.array([0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.4, 2.8, 3.2, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
_MIT_TIP = np.array([3.2, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.3, 6.7, 7.0, 7.8, 8.5, 9.0, 10.0, 10.6, 11.3, 12.4, 13.4, 14.3, 15.2, 16.0])
_MIT = {
    "A": np.array([[4, 115, 5.2, 180], [5, 135, 6.0, 240], [6, 150, 6.6, 300], [7, 190, 7.8, 440], [8, 225, 8.8, 610], [10, 270, 9.8, 780], [12, 305, 10.6, 930],
                   [13, 360, 11.5, 1060], [15, 410, 12.5, 1300], [17, 470, 13.3, 1450], [20, 580, 15.0, 1850], [23, 700, 16.2, 2380], [27, 820, 17.4, 3100],
                   [33, 1100, 19.0, 4200], [38, 1200, 21.2, 4500], [42, 1400, 22.5, 5800], [50, 1750, 25.0, 7600], [58, 2200, 27.5, 9500], [67, 2500, 30.0, 11400],
                   [75, 2900, 32.0, 13500], [83, 3200, 34.0, 16000]], float),
    "B": np.array([[8, 75, 4.5, 160], [9, 90, 5.0, 210], [11, 100, 5.5, 280], [13, 125, 6.5, 400], [17, 150, 7.2, 540], [19, 175, 7.7, 680], [22, 210, 8.5, 850],
                   [25, 240, 9.1, 1000], [28, 275, 9.7, 1180], [30, 300, 10.3, 1370], [37, 370, 11.3, 1770], [43, 430, 12.1, 2300], [50, 500, 12.9, 2850],
                   [61, 630, 15.0, 3800], [64, 710, 15.7, 4300], [67, 800, 16.5, 5200], [92, 970, 18.0, 6800], [108, 1150, 19.5, 8500], [125, 1300, 21.0, 10400],
                   [138, 1500, 22.5, 12300], [150, 1700, 24.0, 14400]], float),
    "C": np.array([[17, 40, 3.5, 125], [20, 45, 4.0, 175], [22, 50, 4.3, 225], [25, 60, 5.0, 355], [30, 75, 5.6, 530], [33, 85, 6.1, 650], [38, 100, 6.6, 780],
                   [43, 115, 7.0, 925], [48, 130, 7.5, 1100], [53, 150, 8.0, 1305], [64, 180, 8.6, 1685], [79, 220, 9.4, 2175], [88, 260, 10.0, 2665],
                   [108, 340, 11.0, 3500], [117, 390, 11.8, 4000], [142, 440, 12.5, 4800], [175, 540, 14.0, 6300], [208, 650, 15.0, 7800], [233, 750, 16.0, 9500],
                   [267, 880, 17.0, 11200], [283, 1000, 18.0, 13100]], float)}
_MIT_NAME = {"A": "A class (best)", "B": "B class (medium)", "C": "C class (ordinary)"}


def mit_lookup(cls, tm):
    """cycles, force kg, current kA of the Mitsubishi table for thickness tm (linear interpolation)."""
    M = _MIT[cls]
    return tuple(float(np.interp(tm, _MIT_T, M[:, j])) for j in range(3))


with tab_wcct:
    try:
        # ---- calibration factors for the current stack (mild steel, AC, 2 panels = 1.0) ----
        if factory:
            w_m, w_f = m_heat, f_force
        else:
            w_m, w_f = float(res_weighted * k_mod_weighted), float(np.sqrt(uts_weighted / 270.0))
        tf = float(np.sqrt(0.24 / K_REC))            # transformer: AC = 1.0, MFDC from the factory constants
        zf = 1.2 if is_zinc else 1.0
        tm_w, tt_w = min(w_t1, w_t2), w_t1 + w_t2

        st.markdown(f"#### WCCT chart — {transformer}, {'3' if len(layers_t) == 3 else '2'} panels" + ("" if factory else "  (generic model: same chart, scaled for your materials)"))
        st.caption("Weld current vs weld time for each sheet thickness. **Yellow** = minimum (general-spot) nugget, **blue** = important-spot nugget, **red** = largest nugget before expulsion (shaded region = acceptable range), "
                   "**green dashed** = the nugget Ø you pick. **Cross arrows** (as in the original Mitsubishi chart) show the applicable current/time range through each thickness point at its force. Optional markers show the **Mitsubishi A / B / C class** table (mild steel, AC, 2 panels) scaled to your stack. "
                   "For 3 panels the sidebar input sets t1 = medium thickness and t2 = sum of the other two.")
        cA, cB = st.columns([2, 1])
        gD, iD = k_gen * np.sqrt(tm_w), k_exp * np.sqrt(tm_w)
        impD = k_imp * np.sqrt(tm_w)
        if iD <= gD:
            iD = gD + 0.05
        with cA:
            d_sel = st.slider("Acceptable nugget Ø (mm), from minimum (general) up to the expulsion limit",
                              float(round(gD, 2)), float(round(iD, 2)), float(round((gD + impD) / 2.0, 2)), step=0.05)
            show_cls = st.multiselect("Mitsubishi classes to overlay", ["A", "B", "C"], default=["A"], format_func=lambda c: _MIT_NAME[c],
                                      help="A = best condition (short time, high current), C = ordinary condition (long time, low current). Class B/C need many more cycles, so the time axis grows.")
            span = st.slider("Cross-arrow maximum length (± % of weld time)", 10, 100, 100, step=5,
                             help="Double-headed arrows follow the constant-nugget line (current² × time = constant) and stop at the edge of the shaded region (yellow / blue lines). Reduce to shorten them.") / 100.0
        k_sel = d_sel / np.sqrt(tm_w)
        with cB:
            st.markdown(f"**Combination:** t1 = {w_t1:.2f} mm, t2 = {w_t2:.2f} mm (total {tt_w:.2f} mm)")
            st.markdown(f"**Calibration:** heat factor {w_m:.2f}, force factor {w_f:.2f}" + (", zinc +20 % current" if is_zinc else "") + (f", MFDC ×{tf:.2f} current" if mfdc else ""))

        def wcct_eq(tm, tt, k):
            """factory-equation point: current kA, time cycles, force kgf, nugget mm"""
            d = k * np.sqrt(tm)
            cyc_ = 10.0 * tm
            F_ = ((0.3428 * tm ** 2 + 1.327 * tm + 0.5865) * 1000.0 / 9.81) * w_f
            I_ = (1.2 if tm >= 1 else 1.16) * np.sqrt((9.7 * 3.14 * (d ** 2 / 4.0) * tt) / (K_REC * (0.0001 * cyc_ * 0.02))) / 1000.0 / np.sqrt(w_m)
            return I_ * zf, cyc_, F_ * 1.0, d

        def mit_point(cls, tm, tt):
            cyc_, F_, I_ = mit_lookup(cls, tm)
            return I_ * np.sqrt(tt / (2.0 * tm)) * tf * zf / np.sqrt(w_m), cyc_, F_ * w_f

        th = np.round(np.arange(0.6, 2.01, 0.1), 2)
        lines = {key: np.array([wcct_eq(t_, 2 * t_, kk) for t_ in th]) for key, kk in (("gen", k_gen), ("sel", k_sel), ("imp", k_imp), ("exp", k_exp))}
        my = {key: wcct_eq(tm_w, tt_w, kk) for key, kk in (("gen", k_gen), ("sel", k_sel), ("imp", k_imp), ("exp", k_exp))}
        cols = {"A": "#c62828", "B": "#6a1b9a", "C": "#546e7a"}
        mit_lines = {}
        for c in show_cls:
            tt_ = _MIT_T[(_MIT_T >= 0.6) & (_MIT_T <= 2.4)]
            mit_lines[c] = np.array([mit_point(c, t_, 2 * t_) for t_ in tt_]); mit_lines[c] = (tt_, mit_lines[c])
        mit_my = {c: mit_point(c, tm_w, tt_w) for c in ("A", "B", "C")}
        lab = [0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
        idx0 = [int(np.where(th == v)[0][0]) for v in lab if v in th]

        _gc, _gi = lines["gen"][:, 1], lines["gen"][:, 0]
        _ic, _ii = lines["exp"][:, 1], lines["exp"][:, 0]

        def _inside(I_, c_):
            return (_gc.min() <= c_ <= _gc.max()) and (np.interp(c_, _gc, _gi) - 1e-6 <= I_ <= np.interp(c_, _ic, _ii) + 1e-6)

        def arrow_ends(I_, c_):
            """double arrow along the constant-nugget line (I²·c = const), clipped to the shaded region between the yellow and blue lines"""
            f_hi, f_lo = 1.0 + span, max(1.0 - span, 0.3)
            if _inside(I_, c_):
                for f in np.linspace(1.0, 1.0 + span, 241):
                    if not _inside(I_ / np.sqrt(f), c_ * f):
                        f_hi = max(1.0, f - (span / 240.0)); break
                for f in np.linspace(1.0, max(1.0 - span, 0.3), 241):
                    if not _inside(I_ / np.sqrt(f), c_ * f):
                        f_lo = min(1.0, f + (span / 240.0)); break
            return (I_ / np.sqrt(f_hi), c_ * f_hi), (I_ / np.sqrt(f_lo), c_ * f_lo)      # upper-left end, lower-right end
        arrows = [(lines["sel"][i, 0], lines["sel"][i, 1], lines["sel"][i, 2], "#2e7d32") for i in idx0] + [(my["sel"][0], my["sel"][1], my["sel"][2], "#000000")]
        ends = [arrow_ends(a[0], a[1]) for a in arrows]
        xs = [lines["gen"][:, 0], lines["exp"][:, 0], [my["sel"][0]]] + [v[1][:, 0] for v in mit_lines.values()] + [[mit_my[c][0]] for c in show_cls] + [[e[0][0], e[1][0]] for e in ends]
        ys = [lines["exp"][:, 1], [my["sel"][1]]] + [v[1][:, 1] for v in mit_lines.values()] + [[mit_my[c][1]] for c in show_cls] + [[e[0][1], e[1][1]] for e in ends]
        x0, x1 = float(np.floor(min(np.min(a) for a in xs) - 0.6)), float(np.ceil(max(np.max(a) for a in xs) + 0.6))
        y1 = float(np.ceil(max(np.max(a) for a in ys) + 2)); y0 = 0.0

        ann_list = []
        for (I_, c_, F_, col_), (ul, lr) in zip(arrows, ends):
            ann_list.append(dict(x=lr[0], y=lr[1], ax=ul[0], ay=ul[1], xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                                 arrowhead=2, startarrowhead=2, arrowsize=1.1, arrowwidth=1.6, arrowcolor=col_, text=""))
            ann_list.append(dict(x=ul[0], y=ul[1], xref="x", yref="y", showarrow=False, text=f"{F_:.0f} kgf", font=dict(size=10, color=col_),
                                 xanchor="right", yanchor="bottom"))
        figW = go.Figure()
        figW.add_trace(go.Scatter(x=lines["gen"][:, 0], y=lines["gen"][:, 1], mode="lines+markers", name="1) Minimum nugget (general spot)",
                                  line=dict(color="#f9a825", width=4), marker=dict(size=6, color="#f9a825")))
        figW.add_trace(go.Scatter(x=lines["exp"][:, 0], y=lines["exp"][:, 1], mode="lines+markers", name="3) Nugget just before expulsion",
                                  line=dict(color="#c62828", width=4), marker=dict(size=6, color="#c62828"), fill="tonexty", fillcolor="rgba(66,165,245,0.14)"))
        figW.add_trace(go.Scatter(x=lines["imp"][:, 0], y=lines["imp"][:, 1], mode="lines+markers", name="2) Important-spot nugget",
                                  line=dict(color="#1e40af", width=4), marker=dict(size=6, color="#1e40af")))
        figW.add_trace(go.Scatter(x=lines["sel"][:, 0], y=lines["sel"][:, 1], mode="lines", name=f"Selected nugget (Ø = {k_sel:.2f}·√t)",
                                  line=dict(color="#2e7d32", width=3, dash="dash")))
        lab = [0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
        idx = [int(np.where(th == v)[0][0]) for v in lab if v in th]
        figW.add_trace(go.Scatter(x=lines["sel"][idx, 0], y=lines["sel"][idx, 1], mode="markers+text", showlegend=False,
                                  marker=dict(size=9, color="#2e7d32", symbol="circle-open", line=dict(width=2)),
                                  text=[f"{th[i]:.1f} mm (Ø{lines['sel'][i, 3]:.1f})<br>{lines['sel'][i, 2]:.0f} kgf" for i in idx],
                                  textposition="top left", textfont=dict(size=11, color="#1b5e20")))
        for c, (tt_, P) in mit_lines.items():
            figW.add_trace(go.Scatter(x=P[:, 0], y=P[:, 1], mode="lines+markers", name=f"Mitsubishi {_MIT_NAME[c]}",
                                      line=dict(color=cols[c], width=2, dash="dot"), marker=dict(size=7, symbol="diamond", color=cols[c]),
                                      text=[f"{t_:.1f} mm, {f_:.0f} kgf" for t_, f_ in zip(tt_, P[:, 2])], hoverinfo="text+x+y"))
        if show_cls:
            figW.add_trace(go.Scatter(x=[mit_my[c][0] for c in show_cls], y=[mit_my[c][1] for c in show_cls], mode="markers+text", showlegend=False,
                                      marker=dict(size=12, symbol="diamond-open", color=[cols[c] for c in show_cls], line=dict(width=2)),
                                      text=[c for c in show_cls], textposition="bottom right"))
        figW.add_trace(go.Scatter(x=[my["sel"][0]], y=[my["sel"][1]], mode="markers", name="Your combination (selected Ø)",
                                  marker=dict(size=16, color="black", symbol="star")))
        shapes_w = [dict(type="line", x0=my["sel"][0], x1=my["sel"][0], y0=y0, y1=my["sel"][1], line=dict(color="#555", width=1, dash="dot")),
                    dict(type="line", x0=x0, x1=my["sel"][0], y0=my["sel"][1], y1=my["sel"][1], line=dict(color="#555", width=1, dash="dot"))]
        figW.update_layout(template="plotly_white", height=660, margin=dict(l=60, r=70, b=60, t=40), shapes=shapes_w,
                           xaxis=dict(title="Welding current (kA)", range=[x0, x1], dtick=1, gridcolor="#cfd8dc"),
                           yaxis=dict(title="Weld time (cycles, 50 Hz)", range=[y0, y1], dtick=2 if y1 < 40 else 5, gridcolor="#cfd8dc"),
                           annotations=ann_list, legend=dict(orientation="h", y=-0.16))
        st.plotly_chart(figW, use_container_width=True)
        st.caption("Right-hand 60 Hz scale: multiply the 50 Hz cycles by 1.2.")

        st.markdown("#### Setting for your sheet combination")
        g1, g2, g3, g4, g5 = st.columns(5)
        g1.metric("Selected nugget Ø", f"{d_sel:.2f} mm", f"range {gD:.2f} – {iD:.2f}", delta_color="off")
        g2.metric("Weld current", f"{my['sel'][0]:.2f} kA", f"min {my['gen'][0]:.2f} / imp. {my['imp'][0]:.2f} / expulsion {my['exp'][0]:.2f}", delta_color="off")
        g3.metric("Weld time (50 Hz)", f"{my['sel'][1]:.1f} cycles")
        g4.metric("Weld time (60 Hz)", f"{my['sel'][1] * 1.2:.1f} cycles")
        g5.metric("Electrode force", f"{my['sel'][2]:.0f} kgf")
        mt = pd.DataFrame([{"Condition": _MIT_NAME[c], "Current (kA)": round(mit_my[c][0], 2), "Time 50 Hz (cyc)": round(mit_my[c][1], 1),
                            "Time 60 Hz (cyc)": round(mit_my[c][1] * 1.2, 1), "Force (kgf)": round(mit_my[c][2], 0)} for c in ("A", "B", "C")])
        st.markdown("**Mitsubishi A / B / C conditions scaled to this stack**")
        st.dataframe(mt, use_container_width=True, hide_index=True)

        with st.expander("Reference tables (equal-thickness 2-ply stacks) and check against the Mitsubishi table"):
            tbl = pd.DataFrame({"Thickness each (mm)": th, "Force (kgf)": lines["sel"][:, 2].round(0), "Time 50 Hz (cyc)": lines["sel"][:, 1].round(1),
                                "I min Ø (kA)": lines["gen"][:, 0].round(2), "I selected (kA)": lines["sel"][:, 0].round(2), "I important (kA)": lines["imp"][:, 0].round(2), "I before expulsion (kA)": lines["exp"][:, 0].round(2),
                                "Ø min (mm)": lines["gen"][:, 3].round(1), "Ø selected (mm)": lines["sel"][:, 3].round(1), "Ø important (mm)": lines["imp"][:, 3].round(1), "Ø expulsion (mm)": lines["exp"][:, 3].round(1)})
            st.dataframe(tbl, use_container_width=True, hide_index=True)
            st.markdown("Mild steel, AC, no zinc: factory equation (general nugget) against the Mitsubishi A class")
            ch = []
            for t_ in _MIT_T[(_MIT_T >= 0.6) & (_MIT_T <= 3.2)]:
                d_ = k_gen * np.sqrt(t_); Ie = (1.2 if t_ >= 1 else 1.16) * np.sqrt((9.7 * 3.14 * d_ ** 2 / 4 * 2 * t_) / (0.24 * (0.0001 * 10 * t_ * 0.02))) / 1000
                cA_, FA_, IA_ = mit_lookup("A", t_); Fe_ = (0.3428 * t_ ** 2 + 1.327 * t_ + 0.5865) * 1000 / 9.81
                ch.append({"t (mm)": t_, "I equation (kA)": round(Ie, 2), "I Mitsubishi A (kA)": IA_, "Δ current %": round((Ie / IA_ - 1) * 100, 1),
                           "F equation (kgf)": round(Fe_), "F Mitsubishi A (kgf)": FA_, "time equation (cyc)": round(10 * t_, 1), "time Mitsubishi A (cyc)": cA_})
            st.dataframe(pd.DataFrame(ch), use_container_width=True, hide_index=True)
        st.caption("Calibration: the lines come from the factory equations, scaled for transformer type, material (heat and force factors from the sidebar, or from the material table in the Generic model), "
                   "zinc and total stack thickness (current ∝ √t_total). The Mitsubishi markers use the same scaling: current × √(t_total / 2·t) × material factor. "
                   "The material factors are assumptions to be tuned with your own trials. The Mitsubishi table was transcribed from the Excel screenshot — please verify the values.")
    except Exception as _e:
        _show_error("WCCT chart", _e)

# ======================================================================================
# TAB 4 : NOTES
# ======================================================================================
with tab_notes:
    st.markdown("""
**Factory equations (default basis).** Taken from the factory Excel sheet — mild steel, 2 panels, Ø4 mm tip:
- Recommended force: F = (0.3428·t² + 1.327·t + 0.5865)·1000 / 9.81 kg, with t = thinnest sheet (mm)
- Recommended weld time: 10 × t_min cycles
- Recommended current: I = f·√[ 9.7·3.14·(d²/4)·t_total / (0.24·(0.0001·cycles·0.02)) ] / 1000 kA, f = 1.2 if t_min ≥ 1 mm else 1.16, d = general-spot nugget
- Nugget diameter: d = √[ 4·1.2·I²·K·0.0001·(0.02·cycles) / ((F/F_rec)·9.7·t_total·3.14) ]
- Transformer constant K: 0.241 for an AC transformer, 0.37 for an MFDC transformer (K = 0.24 / 0.37 in the recommended-current equation; the MFDC value there is inferred from the nugget equation — please confirm). Applies to every material.
- Zinc-coated sheet: +20 % current (applied as I/1.2 inside the nugget equation).
- Nugget-size limits (general, important, upper important band, expulsion) are inferred from the colour boundaries of the Excel lobe table and are editable in the sidebar.

**3D lobe + slice plane.** The lobe is the volume in (current, time, force) space where the predicted nugget is at least the minimum target (4·√t_min) and below the expulsion limit. The yellow plane cuts this volume; the 2D weld lobe on the right is the same cut, shown with the green weld window, the cyan minimum-nugget line and the red dashed expulsion line.

**2D process simulation.** An axisymmetric (r–z) transient finite-difference model with: Joule heating in the sheets and copper electrodes, temperature-dependent resistivity, conductivity and heat capacity of steel, latent heat of fusion, contact resistance at electrode–sheet and sheet–sheet interfaces (falling with temperature and force), water-cooled electrode ends, multi-pulse schedules and hold time. The current path widens as the nugget grows.

**Limits (please read).** The model is a teaching tool. It does not solve the electrical potential field, mechanical contact/indentation, expulsion dynamics, phase transformation or coating behaviour, and the contact-resistance constants are generic. Use the *Heat-input factor* or the calibrate option to align it with your own lab data; use validated software (e.g. SORPAS) and weld trials for production decisions.
""")
