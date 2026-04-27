#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI [Application Name] [Group Letter] [Group Name]
Module: SpyderG31_PlotlyTemplates.py [Application Name][Group Letter] [Module Number]_[Purpose].py
Purpose: Templates for Plotly charts
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-15 Time: 22:24:00

Module Description:
    Templates for Plotly charts in the Spyder Trading Dashboard. Provides
    reusable Plotly chart templates optimized for quantitative trading visualization.
    Templates include candlestick charts, technical indicators, volume analysis,
    and options-specific overlays. All templates match the Spyder dashboard dark
    theme and provide superior interactivity for trading analysis.

    This module was renumbered from SpyderG04_PlotlyTemplates.py as part of the
    modular refactoring effort to eliminate duplicate module numbers and improve
    code organization.

Module Constants:
    DEFAULT_THEME (str): Default Plotly theme for charts ("plotly_dark")
    DEFAULT_HEIGHT (int): Default chart height in pixels (600)
    DEFAULT_WIDTH (int): Default chart width in pixels (1200)
    COLOR_PALETTE (dict): Color palette for chart elements

Change Log:
    2025-10-15 (v1.6.0):
        - Renumbered from SpyderG04_PlotlyTemplates.py to SpyderG31_PlotlyTemplates.py
        - Updated module header with standard structure
        - Enhanced documentation and constants
    2025-09-27 (v1.5):
        - Initial module creation with Plotly templates
        - Added financial chart templates with dark theme
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# ==============================================================================
# CONSTANTS & STYLING
# ==============================================================================
# Spyder dashboard color scheme
COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#FF073A",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "cyan": "#00ffff",
    "purple": "#BF00FF",
    "grid": "#2a2a2a",
}

# Base template for all charts
BASE_LAYOUT = {
    "paper_bgcolor": COLORS["panel"],
    "plot_bgcolor": COLORS["panel"],
    "font": {"color": COLORS["text"], "family": "Arial", "size": 12},
    "showlegend": True,
    "legend": {
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "right",
        "x": 1,
        "bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLORS["text"], "size": 10},
    },
    "margin": {"l": 60, "r": 30, "t": 30, "b": 40},
    "hovermode": "x unified",
}

# Axis styling
AXIS_STYLE = {
    "gridcolor": COLORS["grid"],
    "linecolor": COLORS["border"],
    "tickcolor": COLORS["text"],
    "tickfont": {"color": COLORS["text"], "size": 10},
    "titlefont": {"color": COLORS["text"], "size": 11},
}


