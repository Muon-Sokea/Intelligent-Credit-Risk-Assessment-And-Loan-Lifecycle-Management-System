"""Subtle Cambodian banking visual accents for FinGuard AI."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

ASSETS_PNG_DIR = Path(__file__).resolve().parents[2] / "assets" / "png"


@st.cache_data(show_spinner=False)
def _load_png_data_uri(filename: str) -> str:
    """Load a transparent PNG from assets/png as a base64 data URI."""
    path = ASSETS_PNG_DIR / filename
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_sidebar_brand() -> None:
    """Render FinGuard AI sidebar brand header with subtle Khmer gold cloud accent."""
    cloud_uri = _load_png_data_uri("khmer_cloud_gold.png")
    cloud_img = (
        f'<img src="{cloud_uri}" alt="" '
        'style="position:absolute;right:8px;top:6px;height:28px;opacity:0.28;pointer-events:none;" />'
        if cloud_uri
        else ""
    )
    st.html(
        f"""
        <div style="
            position:relative;
            overflow:hidden;
            padding:12px 14px;
            border-radius:10px;
            background:linear-gradient(135deg, rgba(27,58,107,0.75) 0%, rgba(15,35,66,0.92) 100%);
            border:1px solid rgba(217,169,78,0.38);
            margin-bottom:4px;
        ">
            {cloud_img}
            <div style="display:flex;align-items:center;gap:8px;position:relative;z-index:1;">
                <span style="
                    display:inline-block;width:8px;height:8px;border-radius:50%;
                    background:#E5B95C;box-shadow:0 0 8px rgba(229,185,92,0.7);
                "></span>
                <span style="font-size:1.08rem;font-weight:700;letter-spacing:-0.01em;color:#F8FAFC;">
                    FinGuard AI
                </span>
            </div>
            <div style="font-size:0.74rem;color:#CBD5E1;margin-top:3px;position:relative;z-index:1;">
                Credit Risk &amp; Loan Lifecycle
            </div>
        </div>
        """
    )


def render_sidebar_footer() -> None:
    """Render a pinned golden lotus heritage footer at the bottom of the sidebar."""
    lotus_uri = _load_png_data_uri("khmer_lotus_bottom_gold.png")
    lotus_img = (
        f'<img src="{lotus_uri}" alt="" '
        'style="display:block;width:96px;margin:0 auto 4px;opacity:0.36;pointer-events:none;" />'
        if lotus_uri
        else ""
    )
    st.html(
        """
        <style>
        [data-testid="stSidebarContent"] {
            display: flex !important;
            flex-direction: column !important;
            height: 100vh !important;
            min-height: 100vh !important;
        }
        [data-testid="stSidebarNav"] {
            flex: 0 1 auto !important;
        }
        [data-testid="stSidebarUserContent"] {
            display: flex !important;
            flex-direction: column !important;
            flex: 1 1 auto !important;
            padding-bottom: 12px !important;
        }
        [data-testid="stSidebarUserContent"] > div,
        [data-testid="stSidebarUserContent"] > div > div,
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {
            display: flex !important;
            flex-direction: column !important;
            flex: 1 1 auto !important;
            height: 100% !important;
        }
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > div {
            flex: 0 0 auto;
        }
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > div:has(.st-key-sidebar-heritage-footer),
        .st-key-sidebar-heritage-footer {
            margin-top: auto !important;
            position: sticky !important;
            bottom: 0 !important;
            z-index: 3;
            background: var(--background-color, #0F2342);
            padding: 8px 0 4px;
        }
        </style>
        """
    )
    with st.container(key="sidebar-heritage-footer"):
        st.html(
            f"""
            <div style="
                padding-top:10px;
                border-top:1px solid rgba(217,169,78,0.26);
                text-align:center;
            ">
                {lotus_img}
                <div style="font-size:0.68rem;color:#94A3B8;letter-spacing:0.04em;text-transform:uppercase;">
                    Cambodia Banking Decision Support
                </div>
            </div>
            """
        )


def render_page_banner(title: str, role_short: str, subtitle: str = "") -> None:
    """Render a compact navy-and-gold executive header banner with Khmer skyline watermark."""
    skyline_uri = _load_png_data_uri("khmer_skyline_gold.png")
    frame_uri = _load_png_data_uri("khmer_frame_gold.png")

    skyline_img = (
        f'<img src="{skyline_uri}" alt="" '
        'style="position:absolute;right:18px;bottom:-4px;height:78px;opacity:0.24;pointer-events:none;" />'
        if skyline_uri
        else ""
    )
    frame_img = (
        f'<img src="{frame_uri}" alt="" '
        'style="position:absolute;left:-6px;top:-6px;height:94px;opacity:0.16;pointer-events:none;" />'
        if frame_uri
        else ""
    )

    safe_title = html.escape(title)
    safe_role = html.escape(role_short)
    safe_sub = html.escape(subtitle)
    sub_html = (
        f'<div style="font-size:0.8rem;color:#CBD5E1;margin-top:4px;max-width:640px;">{safe_sub}</div>'
        if safe_sub
        else ""
    )

    st.html(
        f"""
        <div style="
            position:relative;
            overflow:hidden;
            padding:16px 22px;
            border-radius:12px;
            background:linear-gradient(125deg, #0F2342 0%, #1B3A6B 62%, #1E3A5F 100%);
            border:1px solid rgba(217,169,78,0.42);
            margin-bottom:8px;
        ">
            {frame_img}
            {skyline_img}
            <div style="position:relative;z-index:1;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
                <div>
                    <div style="font-size:1.45rem;font-weight:700;color:#FFFFFF;line-height:1.2;letter-spacing:-0.02em;">
                        {safe_title}
                    </div>
                    {sub_html}
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                    <span style="
                        padding:4px 10px;border-radius:999px;font-size:0.74rem;font-weight:600;
                        color:#FDE68A;background:rgba(217,169,78,0.16);
                        border:1px solid rgba(217,169,78,0.45);
                    ">
                        Role: {safe_role}
                    </span>
                    <span style="
                        padding:4px 10px;border-radius:999px;font-size:0.74rem;font-weight:500;
                        color:#E2E8F0;background:rgba(255,255,255,0.08);
                        border:1px solid rgba(255,255,255,0.18);
                    ">
                        Decision Support
                    </span>
                </div>
            </div>
        </div>
        """
    )
