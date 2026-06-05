# Asari-Rashidi Multi-Ply Automotive Spot Welding Simulator 🔬

## Overview
This interactive engineering platform offers real-time visualization and multi-axis parametric mapping of the process operating window (Weld Lobe) for automotive sheet steel assemblies. Driven by the proprietary **Asari-Rashidi Nugget Growth Model**, the simulator predicts thermodynamic and physical bonding thresholds across multi-ply material stacks.

The simulator bridges the gap between raw experimental values and finite element method (FEM) software (such as SORPAS) by instantly solving thickness-weighted resistivity scaling, thermal sink profiles, and expulsion limits.

---

## 🚀 Key Evolutionary Features

### 1. Advanced 3D Volumetric Weld Lobe
* Maps the complete multi-variable process window across **Current ($I$)**, **Weld Time ($T$)**, and **Electrode Force ($F$)** simultaneously.
* Renders real-time interactive volumetric isosurfaces using WebGL via Plotly, automatically masking out sub-critical combinations based on industrial requirements ($4\sqrt{t_{min}}$).

### 2. Dual-Orientation 2D Cross-Section Slicing
* **X-Y Plane (Current vs. Time):** Evaluates traditional weld lobe maps at any discrete, slider-adjusted electrode force.
* **X-Z Plane (Current vs. Force):** Maps critical force-dependent contact-resistance paths at a selected hold time, tracking performance across varying clamping conditions.

### 3. Synchronized Transient Thermal Animation Map
* Uses a side-by-side graphical layout pairing your Plotly contour map directly with an embedded canvas rendering engine.
* Animates cycle-by-cycle transient developmental progress showing:
  * **Electrode Thermal Sinks:** Dynamic gradient fields cooling down the outer stack boundaries.
  * **Heat Affected Zone (HAZ):** Real-time expansion of solid-state structural modification rings.
  * **Molten Weld Pool:** Visually tracks the liquid phase front, dynamically converting to a high-contrast danger profile if localized parameters bypass the mathematical expulsion threshold.

### 4. Dynamic Operating Point Interactivity
* Integrates an interactive "crosshair marker" directly onto the analytical planes. Adjusting process settings updates the exact localized coordinate marker position while simultaneously computing its frame timeline for the playback loop.

---

## 📐 Scientific & Engineering Principles

### Nugget Diameter Formulation
The base model computes nugget growth ($D_{nugget}$) as a function of thermal energy input scaled across structural and chemical characteristics:

$$D_{nugget} = k_{approx} \cdot \left(\frac{I \cdot \eta_{tip}}{10000}\right)^2 \cdot \left(\frac{T}{10}\right) \cdot \left(\frac{300}{F}\right)^{0.25} \cdot 5.5$$

Where:
* **$k_{approx}$**: The thickness-weighted, resistivity-corrected base efficiency factor of your specific material ply stack.
* **$\eta_{tip}$**: Current density geometric scaler derived from electrode tip wear/contact diameter: $\eta_{tip} = (6.0 / d_{tip})^2$.

### Dynamic Expulsion Threshold Bounds
Rather than assigning a static limit, the app computes a moving boundary line tracking localized pressure breakdowns and metal splashing conditions:

$$D_{expulsion} = (5.5 \cdot \sqrt{t_{min}}) \cdot \left(\frac{F}{300}\right)^{0.1} \cdot \left(\frac{d_{tip}}{6.0}\right)^{0.2}$$

In **Current vs. Force** cross-sections, the script actively resolves a structural difference matrix ($D_{nugget} - D_{expulsion} = 0$) to cleanly render the complex, curved red boundary path.

---

## 🌐 Modern Automotive Material Database
Includes advanced high-strength steel (AHSS) and ultra-high-strength steel (UHSS) grades, accounting for localized chemical tracking factors:
* **Mild Steel (JSC270)**
* **High Strength (JSC440)**
* **DP600 (Dual Phase)**
* **DP980 (Ultra High Strength)**
* **Boron Steel (Usibor 1500)**
* **Trip Steel (TRIP780)**

*Includes a toggle for surface coatings (Zinc Coated GA/GI) that automatically adjusts initial interfacial contact resistances by applying a $0.82\times$ scale adjustment.*

---

## 🛠️ Installation & Local Setup

Ensure you have Python 3.8+ installed, then complete the setup steps:

1. **Clone the repository:**
```bash
git clone [https://github.com/your-username/asari-rashidi-spot-weld.git](https://github.com/your-username/asari-rashidi-spot-weld.git)
cd asari-rashidi-spot-weld