# ==============================================================================
# CANDLESTICK CHART TEMPLATES
# ==============================================================================
class CandlestickChartTemplate:
    """Template for candlestick charts with technical indicators."""

    @staticmethod
    def create_basic_candlestick(
        df: pd.DataFrame, symbol: str = "SPY", height: int = 600
    ) -> go.Figure:
        """Create basic candlestick chart."""
        fig = go.Figure()

        # Candlestick trace
        candlestick = go.Candlestick(
            x=df["datetime"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol,
            increasing_line_color=COLORS["positive"],
            decreasing_line_color=COLORS["negative"],
            increasing_fillcolor=COLORS["positive"],
            decreasing_fillcolor=COLORS["negative"],
            line=dict(width=1),
        )
        fig.add_trace(candlestick)

        # Apply styling
        fig.update_layout(
            **BASE_LAYOUT,
            title=f"{symbol} Price Chart",
            height=height,
            xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(**AXIS_STYLE, title="Time")
        fig.update_yaxes(**AXIS_STYLE, title="Price ($)")

        return fig

    @staticmethod
    def create_advanced_candlestick(
        df: pd.DataFrame,
        symbol: str = "SPY",
        indicators: dict | None = None,
        height: int = 700,
    ) -> go.Figure:
        """Create advanced candlestick chart with multiple technical indicators."""
        if indicators is None:
            indicators = {
                "sma_20": True,
                "sma_50": True,
                "vwap": True,
                "bollinger": True,
                "volume": True,
                "rsi": False,
            }

        # Determine number of subplots
        rows = 1
        if indicators.get("volume", False):
            rows += 1
        if indicators.get("rsi", False):
            rows += 1

        # Create subplots
        subplot_titles = [f"{symbol} Price"]
        row_heights = [0.6]

        if indicators.get("volume", False):
            subplot_titles.append("Volume")
            row_heights.append(0.2)
        if indicators.get("rsi", False):
            subplot_titles.append("RSI")
            row_heights.append(0.2)

        # Normalize row heights
        row_heights = [h / sum(row_heights) for h in row_heights]

        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=row_heights,
            subplot_titles=subplot_titles,
        )

        # Main candlestick chart
        candlestick = go.Candlestick(
            x=df["datetime"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=symbol,
            increasing_line_color=COLORS["positive"],
            decreasing_line_color=COLORS["negative"],
            increasing_fillcolor=COLORS["positive"],
            decreasing_fillcolor=COLORS["negative"],
        )
        fig.add_trace(candlestick, row=1, col=1)

        # Technical indicators on price chart
        current_row = 1

        # Moving averages
        if indicators.get("sma_20", False) and "sma_20" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["sma_20"],
                    mode="lines",
                    name="SMA20",
                    line=dict(color=COLORS["cyan"], width=1.5),
                    opacity=0.8,
                ),
                row=current_row,
                col=1,
            )

        if indicators.get("sma_50", False) and "sma_50" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["sma_50"],
                    mode="lines",
                    name="SMA50",
                    line=dict(color=COLORS["warning"], width=1.5),
                    opacity=0.8,
                ),
                row=current_row,
                col=1,
            )

        # VWAP
        if indicators.get("vwap", False) and "vwap" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["vwap"],
                    mode="lines",
                    name="VWAP",
                    line=dict(color=COLORS["purple"], width=2),
                    opacity=0.9,
                ),
                row=current_row,
                col=1,
            )

        # Bollinger Bands
        if indicators.get("bollinger", False):
            if "bb_upper" in df.columns and "bb_lower" in df.columns:
                # Upper band
                fig.add_trace(
                    go.Scatter(
                        x=df["datetime"],
                        y=df["bb_upper"],
                        mode="lines",
                        name="BB Upper",
                        line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
                        opacity=0.6,
                    ),
                    row=current_row,
                    col=1,
                )

                # Lower band
                fig.add_trace(
                    go.Scatter(
                        x=df["datetime"],
                        y=df["bb_lower"],
                        mode="lines",
                        name="BB Lower",
                        line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
                        fill="tonexty",
                        fillcolor="rgba(136,136,136,0.1)",
                        opacity=0.6,
                    ),
                    row=current_row,
                    col=1,
                )

        # Volume chart
        if indicators.get("volume", False):
            current_row += 1
            colors = [
                COLORS["positive"] if close >= open_price else COLORS["negative"]
                for close, open_price in zip(df["close"], df["open"], strict=False)
            ]

            fig.add_trace(
                go.Bar(
                    x=df["datetime"],
                    y=df["volume"],
                    name="Volume",
                    marker_color=colors,
                    opacity=0.7,
                ),
                row=current_row,
                col=1,
            )

        # RSI chart
        if indicators.get("rsi", False) and "rsi" in df.columns:
            current_row += 1
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["rsi"],
                    mode="lines",
                    name="RSI",
                    line=dict(color=COLORS["neutral"], width=2),
                ),
                row=current_row,
                col=1,
            )

            # RSI overbought/oversold levels
            fig.add_hline(
                y=70, line_dash="dash", line_color=COLORS["negative"], opacity=0.5
            )
            fig.add_hline(
                y=30, line_dash="dash", line_color=COLORS["positive"], opacity=0.5
            )

        # Apply styling
        fig.update_layout(**BASE_LAYOUT, height=height, xaxis_rangeslider_visible=False)
        fig.update_xaxes(**AXIS_STYLE)
        fig.update_yaxes(**AXIS_STYLE)

        return fig


# ==============================================================================
# OPTIONS-SPECIFIC CHARTS
# ==============================================================================
class OptionsChartTemplate:
    """Templates for options-specific visualizations."""

    @staticmethod
    def create_options_flow_chart(df: pd.DataFrame, height: int = 500) -> go.Figure:
        """Create options flow visualization."""
        fig = go.Figure()

        # Call vs Put volume
        if "call_volume" in df.columns and "put_volume" in df.columns:
            fig.add_trace(
                go.Bar(
                    x=df["datetime"],
                    y=df["call_volume"],
                    name="Call Volume",
                    marker_color=COLORS["positive"],
                    opacity=0.7,
                )
            )

            fig.add_trace(
                go.Bar(
                    x=df["datetime"],
                    y=-df["put_volume"],  # Negative for visual separation
                    name="Put Volume",
                    marker_color=COLORS["negative"],
                    opacity=0.7,
                )
            )

        fig.update_layout(
            **BASE_LAYOUT,
            title="Options Flow - Calls vs Puts",
            height=height,
            yaxis_title="Volume",
            barmode="relative",
        )
        fig.update_xaxes(**AXIS_STYLE, title="Time")
        fig.update_yaxes(**AXIS_STYLE)

        return fig

    @staticmethod
    def create_gamma_exposure_chart(df: pd.DataFrame, height: int = 400) -> go.Figure:
        """Create Gamma Exposure (GEX) visualization."""
        fig = go.Figure()

        if "gex" in df.columns:
            colors = [
                COLORS["positive"] if gex > 0 else COLORS["negative"]
                for gex in df["gex"]
            ]

            fig.add_trace(
                go.Bar(
                    x=df["datetime"],
                    y=df["gex"],
                    name="GEX",
                    marker_color=colors,
                    opacity=0.8,
                )
            )

            # Zero line
            fig.add_hline(y=0, line_color=COLORS["text_dim"], line_width=1)

        fig.update_layout(
            **BASE_LAYOUT,
            title="Gamma Exposure (GEX)",
            height=height,
            yaxis_title="GEX ($B)",
        )
        fig.update_xaxes(**AXIS_STYLE, title="Time")
        fig.update_yaxes(**AXIS_STYLE)

        return fig


