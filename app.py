import os
import random
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import torch
import torch.nn as nn
import torch.nn.functional as F


# -----------------------------
# Page config + CSS
# -----------------------------
st.set_page_config(
    page_title="Torus Topology Classifier",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root {
    --bg1: #0b1020;
    --bg2: #121a30;
    --card: rgba(255,255,255,0.07);
    --stroke: rgba(255,255,255,0.10);
    --text: #ecf2ff;
    --muted: #b7c3e0;
    --green: #00998c;
    --yellow: #f2d933;
    --purple: #5c298c;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(92,41,140,0.25), transparent 30%),
        radial-gradient(circle at top right, rgba(0,153,140,0.20), transparent 28%),
        linear-gradient(135deg, var(--bg1), var(--bg2));
    color: var(--text);
}

.block-container {
    padding-top: 1.6rem;
    padding-bottom: 2rem;
}

.hero {
    padding: 1.4rem 1.5rem;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
    border: 1px solid var(--stroke);
    box-shadow: 0 16px 40px rgba(0,0,0,0.25);
    margin-bottom: 1rem;
}

.hero h1 {
    font-size: 2.2rem;
    margin: 0 0 0.35rem 0;
    color: var(--text);
}

.hero p {
    margin: 0;
    color: var(--muted);
    line-height: 1.6;
}

.metric-card {
    background: var(--card);
    border: 1px solid var(--stroke);
    border-radius: 22px;
    padding: 1rem 1.1rem;
    box-shadow: 0 12px 28px rgba(0,0,0,0.18);
}

.section-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--stroke);
    border-radius: 24px;
    padding: 1rem 1rem 0.5rem 1rem;
    margin-top: 0.6rem;
}

.small-note {
    color: var(--muted);
    font-size: 0.95rem;
}

.stButton > button {
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,0.12);
    background: linear-gradient(135deg, rgba(92,41,140,0.95), rgba(0,153,140,0.95));
    color: white;
    font-weight: 700;
    padding: 0.6rem 1rem;
}

[data-testid="stSidebar"] {
    background: rgba(9, 13, 26, 0.97);
    border-right: 1px solid rgba(255,255,255,0.07);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# -----------------------------
# Constants
# -----------------------------
C_GREEN = "rgb(0,153,140)"
C_YELLOW = "rgb(242,217,51)"
C_PURPLE = "rgb(92,41,140)"
CLASS_NAMES = {0: "Green", 1: "Yellow", 2: "Purple"}
CLASS_COLORS = {0: C_GREEN, 1: C_YELLOW, 2: C_PURPLE}

R_MAJOR = 2.0
R_MINOR = 0.75
Y1_START, Y1_END = 0.20 * np.pi, 0.55 * np.pi
P_START, P_END = 0.55 * np.pi, 0.70 * np.pi
Y2_START, Y2_END = 0.70 * np.pi, 1.05 * np.pi


# -----------------------------
# Utilities
# -----------------------------
@dataclass
class Config:
    seed: int = 2
    n_points: int = 6000
    noise: float = 0.01
    epochs: int = 700
    lr: float = 2e-3
    weight_decay: float = 1e-5
    grad_clip: float = 1.0
    lambda_w1_disk: float = 1.0
    lambda_w2_ortho: float = 0.05
    lambda_w3_ribbon: float = 1.2
    lambda_simplex_spread: float = 0.03
    lambda_vertex_pull: float = 0.20


def set_seed(seed: int) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True)
    except Exception:
        pass


def build_dataset(cfg: Config):
    rng = np.random.default_rng(cfg.seed)
    theta = rng.uniform(0, 2 * np.pi, size=cfg.n_points)
    phi = rng.uniform(0, 2 * np.pi, size=cfg.n_points)

    x = (R_MAJOR + R_MINOR * np.cos(phi)) * np.cos(theta)
    y = (R_MAJOR + R_MINOR * np.cos(phi)) * np.sin(theta)
    z = R_MINOR * np.sin(phi)

    raw = np.stack([x, y, z], axis=1).astype(np.float32)
    raw += rng.normal(scale=cfg.noise, size=raw.shape).astype(np.float32)

    t = theta % (2 * np.pi)
    labels = np.zeros_like(t, dtype=int)
    labels[(t >= Y1_START) & (t < Y1_END)] = 1
    labels[(t >= Y2_START) & (t < Y2_END)] = 1
    labels[(t >= P_START) & (t < P_END)] = 2

    mu = raw.mean(axis=0, keepdims=True)
    sd = raw.std(axis=0, keepdims=True) + 1e-8
    std = ((raw - mu) / sd).astype(np.float32)
    return raw, std, labels, theta


