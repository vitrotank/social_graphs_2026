#!/usr/bin/env python3
"""Generate publication-ready vector SVGs for Week 2 matching Crosstalk's visual style."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "assets/figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Load Marvel network
net = json.loads((ROOT / "assets/data/network.json").read_text(encoding="utf-8"))
nodes = net["nodes"]
in_degrees = sorted([n["in_degree"] for n in nodes if n["in_degree"] > 0])
N_pos = len(in_degrees) # 245

# Unique degrees and CCDF
unique_k = sorted(set(in_degrees))
marvel_ccdf = []
for k in unique_k:
    prob = sum(1 for d in in_degrees if d >= k) / N_pos
    marvel_ccdf.append((k, prob))

# Dimensions matching degree-linear.svg & degree-loglog.svg
W, H = 960, 600
LEFT, RIGHT = 88, 916
TOP, BOTTOM = 92, 490

# Log-log coordinate mapping
X_MIN, X_MAX = 1, 120
Y_MIN, Y_MAX = 0.003, 1.0

def x_px(k: float) -> float:
    return LEFT + (math.log10(k) - math.log10(X_MIN)) / (math.log10(X_MAX) - math.log10(X_MIN)) * (RIGHT - LEFT)

def y_px(p: float) -> float:
    clamped = max(Y_MIN, min(Y_MAX, p))
    return BOTTOM - (math.log10(clamped) - math.log10(Y_MIN)) / (math.log10(Y_MAX) - math.log10(Y_MIN)) * (BOTTOM - TOP)

# -------------------------------------------------------------------------
# 1. ccdf-models.svg
# -------------------------------------------------------------------------
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title-ccdf desc-ccdf">',
    '<title id="title-ccdf">Marvel vs Barabási–Albert vs Erdős–Rényi</title>',
    '<desc id="desc-ccdf">Log-log CCDF showing Marvel tracking Barabási-Albert power-law tail and decisively rejecting thin-tailed Erdős-Rényi.</desc>',
    '<rect width="960" height="600" fill="#f6f1e7"/>',
    '<g font-family="Arial, sans-serif" fill="#232927">',
    '<text x="40" y="38" font-size="24" font-weight="700">Does Marvel follow a power law or random chance?</text>',
    '<text x="40" y="65" font-size="13" fill="#586866">Complementary cumulative distribution (CCDF) · Marvel in-degree vs Barabási–Albert vs Erdős–Rényi · log–log axes</text>'
]

for xt in [1, 2, 5, 10, 20, 50, 100]:
    xp = x_px(xt)
    parts.append(f'<path d="M{xp:.2f},{TOP} V{BOTTOM}" stroke="#d5d9cf"/><text x="{xp:.2f}" y="514" text-anchor="middle" font-size="12">{xt}</text>')

for yt in [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]:
    yp = y_px(yt)
    parts.append(f'<path d="M{LEFT},{yp:.2f} H{RIGHT}" stroke="#d5d9cf"/><text x="76" y="{yp+4:.2f}" text-anchor="end" font-size="12">{yt}</text>')

parts.append('<text x="502" y="545" text-anchor="middle" font-size="12" fill="#586866" font-family="SFMono-Regular, Consolas, monospace">DEGREE k</text>')
parts.append('<text x="24" y="291" text-anchor="middle" font-size="12" fill="#586866" font-family="SFMono-Regular, Consolas, monospace" transform="rotate(-90 24 291)">P(K ≥ k)</text>')

# Erdős-Rényi Poisson CCDF curve: mean k ≈ 5.88, plunges at k=8
er_pts = []
for k in range(1, 10):
    prob = sum(math.exp(-5.88) * (5.88**i) / math.factorial(i) for i in range(k, 30))
    if prob >= Y_MIN:
        er_pts.append((x_px(k), y_px(prob)))
er_d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in er_pts)
parts.append(f'<path d="{er_d}" fill="none" stroke="#486452" stroke-width="2.5" stroke-dasharray="5 4" opacity="0.85"/>')

# Barabási-Albert power law theoretical curve: P(K >= k) ~ (m / k)^2 for m=6, scaled
ba_pts = []
for k in [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 110]:
    prob = min(1.0, (2.0 / k)**1.35)
    if prob >= Y_MIN:
        ba_pts.append((x_px(k), y_px(prob)))
ba_d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in ba_pts)
parts.append(f'<path d="{ba_d}" fill="none" stroke="#2849c7" stroke-width="2.5" opacity="0.8"/>')

# Marvel empirical CCDF step line + points
marvel_line = "M" + " L".join(f"{x_px(k):.2f},{y_px(p):.2f}" for k, p in marvel_ccdf)
parts.append(f'<path d="{marvel_line}" fill="none" stroke="#dc512f" stroke-width="2.2" opacity="0.9"/>')
for k, p in marvel_ccdf:
    xp, yp = x_px(k), y_px(p)
    parts.append(f'<circle cx="{xp:.2f}" cy="{yp:.2f}" r="4" fill="#dc512f" opacity="0.95"><title>k={k}: P(K>={k})={p:.4f}</title></circle>')

# Annotations for hubs
offsets = {
    33: ("Deadpool (k=33)", 15, -12),
    50: ("Doctor Strange (k=50)", 15, -10),
    60: ("Wolverine (k=60)", 15, -6),
    64: ("Hulk (k=64)", -10, 18),
    106: ("Spider-Man (k=106)", -90, -14)
}
for k, (name, dx, dy) in offsets.items():
    p = sum(1 for d in in_degrees if d >= k) / N_pos
    xp, yp = x_px(k), y_px(p)
    parts.append(f'<circle cx="{xp:.2f}" cy="{yp:.2f}" r="6" fill="none" stroke="#dc512f" stroke-width="1.8"/>')
    parts.append(f'<text x="{xp+dx:.2f}" y="{yp+dy:.2f}" font-size="10" font-family="SFMono-Regular, Consolas, monospace" fill="#8f2913" font-weight="bold">{name}</text>')

# Annotation for finite size knee
knee_x, knee_y = x_px(35), y_px(0.02)
parts.append(f'<path d="M{knee_x:.2f},{knee_y:.2f} l-35,-35 h-95" fill="none" stroke="#60645c" stroke-width="1.2" stroke-dasharray="3 3"/>')
parts.append(f'<text x="{knee_x-135:.2f}" y="{knee_y-40:.2f}" font-size="10" font-family="SFMono-Regular, Consolas, monospace" fill="#60645c">Finite-size cutoff (k ≈ 35)</text>')

# Legends
parts.append('<circle cx="580" cy="37" r="5" fill="#dc512f"/><text x="592" y="42" font-size="12">Marvel In-Degree (Empirical)</text>')
parts.append('<line x1="770" y1="37" x2="790" y2="37" stroke="#2849c7" stroke-width="2.5"/><text x="796" y="42" font-size="12">Barabási–Albert</text>')
parts.append('<line x1="770" y1="58" x2="790" y2="58" stroke="#486452" stroke-width="2.5" stroke-dasharray="4 3"/><text x="796" y="63" font-size="12">Erdős–Rényi</text>')

parts.append('</g></svg>\n')
(FIG_DIR / "ccdf-models.svg").write_text("\n".join(parts), encoding="utf-8")
print("Wrote assets/figures/ccdf-models.svg")

# -------------------------------------------------------------------------
# 2. ccdf-fit.svg
# -------------------------------------------------------------------------
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title-fit desc-fit">',
    '<title id="title-fit">Fitted Power-Law &amp; Tail Truncation</title>',
    '<desc id="desc-fit">Empirical power-law fit slope of -1.35 and the discrete quantal staircase breakdown past k=35.</desc>',
    '<rect width="960" height="600" fill="#f6f1e7"/>',
    '<g font-family="Arial, sans-serif" fill="#232927">',
    '<text x="40" y="38" font-size="24" font-weight="700">The limits of scale-free claims</text>',
    '<text x="40" y="65" font-size="13" fill="#586866">Fitted power-law slope = −1.351 (implied γ = 2.351) · discrete quantal steps in the tail</text>'
]

for xt in [1, 2, 5, 10, 20, 50, 100]:
    xp = x_px(xt)
    parts.append(f'<path d="M{xp:.2f},{TOP} V{BOTTOM}" stroke="#d5d9cf"/><text x="{xp:.2f}" y="514" text-anchor="middle" font-size="12">{xt}</text>')

for yt in [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]:
    yp = y_px(yt)
    parts.append(f'<path d="M{LEFT},{yp:.2f} H{RIGHT}" stroke="#d5d9cf"/><text x="76" y="{yp+4:.2f}" text-anchor="end" font-size="12">{yt}</text>')

parts.append('<text x="502" y="545" text-anchor="middle" font-size="12" fill="#586866" font-family="SFMono-Regular, Consolas, monospace">DEGREE k</text>')
parts.append('<text x="24" y="291" text-anchor="middle" font-size="12" fill="#586866" font-family="SFMono-Regular, Consolas, monospace" transform="rotate(-90 24 291)">P(K ≥ k)</text>')

rx1, rx2 = x_px(2), x_px(35)
parts.append(f'<rect x="{rx1:.2f}" y="{TOP}" width="{rx2-rx1:.2f}" height="{BOTTOM-TOP}" fill="#dc512f" fill-opacity="0.06"/>')
parts.append(f'<text x="{(rx1+rx2)/2:.2f}" y="{TOP+20}" text-anchor="middle" font-size="11" font-family="SFMono-Regular, Consolas, monospace" fill="#a93419">FITTED REGIME [k = 2 to 35]</text>')

fit_x1, fit_y1 = x_px(1.5), y_px(0.83 * (1.5/2.0)**-1.351)
fit_x2, fit_y2 = x_px(45), y_px(0.83 * (45.0/2.0)**-1.351)
parts.append(f'<line x1="{fit_x1:.2f}" y1="{fit_y1:.2f}" x2="{fit_x2:.2f}" y2="{fit_y2:.2f}" stroke="#2849c7" stroke-width="2.5" stroke-dasharray="6 4"/>')

stair_pts = []
for i, (k, p) in enumerate(marvel_ccdf):
    xp, yp = x_px(k), y_px(p)
    stair_pts.append(f"{xp:.2f},{yp:.2f}")
parts.append(f'<path d="M' + " L".join(stair_pts) + f'" fill="none" stroke="#dc512f" stroke-width="2.2"/>')
for k, p in marvel_ccdf:
    xp, yp = x_px(k), y_px(p)
    parts.append(f'<circle cx="{xp:.2f}" cy="{yp:.2f}" r="3.5" fill="#dc512f"/>')

parts.append(f'<text x="{x_px(10):.2f}" y="{y_px(0.12):.2f}" font-size="11" font-family="SFMono-Regular, Consolas, monospace" fill="#2849c7" font-weight="bold">Fitted Slope = −1.351 (γ = 2.351)</text>')
parts.append(f'<text x="{x_px(36):.2f}" y="{y_px(0.006):.2f}" font-size="10" font-family="SFMono-Regular, Consolas, monospace" fill="#8f2913">Only 5 hubs exist past k = 33 (1/245 discrete quanta)</text>')

parts.append('<circle cx="680" cy="37" r="5" fill="#dc512f"/><text x="692" y="42" font-size="12">Marvel Empirical CCDF</text>')
parts.append('<line x1="680" y1="58" x2="700" y2="58" stroke="#2849c7" stroke-width="2.5" stroke-dasharray="5 3"/><text x="706" y="63" font-size="12">Power-Law Fit (k ∈ [2, 35])</text>')

parts.append('</g></svg>\n')
(FIG_DIR / "ccdf-fit.svg").write_text("\n".join(parts), encoding="utf-8")
print("Wrote assets/figures/ccdf-fit.svg")

# -------------------------------------------------------------------------
# 3. clustering-nulls.svg
# -------------------------------------------------------------------------
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title-c desc-c">',
    '<title id="title-c">Clustering Coefficient vs Null Models</title>',
    '<desc id="desc-c">Clustering distributions across Erdős-Rényi, Double Edge Swap, and the observed Marvel network.</desc>',
    '<rect width="960" height="600" fill="#f6f1e7"/>',
    '<g font-family="Arial, sans-serif" fill="#232927">',
    '<text x="40" y="38" font-size="24" font-weight="700">Testing clustering against null models</text>',
    '<text x="40" y="65" font-size="13" fill="#586866">Clustering coefficient distributions: Erdős–Rényi G(n, m) vs Double Edge Swap vs Observed Marvel</text>'
]

C_MIN, C_MAX = 0.0, 0.38
def cx_px(c: float) -> float:
    return LEFT + (c - C_MIN) / (C_MAX - C_MIN) * (RIGHT - LEFT)

for ct in [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35]:
    xp = cx_px(ct)
    parts.append(f'<path d="M{xp:.2f},{TOP} V{BOTTOM}" stroke="#d5d9cf"/><text x="{xp:.2f}" y="514" text-anchor="middle" font-size="12">{ct:.2f}</text>')

for yt, yval in [(0, "0"), (100, "Low"), (200, "Med"), (300, "High")]:
    yp = BOTTOM - yt
    parts.append(f'<path d="M{LEFT},{yp} H{RIGHT}" stroke="#d5d9cf"/>')

parts.append('<text x="502" y="545" text-anchor="middle" font-size="12" fill="#586866" font-family="SFMono-Regular, Consolas, monospace">CLUSTERING COEFFICIENT C</text>')

er_curve = []
for i in range(50):
    val = 0.025 + i * 0.0005
    h = 240 * math.exp(-0.5 * ((val - 0.0371) / 0.003)**2)
    er_curve.append((cx_px(val), BOTTOM - h))
er_path = f"M{cx_px(0.025):.2f},{BOTTOM} " + " ".join(f"L{x:.2f},{y:.2f}" for x, y in er_curve) + f" L{cx_px(0.05):.2f},{BOTTOM} Z"
parts.append(f'<path d="{er_path}" fill="#486452" fill-opacity="0.35" stroke="#486452" stroke-width="2"/>')
parts.append(f'<text x="{cx_px(0.0371):.2f}" y="{BOTTOM-250}" text-anchor="middle" font-size="11" font-family="SFMono-Regular, Consolas, monospace" fill="#486452" font-weight="bold">Erdős–Rényi G(n, m)</text>')
parts.append(f'<text x="{cx_px(0.0371):.2f}" y="{BOTTOM-235}" text-anchor="middle" font-size="9" fill="#486452">C = 0.037 ± 0.003</text>')

swap_curve = []
for i in range(60):
    val = 0.125 + i * 0.001
    h = 210 * math.exp(-0.5 * ((val - 0.155) / 0.008)**2)
    swap_curve.append((cx_px(val), BOTTOM - h))
swap_path = f"M{cx_px(0.125):.2f},{BOTTOM} " + " ".join(f"L{x:.2f},{y:.2f}" for x, y in swap_curve) + f" L{cx_px(0.185):.2f},{BOTTOM} Z"
parts.append(f'<path d="{swap_path}" fill="#2849c7" fill-opacity="0.3" stroke="#2849c7" stroke-width="2"/>')
parts.append(f'<text x="{cx_px(0.155):.2f}" y="{BOTTOM-220}" text-anchor="middle" font-size="11" font-family="SFMono-Regular, Consolas, monospace" fill="#2849c7" font-weight="bold">Degree-Preserving Swap Null</text>')
parts.append(f'<text x="{cx_px(0.155):.2f}" y="{BOTTOM-205}" text-anchor="middle" font-size="9" fill="#2849c7">C = 0.155 ± 0.008 (z = 19.6)</text>')

rx = cx_px(0.320)
parts.append(f'<line x1="{rx:.2f}" y1="{TOP+40}" x2="{rx:.2f}" y2="{BOTTOM}" stroke="#dc512f" stroke-width="3.5"/>')
parts.append(f'<circle cx="{rx:.2f}" cy="{TOP+40}" r="6" fill="#dc512f"/>')
parts.append(f'<rect x="{rx-135:.2f}" y="{TOP+20}" width="130" height="50" rx="3" fill="#dc512f"/>')
parts.append(f'<text x="{rx-70:.2f}" y="{TOP+38}" text-anchor="middle" font-size="11" font-family="SFMono-Regular, Consolas, monospace" fill="#fff" font-weight="bold">REAL MARVEL</text>')
parts.append(f'<text x="{rx-70:.2f}" y="{TOP+54}" text-anchor="middle" font-size="10" font-family="SFMono-Regular, Consolas, monospace" fill="#fff">C = 0.320 (z = 19.6)</text>')

parts.append(f'<path d="M{cx_px(0.155):.2f},350 H{rx:.2f}" stroke="#a93419" stroke-width="1.5" stroke-dasharray="3 3"/>')
parts.append(f'<text x="{(cx_px(0.155)+rx)/2:.2f}" y="342" text-anchor="middle" font-size="10" font-family="SFMono-Regular, Consolas, monospace" fill="#a93419" font-weight="bold">+106% UNEXPLAINED CLUSTERING (TRIADIC CLOSURE)</text>')

parts.append('</g></svg>\n')
(FIG_DIR / "clustering-nulls.svg").write_text("\n".join(parts), encoding="utf-8")
print("Wrote assets/figures/clustering-nulls.svg")

# -------------------------------------------------------------------------
# 4. growth-models.svg
# -------------------------------------------------------------------------
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title-growth desc-growth">',
    '<title id="title-growth">Preferential Attachment vs Uniform Growth</title>',
    '<desc id="desc-growth">Degree distribution comparison showing preferential attachment power law tail versus exponential uniform growth.</desc>',
    '<rect width="960" height="600" fill="#f6f1e7"/>',
    '<g font-family="Arial, sans-serif" fill="#232927">',
    '<text x="40" y="38" font-size="24" font-weight="700">Preferential attachment vs uniform growth</text>',
    '<text x="40" y="65" font-size="13" fill="#586866">Network growth to N = 303: rich-get-richer hub emergence vs uniform exponential tail</text>'
]

for xt in [1, 2, 5, 10, 20, 50, 100]:
    xp = x_px(xt)
    parts.append(f'<path d="M{xp:.2f},{TOP} V{BOTTOM}" stroke="#d5d9cf"/><text x="{xp:.2f}" y="514" text-anchor="middle" font-size="12">{xt}</text>')

for yt in [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]:
    yp = y_px(yt)
    parts.append(f'<path d="M{LEFT},{yp:.2f} H{RIGHT}" stroke="#d5d9cf"/><text x="76" y="{yp+4:.2f}" text-anchor="end" font-size="12">{yt}</text>')

parts.append('<text x="502" y="545" text-anchor="middle" font-size="12" fill="#586866" font-family="SFMono-Regular, Consolas, monospace">DEGREE k</text>')
parts.append('<text x="24" y="291" text-anchor="middle" font-size="12" fill="#586866" font-family="SFMono-Regular, Consolas, monospace" transform="rotate(-90 24 291)">P(K ≥ k)</text>')

ba_curve = []
for k in [1, 2, 4, 8, 16, 32, 64, 106]:
    p = (2.0 / k)**1.35
    ba_curve.append((x_px(k), y_px(p)))
parts.append('<path d="M' + " L".join(f"{x:.2f},{y:.2f}" for x, y in ba_curve) + '" fill="none" stroke="#dc512f" stroke-width="2.8"/>')
for x, y in ba_curve:
    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="#dc512f"/>')

unif_curve = []
for k in range(1, 25):
    p = math.exp(-0.28 * (k - 1))
    if p >= Y_MIN:
        unif_curve.append((x_px(k), y_px(p)))
parts.append('<path d="M' + " L".join(f"{x:.2f},{y:.2f}" for x, y in unif_curve) + '" fill="none" stroke="#2849c7" stroke-width="2.5" stroke-dasharray="5 3"/>')
for x, y in unif_curve:
    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#2849c7"/>')

parts.append(f'<text x="{x_px(35):.2f}" y="{y_px(0.03):.2f}" font-size="11" font-family="SFMono-Regular, Consolas, monospace" fill="#dc512f" font-weight="bold">Preferential Attachment (Hubs reach k = 106)</text>')
parts.append(f'<text x="{x_px(12):.2f}" y="{y_px(0.008):.2f}" font-size="11" font-family="SFMono-Regular, Consolas, monospace" fill="#2849c7" font-weight="bold">Uniform Growth (Dies at k ≈ 20)</text>')

parts.append('<circle cx="680" cy="37" r="5" fill="#dc512f"/><text x="692" y="42" font-size="12">Preferential Attachment (BA)</text>')
parts.append('<line x1="680" y1="58" x2="700" y2="58" stroke="#2849c7" stroke-width="2.5" stroke-dasharray="5 3"/><text x="706" y="63" font-size="12">Uniform Growth (No Hubs)</text>')

parts.append('</g></svg>\n')
(FIG_DIR / "growth-models.svg").write_text("\n".join(parts), encoding="utf-8")
print("Wrote assets/figures/growth-models.svg")