# ==============================================================================
# VOLATILITY CHARTS
# ==============================================================================
class VolatilityChartTemplate:
    """Templates for volatility analysis."""

    @staticmethod
    def create_vix_term_structure(vix_data: dict, height: int = 400) -> go.Figure:
        """Create VIX term structure chart."""
        fig = go.Figure()

        # VIX term structure (if available)
        if all(k in vix_data for k in ["vix9d", "vix", "vxv", "vxmt"]):
            terms = ["9D", "30D", "3M", "6M"]
            values = [
                vix_data["vix9d"],
                vix_data["vix"],
                vix_data["vxv"],
                vix_data["vxmt"],
            ]

            fig.add_trace(
                go.Scatter(
                    x=terms,
                    y=values,
                    mode="lines+markers",
                    name="VIX Term Structure",
                    line=dict(color=COLORS["warning"], width=3),
                    marker=dict(size=8, color=COLORS["warning"]),
                )
            )

        fig.update_layout(
            **BASE_LAYOUT,
            title="VIX Term Structure",
            height=height,
            xaxis_title="Term",
            yaxis_title="Implied Volatility (%)",
        )
        fig.update_xaxes(**AXIS_STYLE)
        fig.update_yaxes(**AXIS_STYLE)

        return fig

    @staticmethod
    def create_realized_vs_implied_vol(
        df: pd.DataFrame, height: int = 400
    ) -> go.Figure:
        """Create realized vs implied volatility comparison."""
        fig = go.Figure()

        if "realized_vol" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["realized_vol"],
                    mode="lines",
                    name="Realized Vol",
                    line=dict(color=COLORS["cyan"], width=2),
                )
            )

        if "implied_vol" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["implied_vol"],
                    mode="lines",
                    name="Implied Vol (VIX)",
                    line=dict(color=COLORS["warning"], width=2),
                )
            )

        fig.update_layout(
            **BASE_LAYOUT,
            title="Realized vs Implied Volatility",
            height=height,
            yaxis_title="Volatility (%)",
        )
        fig.update_xaxes(**AXIS_STYLE, title="Time")
        fig.update_yaxes(**AXIS_STYLE)

        return fig


# ==============================================================================
# MARKET MICROSTRUCTURE CHARTS
# ==============================================================================
class MicrostructureChartTemplate:
    """Templates for market microstructure analysis."""

    @staticmethod
    def create_orderbook_heatmap(
        orderbook_data: pd.DataFrame, height: int = 500
    ) -> go.Figure:
        """Create order book heatmap visualization."""
        fig = go.Figure()

        if not orderbook_data.empty:
            fig.add_trace(
                go.Heatmap(
                    z=orderbook_data.values,
                    x=orderbook_data.columns,
                    y=orderbook_data.index,
                    colorscale=[
                        [0, COLORS["negative"]],
                        [0.5, COLORS["panel"]],
                        [1, COLORS["positive"]],
                    ],
                    showscale=True,
                )
            )

        fig.update_layout(
            **BASE_LAYOUT,
            title="Order Book Depth",
            height=height,
            xaxis_title="Price Levels",
            yaxis_title="Time",
        )

        return fig

    @staticmethod
    def create_tick_analysis(df: pd.DataFrame, height: int = 400) -> go.Figure:
        """Create tick analysis chart."""
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            row_heights=[0.6, 0.4],
            subplot_titles=["Price Ticks", "Tick Direction"],
        )

        # Price ticks
        if "price" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["price"],
                    mode="lines",
                    name="Price Ticks",
                    line=dict(color=COLORS["cyan"], width=1),
                ),
                row=1,
                col=1,
            )

        # Tick direction (uptick/downtick)
        if "tick_direction" in df.columns:
            colors = [
                COLORS["positive"] if td > 0 else COLORS["negative"]
                for td in df["tick_direction"]
            ]

            fig.add_trace(
                go.Bar(
                    x=df["datetime"],
                    y=df["tick_direction"],
                    name="Tick Direction",
                    marker_color=colors,
                    opacity=0.7,
                ),
                row=2,
                col=1,
            )

        fig.update_layout(**BASE_LAYOUT, height=height)
        fig.update_xaxes(**AXIS_STYLE)
        fig.update_yaxes(**AXIS_STYLE)

        return fig


