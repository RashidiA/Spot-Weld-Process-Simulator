# Asari-Rashidi Spot Welding Lobe & 2D Process Simulator 🔬

## Overview
An interactive engineering and teaching tool for resistance spot welding of automotive sheet steel. It combines:

1. a **3D weld lobe** (current × time × force) with an **adjustable slice plane** that shows the matching **2D weld lobe** and an Excel-style lobe table, and
2. a **SORPAS-style 2D process simulation** (axisymmetric thermal model) that animates nugget growth and stops when the target nugget diameter is reached.

The lobe is based on **factory equations tuned from real experiments** (mild steel, 2 panels, Ø4 mm electrode tip). Other steel grades (AHSS, UHSS, HPF) are scaled from that mild-steel basis. A *Generic model* (the earlier Asari-Rashidi formula) is still available for 2–3 ply stacks and other tip sizes.

> **Learning tool.** Results are indicative. The 2D model is a simplified physics model, not a replacement for validated FEA such as SORPAS or for weld trials.

**Simulator link:** https://spot-weld-process-simulator-jogq55brt4wsqfy8sgonbp.streamlit.app/

---

## 🚀 Features

### 1. 3D weld lobe with adjustable slice plane (tab 1)
* The acceptable window (minimum nugget ≤ Ø ≤ expulsion limit) is drawn as a **colour-filled 3D volume**, coloured by nugget size, with smooth blue (minimum nugget) and red (expulsion) limit surfaces.
* Choose the plane to fix: **Force**, **Time** or **Current**, then slide its position. The plane moves inside the 3D lobe.
* The **2D weld lobe** beside it is exactly the cut along that plane, with smooth zone colours, nugget contour lines, limit lines and the operating-point marker.
* An **Excel-style lobe table** follows the same cross-section as the 2D lobe, using the factory colour code:
  grey = below general spot, green = general spot, blue = important spot, pink = large nugget, orange = expulsion.
* **Recommended setting** (force, time, current, target nugget) is shown as values from the factory equations.
* A nugget-growth chart shows Ø against weld time at the operating point.

### 2. 2D process simulation (tab 2)
* **Operating point and weld schedule** are set at the top of this tab: current, time, force, required nugget level (General or Important spot), mains frequency (50/60 Hz), number of pulses, cool time and hold time.
* Axisymmetric transient thermal model with Joule heating in sheets and electrodes, temperature-dependent steel properties, latent heat of fusion, contact resistance (electrode–sheet and sheet–sheet), water-cooled electrodes, and a current path that widens as the nugget grows.
* **SORPAS-style picture:** electrodes with smooth curved caps and the sheets between them, rainbow temperature scale, molten nugget (above 1500 °C) in purple.
* **Stop at target:** the weld current is cut as soon as the molten nugget reaches the required diameter, and the result reports the time and cycles taken.
* **Animation with slow-motion control:** ▶ Play / ⏸ Pause, a time slider and an "animation delay per frame" slider (each frame = 1 ms of weld time). The animation plays in your browser without re-running the server.
* Charts: nugget growth, dynamic resistance, peak temperature; metrics for penetration and HAZ radius.
* Optional **calibration** of the 2D model to the lobe equation at the operating point.

### 3. Multi-Stack-Up Weld Lobe Prediction Model – MSWLPM (tab 4)
Weld-current / weld-time chart that works in **both** the Factory and the Generic model. Three limit lines: yellow = minimum (general-spot) nugget, blue = important-spot nugget, red = largest nugget before expulsion (k_exp·√t, editable); green dashed = the **acceptable nugget Ø you select** between the two, with force and time for each sheet thickness (50 Hz; ×1.2 for 60 Hz).
* **Mitsubishi A / B / C class overlay:** the Mitsubishi welding-parameter table (mild steel, AC, 2 equal sheets) is built in. A = best, B = medium, C = ordinary condition. It is scaled to your stack: current × √(t_total / 2t), material heat/force factors, zinc +20 %, MFDC factor.
* **Cross arrows:** like the original Mitsubishi chart, a double-headed arrow through each thickness point (and your combination) shows the applicable current/time range at that force, following the constant-nugget line; the span is adjustable.
* **2 or 3 panels (sidebar):** choose the number of panels. For 3 panels the app sets t1 = medium thickness and t2 = sum of the other two sheets, and the factory equations use the same rule.
* **Other materials (AHSS, UHSS, HPF):** scaled with the material factors (editable in the Factory model; taken from the material table in the Generic model).
* Check: for mild steel AC the equation (general nugget) is within about 4 % of the Mitsubishi A-class current up to 1.6 mm and 7–10 % lower at 2.0–2.4 mm. Material factors and the MFDC factor are assumptions; the table was transcribed from a screenshot, so verify the values.