class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.W1 = nn.Linear(3, 3, bias=True)
        self.W2 = nn.Linear(3, 3, bias=True)
        self.W3 = nn.Linear(3, 3, bias=True)
        self.W4 = nn.Linear(3, 3, bias=True)

        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_uniform_(m.weight, nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward_trace(self, x):
        z1 = self.W1(x)
        a1 = F.relu(z1)
        z2 = self.W2(a1)
        a2 = F.relu(z2)
        z3 = self.W3(a2)
        a3 = F.relu(z3)
        logits = self.W4(a3)
        return z1, a1, z2, a2, z3, a3, logits

    def forward(self, x):
        return self.forward_trace(x)[-1]


def ortho_penalty(W):
    I = torch.eye(W.shape[0], device=W.device, dtype=W.dtype)
    return torch.sum((W.T @ W - I) ** 2)


def collapse_one_dim_loss(P):
    return torch.min(torch.var(P, dim=0, unbiased=False))


def simplex_spread_loss(logits):
    Z = logits - logits.mean(dim=0, keepdim=True)
    C = (Z.T @ Z) / (Z.shape[0] + 1e-8)
    eig = torch.linalg.eigvalsh(C)
    return 1.0 / (eig[-2] + 1e-6)


def vertex_pull_loss(probs, y, n_classes=3):
    V = torch.eye(n_classes, device=probs.device, dtype=probs.dtype)
    loss = 0.0
    for c in range(n_classes):
        pc = probs[y == c]
        if pc.numel() > 0:
            loss = loss + torch.mean((pc.mean(dim=0) - V[c]) ** 2)
    return loss


@st.cache_resource(show_spinner=False)
def train_model_cached(cfg: Config):
    set_seed(cfg.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    raw, std, labels, theta = build_dataset(cfg)
    X = torch.tensor(std, dtype=torch.float32, device=device)
    y_t = torch.tensor(labels, dtype=torch.long, device=device)

    model = Net().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    history = []
    for ep in range(1, cfg.epochs + 1):
        model.train()
        opt.zero_grad()
        z1, a1, z2, a2, z3, a3, logits = model.forward_trace(X)

        ce = F.cross_entropy(logits, y_t)
        disk_loss = collapse_one_dim_loss(z1)
        ribbon_loss = collapse_one_dim_loss(z3)
        ortho_loss = ortho_penalty(model.W2.weight)
        spread_loss = simplex_spread_loss(logits)
        probs_train = F.softmax(logits, dim=1)
        vpull_loss = vertex_pull_loss(probs_train, y_t)
        wd = sum((p * p).sum() for p in model.parameters())

        loss = (
            ce
            + cfg.lambda_w1_disk * disk_loss
            + cfg.lambda_w3_ribbon * ribbon_loss
            + cfg.lambda_w2_ortho * ortho_loss
            + cfg.lambda_simplex_spread * spread_loss
            + cfg.lambda_vertex_pull * vpull_loss
            + cfg.weight_decay * wd
        )

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        opt.step()

        if ep == 1 or ep % 25 == 0 or ep == cfg.epochs:
            with torch.no_grad():
                acc = (logits.argmax(dim=1) == y_t).float().mean().item()
            history.append(
                {
                    "epoch": ep,
                    "loss": float(loss.item()),
                    "accuracy": float(acc),
                    "ce": float(ce.item()),
                    "disk": float(disk_loss.item()),
                    "ribbon": float(ribbon_loss.item()),
                    "spread": float(spread_loss.item()),
                    "vpull": float(vpull_loss.item()),
                }
            )

    model.eval()
    with torch.no_grad():
        z1, a1, z2, a2, z3, a3, logits = model.forward_trace(X)
        probs = F.softmax(logits / 0.7, dim=1)
        preds = logits.argmax(dim=1)
        acc = (preds == y_t).float().mean().item()

    outputs = {
        "P0_raw": raw,
        "P0_plot": std,
        "P1": z1.detach().cpu().numpy(),
        "P2": a1.detach().cpu().numpy(),
        "P3": z2.detach().cpu().numpy(),
        "P4": a2.detach().cpu().numpy(),
        "P5": z3.detach().cpu().numpy(),
        "P6": a3.detach().cpu().numpy(),
        "P7": probs.detach().cpu().numpy(),
        "labels": labels,
        "theta": theta,
        "preds": preds.detach().cpu().numpy(),
        "device": device,
        "accuracy": acc,
        "history": pd.DataFrame(history),
    }
    return model.cpu(), outputs


def build_all_layers_figure(outputs):
    titles = [
        "Step 1: Input torus in ℝ³",
        "Step 2: After learned W1",
        "Step 3: After ReLU",
        "Step 4: After learned W2",
        "Step 5: After ReLU",
        "Step 6: After learned W3",
        "Step 7: After ReLU",
        "Step 8: Softmax output (Δ₂)",
    ]
    points_list = [
        outputs["P0_plot"], outputs["P1"], outputs["P2"], outputs["P3"],
        outputs["P4"], outputs["P5"], outputs["P6"], outputs["P7"],
    ]
    labels = outputs["labels"]

    fig = make_subplots(
        rows=2,
        cols=4,
        specs=[[{"type": "scene"}] * 4, [{"type": "scene"}] * 4],
        subplot_titles=titles,
        horizontal_spacing=0.02,
        vertical_spacing=0.07,
    )

    k = 0
    for r in [1, 2]:
        for c in [1, 2, 3, 4]:
            P = points_list[k]
            for cls in [0, 1, 2]:
                idx = labels == cls
                fig.add_trace(
                    go.Scatter3d(
                        x=P[idx, 0],
                        y=P[idx, 1],
                        z=P[idx, 2],
                        mode="markers",
                        marker=dict(size=2, color=CLASS_COLORS[cls], opacity=0.95),
                        name=CLASS_NAMES[cls],
                        showlegend=(k == 0),
                    ),
                    row=r,
                    col=c,
                )
            k += 1

    for i in range(1, 9):
        fig.update_layout(
            **{
                f"scene{i}": dict(
                    xaxis=dict(showgrid=True, zeroline=False, visible=True),
                    yaxis=dict(showgrid=True, zeroline=False, visible=True),
                    zaxis=dict(showgrid=True, zeroline=False, visible=True),
                    aspectmode="data",
                    camera=dict(eye=dict(x=1.6, y=1.3, z=0.7)),
                )
            }
        )

    fig.update_layout(
        title="Interactive layer-by-layer geometry of the learned torus classifier",
        height=850,
        margin=dict(l=10, r=150, t=70, b=10),
        legend=dict(
            x=1.01,
            y=1,
            bgcolor="rgba(255,255,255,0.75)",
            bordercolor="rgba(0,0,0,0.18)",
            borderwidth=1,
        ),
    )
    return fig


def build_training_curve(history_df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history_df["epoch"], y=history_df["loss"], mode="lines+markers", name="Total loss"))
    fig.add_trace(go.Scatter(x=history_df["epoch"], y=history_df["ce"], mode="lines", name="Cross entropy"))
    fig.update_layout(
        title="Training loss history",
        xaxis_title="Epoch",
        yaxis_title="Loss",
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def build_accuracy_curve(history_df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history_df["epoch"], y=100 * history_df["accuracy"], mode="lines+markers", name="Accuracy (%)"))
    fig.update_layout(
        title="Training accuracy",
        xaxis_title="Epoch",
        yaxis_title="Accuracy (%)",
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def build_confusion_matrix(outputs):
    labels = outputs["labels"]
    preds = outputs["preds"]
    cm = np.zeros((3, 3), dtype=int)
    for a, p in zip(labels, preds):
        cm[a, p] += 1

    fig = go.Figure(
        data=go.Heatmap(
            z=cm,
            x=[CLASS_NAMES[i] for i in range(3)],
            y=[CLASS_NAMES[i] for i in range(3)],
            text=cm,
            texttemplate="%{text}",
            colorscale="Viridis",
        )
    )
    fig.update_layout(
        title="Confusion matrix",
        xaxis_title="Predicted class",
        yaxis_title="True class",
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def class_probability_table(prob_vector):
    return pd.DataFrame(
        {
            "Class": [CLASS_NAMES[0], CLASS_NAMES[1], CLASS_NAMES[2]],
            "Probability": [float(prob_vector[0]), float(prob_vector[1]), float(prob_vector[2])],
        }
    ).sort_values("Probability", ascending=False)


def predict_single_point(model, point_xyz):
    x = torch.tensor(point_xyz, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        probs = F.softmax(model(x), dim=1).squeeze(0).numpy()
    pred = int(np.argmax(probs))
    return pred, probs


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("⚙️ Controls")
seed = st.sidebar.number_input("Random seed", min_value=1, max_value=9999, value=2, step=1)
n_points = st.sidebar.slider("Number of torus points", 1500, 12000, 6000, step=500)
noise = st.sidebar.slider("Noise level", 0.0, 0.08, 0.01, step=0.005)
epochs = st.sidebar.slider("Training epochs", 100, 1500, 700, step=100)
lr = st.sidebar.select_slider("Learning rate", options=[5e-4, 1e-3, 2e-3, 3e-3, 5e-3], value=2e-3)

cfg = Config(seed=int(seed), n_points=int(n_points), noise=float(noise), epochs=int(epochs), lr=float(lr))

st.markdown(
    """
    <div class="hero">
        <h1>🧠 Torus Topology Classifier Dashboard</h1>
        <p>
            This Streamlit app turns your notebook model into a polished interactive demo. It generates a labeled torus,
            trains the neural network, shows the geometry at every layer, and lets you test predictions on custom 3D points.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.spinner("Training model and preparing interactive outputs..."):
    model, outputs = train_model_cached(cfg)

history_df = outputs["history"]

# -----------------------------
# Top metrics
# -----------------------------
col1, col2, col3, col4 = st.columns(4)
col1.markdown(f'<div class="metric-card"><h3>Accuracy</h3><h2>{outputs["accuracy"] * 100:.2f}%</h2></div>', unsafe_allow_html=True)
col2.markdown(f'<div class="metric-card"><h3>Device</h3><h2>{outputs["device"].upper()}</h2></div>', unsafe_allow_html=True)
col3.markdown(f'<div class="metric-card"><h3>Points</h3><h2>{cfg.n_points:,}</h2></div>', unsafe_allow_html=True)
col4.markdown(f'<div class="metric-card"><h3>Epochs</h3><h2>{cfg.epochs}</h2></div>', unsafe_allow_html=True)

# -----------------------------
# Main tabs
# -----------------------------
tab1, tab2, tab3 = st.tabs(["Model Visuals", "Training Analytics", "Single-Point Prediction"])

with tab1:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.plotly_chart(build_all_layers_figure(outputs), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("Rotate any 3D panel to inspect how the learned transformations reshape the torus through the network.")

with tab2:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(build_training_curve(history_df), use_container_width=True)
    with c2:
        st.plotly_chart(build_accuracy_curve(history_df), use_container_width=True)

    c3, c4 = st.columns([1.2, 1])
    with c3:
        st.plotly_chart(build_confusion_matrix(outputs), use_container_width=True)
    with c4:
        latest = history_df.tail(10).copy()
        latest["accuracy"] = (latest["accuracy"] * 100).round(2)
        st.dataframe(latest, use_container_width=True)

with tab3:
    st.markdown("### Test the model on one custom 3D point")
    st.markdown('<p class="small-note">Enter standardized coordinates. The app will return the predicted class and the full class-probability breakdown.</p>', unsafe_allow_html=True)

    pc1, pc2 = st.columns([1, 1.2])
    with pc1:
        x_val = st.number_input("x", value=0.0, format="%.4f")
        y_val = st.number_input("y", value=0.0, format="%.4f")
        z_val = st.number_input("z", value=0.0, format="%.4f")
        run_pred = st.button("Predict point")

    with pc2:
        if run_pred:
            pred, probs = predict_single_point(model, [x_val, y_val, z_val])
            st.success(f"Predicted class: {CLASS_NAMES[pred]}")
            st.dataframe(class_probability_table(probs), use_container_width=True)

            bar = go.Figure()
            bar.add_trace(go.Bar(x=[CLASS_NAMES[0], CLASS_NAMES[1], CLASS_NAMES[2]], y=probs))
            bar.update_layout(title="Class probabilities", yaxis_title="Probability", height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("Click 'Predict point' to see the model output.")

st.markdown("---")
st.markdown(
    "<p class='small-note'>Built from your uploaded notebook model, now packaged for Streamlit deployment.</p>",
    unsafe_allow_html=True,
)