# ==============================================================================
# PERFORMANCE & ANALYTICS CHARTS
# ==============================================================================
class PerformanceChartTemplate:
    """Templates for trading performance analysis."""

    @staticmethod
    def create_pnl_chart(df: pd.DataFrame, height: int = 400) -> go.Figure:
        """Create P&L performance chart."""
        fig = go.Figure()

        # Cumulative P&L
        if "cumulative_pnl" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["cumulative_pnl"],
                    mode="lines",
                    name="Cumulative P&L",
                    line=dict(color=COLORS["positive"], width=2),
                    fill="tonexty" if df["cumulative_pnl"].iloc[0] >= 0 else "tozeroy",
                    fillcolor=f"rgba{tuple(list(bytes.fromhex(COLORS['positive'][1:])) + [50])}",
                )
            )

        # Daily P&L bars
        if "daily_pnl" in df.columns:
            colors = [
                COLORS["positive"] if pnl >= 0 else COLORS["negative"]
                for pnl in df["daily_pnl"]
            ]

            fig.add_trace(
                go.Bar(
                    x=df["datetime"],
                    y=df["daily_pnl"],
                    name="Daily P&L",
                    marker_color=colors,
                    opacity=0.6,
                    yaxis="y2",
                )
            )

        # Zero line
        fig.add_hline(y=0, line_color=COLORS["text_dim"], line_width=1)

        fig.update_layout(
            **BASE_LAYOUT,
            title="Trading Performance",
            height=height,
            yaxis_title="Cumulative P&L ($)",
            yaxis2=dict(
                title="Daily P&L ($)", overlaying="y", side="right", **AXIS_STYLE
            ),
        )
        fig.update_xaxes(**AXIS_STYLE, title="Time")
        fig.update_yaxes(**AXIS_STYLE)

        return fig

    @staticmethod
    def create_drawdown_chart(df: pd.DataFrame, height: int = 300) -> go.Figure:
        """Create drawdown analysis chart."""
        fig = go.Figure()

        if "drawdown" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["datetime"],
                    y=df["drawdown"],
                    mode="lines",
                    name="Drawdown",
                    line=dict(color=COLORS["negative"], width=2),
                    fill="tozeroy",
                    fillcolor=f"rgba{tuple(list(bytes.fromhex(COLORS['negative'][1:])) + [30])}",
                )
            )

        fig.update_layout(
            **BASE_LAYOUT,
            title="Drawdown Analysis",
            height=height,
            yaxis_title="Drawdown (%)",
        )
        fig.update_xaxes(**AXIS_STYLE, title="Time")
        fig.update_yaxes(**AXIS_STYLE)

        return fig


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate common technical indicators for chart templates."""
    df = df.copy()

    # Simple Moving Averages
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["sma_50"] = df["close"].rolling(window=50).mean()

    # VWAP
    if "volume" in df.columns:
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

    # Bollinger Bands
    rolling_mean = df["close"].rolling(window=20).mean()
    rolling_std = df["close"].rolling(window=20).std()
    df["bb_upper"] = rolling_mean + (rolling_std * 2)
    df["bb_lower"] = rolling_mean - (rolling_std * 2)

    # RSI (placeholder - implement proper calculation as needed)
    # For template purposes, generate mock RSI values
    df["rsi"] = 45 + 10 * np.sin(np.arange(len(df)) * 0.1)  # Oscillates between 35-55

    return df


def apply_spyder_theme(fig: go.Figure) -> go.Figure:
    """Apply consistent Spyder theme to any Plotly figure."""
    fig.update_layout(**BASE_LAYOUT)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    """Example usage of chart templates."""
    # Generate sample data
    periods = 100
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=periods, freq="5T")

    np.random.seed(42)
    base_price = 585.0
    price_changes = np.random.normal(0, 0.5, periods).cumsum()

    sample_df = pd.DataFrame(
        {
            "datetime": dates,
            "open": base_price + price_changes,
            "high": base_price + price_changes + np.random.exponential(0.2, periods),
            "low": base_price + price_changes - np.random.exponential(0.2, periods),
            "close": base_price + price_changes + np.random.normal(0, 0.3, periods),
            "volume": np.random.normal(2000000, 500000, periods).astype(int),
        }
    )

    # Calculate indicators
    sample_df = calculate_technical_indicators(sample_df)

    # Create example charts
    candlestick_chart = CandlestickChartTemplate.create_advanced_candlestick(
        sample_df,
        "SPY",
        indicators={"sma_20": True, "sma_50": True, "vwap": True, "volume": True},
    )