### 4. Strength & metallurgy (tab 3)
Tensile-shear and cross-tension estimates, ductility ratio, fusion-zone and HAZ hardness, and a predicted failure mode, using either the lobe-model nugget or the 2D-simulation nugget.

### 4. Materials
Mild Steel (JSC270), High Strength (JSC440), DP600 and TRIP780 (AHSS), DP980 (UHSS) and Boron Steel Usibor 1500 (HPF). Each ply of the stack can use a different grade. Zinc-coated sheet is supported.

---

## 📐 Equations

### Factory model (default): mild steel, 2 panels, Ø4 mm tip
With `t_min` the thinnest sheet (mm), `t_total` the stack thickness (mm), `I` the current (A), `c` the weld time (cycles) and `F` the electrode force (kg):

| Quantity | Equation |
|---|---|
| Recommended force | `F_rec = (0.3428·t_min² + 1.327·t_min + 0.5865) · 1000 / 9.81` kg |
| Recommended weld time | `c_rec = 10 · t_min` cycles |
| Recommended current | `I_rec = f · √[ 9.7·3.14·(d²/4)·t_total / (K_rec·(0.0001·c_rec·0.02)) ] / 1000` kA, `f = 1.2` if `t_min ≥ 1 mm` else `1.16`, `d` = general-spot nugget |
| Nugget diameter | `d = √[ 4·1.2·I²·K·0.0001·(0.02·c) / ((F/F_rec)·9.7·t_total·3.14) ]` |

* **Transformer type (first selection in the sidebar):** the factory equations differ between transformers. `K = 0.241` for an **AC transformer** and `K = 0.37` for an **MFDC transformer** in the nugget equation. In the recommended-current equation `K_rec = 0.24` (AC) and `0.37` (MFDC); the MFDC value there is inferred from the nugget equation and should be confirmed. The selection applies to every material grade.
* **Zinc-coated sheet:** current increased by 20 % (applied as `I/1.2` in the nugget equation).
* **Nugget limits** (inferred from the colour boundaries of the factory lobe table and editable in the sidebar): general spot 4.1·√t_min, important spot 5.0·√t_min, upper edge of the "important" band 6.0·√t_min, expulsion 9.0·√t_min.
* **AHSS / UHSS / HPF:** scaled from the mild-steel basis with two assumed factors, editable under *Material correction*:
  heat factor `m` = weighted resistivity factor × weighted k-modifier (nugget Ø ∝ √m), and force factor = √(UTS/270 MPa). These are assumptions to be tuned with your own trials.

### Generic model (other materials, 2–3 ply, other tip sizes)
$$D_{nugget} = k_{approx} \cdot \left(\frac{I \cdot \eta_{tip}}{10000}\right)^2 \cdot \left(\frac{T}{10}\right) \cdot \left(\frac{300}{F}\right)^{0.25} \cdot 5.5, \qquad \eta_{tip} = (6.0/d_{tip})^2$$

$$D_{expulsion} = (5.5\sqrt{t_{min}})\left(\frac{F}{300}\right)^{0.1}\left(\frac{d_{tip}}{6.0}\right)^{0.2}, \qquad D_{min} = 4\sqrt{t_{min}}$$

`k_approx` is the thickness-weighted, resistivity-corrected efficiency of the stack (×0.82 for zinc-coated sheet).

---

## ⚠️ Model limits
* The 2D thermal model does not solve the electrical potential field, mechanical contact or indentation, expulsion dynamics, phase transformation or coating behaviour. Contact-resistance constants are generic.
* The 2D model grows the nugget faster early in the weld than the factory equation. Calibration matches the final nugget only; use the heat-input factor to tune it to your own data.
* Dynamic resistance, power and energy blocks of the factory Excel sheet are not reproduced; the dynamic-resistance curve shown comes from the 2D model.
* Material scaling for AHSS / UHSS / HPF is an assumption (see above), because the factory equations were tuned on mild steel only.

---

## 🛠️ Installation & Local Setup

Python 3.8+ is required.

```bash
git clone https://github.com/RashidiA/Industrial-Robot-Cloud-Simulator.git   # replace with this app's repository
cd <your-repository-folder>
pip install streamlit numpy pandas plotly
streamlit run Weld_Lobe.py
```

For Streamlit Community Cloud, list `streamlit`, `numpy`, `pandas` and `plotly` in `requirements.txt`.

---

## 📚 Part of the Automotive Knowledge Hub
This simulator is one of the learning tools in the Automotive Knowledge Hub. Collaborators are welcome: developers, welding and process engineers, educators and students.

## 🤝 License
Distributed under open-source project standards for automotive manufacturing simulation, design verification and teaching applications.
