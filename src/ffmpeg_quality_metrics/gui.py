#!/usr/bin/env python3
#
# ffmpeg-quality-metrics GUI
# Author: Werner Robitza
# License: MIT

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import click
    import plotly.colors
    import plotly.graph_objects as go
    from dash import Dash, Input, Output, dash_table, dcc, html
except ImportError:
    raise ImportError(
        "GUI dependencies not installed. Install with: pip install 'ffmpeg-quality-metrics[gui]'"
    )

logger = logging.getLogger("ffmpeg-quality-metrics")


class MetricsData:
    """Container for parsed metrics data"""

    def __init__(
        self,
        metrics: Dict[str, List[Dict[str, float]]],
        global_stats: Optional[Dict[str, Any]] = None,
        input_file_dist: Optional[str] = None,
        input_file_ref: Optional[str] = None,
        framerate: Optional[float] = None,
    ):
        self.metrics = metrics
        self.global_stats = global_stats or {}
        self.input_file_dist = input_file_dist
        self.input_file_ref = input_file_ref
        self.framerate = framerate

    @property
    def metric_names(self) -> List[str]:
        """Get list of available metrics"""
        return [k for k in self.metrics.keys() if self.metrics[k]]

    def get_frame_numbers(self) -> List[int]:
        """Get list of all frame numbers"""
        # Get from the first available metric
        for metric_data in self.metrics.values():
            if metric_data:
                return [int(frame["n"]) for frame in metric_data]
        return []

    def get_time_values(self) -> List[float]:
        """Calculate time values from frame numbers and framerate"""
        if not self.framerate:
            return []
        frame_numbers = self.get_frame_numbers()
        return [float(n - 1) / self.framerate for n in frame_numbers]


def load_json_data(file_path: str) -> MetricsData:
    """Load metrics from JSON file"""
    with open(file_path, "r") as f:
        data = json.load(f)

    # Extract metrics (exclude special keys)
    metrics = {}
    for key in ["psnr", "ssim", "vmaf", "vif", "msad"]:
        if key in data and data[key]:
            metrics[key] = data[key]

    return MetricsData(
        metrics=metrics,
        global_stats=data.get("global", {}),
        input_file_dist=data.get("input_file_dist"),
        input_file_ref=data.get("input_file_ref"),
        framerate=None,  # Not stored in JSON
    )


def load_csv_data(file_path: str) -> MetricsData:
    """Load metrics from CSV file"""
    with open(file_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("CSV file is empty")

    # Extract file paths from first row
    input_file_dist = rows[0].get("input_file_dist")
    input_file_ref = rows[0].get("input_file_ref")

    # Identify metrics by column prefixes
    metrics: Dict[str, List[Dict[str, float]]] = {
        "psnr": [],
        "ssim": [],
        "vmaf": [],
        "vif": [],
        "msad": [],
    }

    # Group columns by metric
    metric_columns: Dict[str, List[str]] = {
        "psnr": [],
        "ssim": [],
        "vmaf": [],
        "vif": [],
        "msad": [],
    }

    for col in rows[0].keys():
        if col in ["n", "input_file_dist", "input_file_ref"]:
            continue
        # Determine metric from column name
        for metric in ["psnr", "ssim", "vmaf", "vif", "msad"]:
            if col.startswith(metric) or col.startswith(
                metric.replace("vmaf", "integer_")
            ):
                metric_columns[metric].append(col)
                break

    # Convert rows to metric-specific lists
    for row in rows:
        n = int(row["n"])
        for metric, cols in metric_columns.items():
            if cols:  # Only if metric has columns
                frame_data: Dict[str, float] = {"n": float(n)}
                for col in cols:
                    value = row.get(col, "")
                    if value:
                        try:
                            frame_data[col] = float(value)
                        except ValueError:
                            pass
                if len(frame_data) > 1:  # More than just 'n'
                    metrics[metric].append(frame_data)

    # Remove empty metrics
    metrics = {k: v for k, v in metrics.items() if v}

    return MetricsData(
        metrics=metrics,
        global_stats={},  # Not available in CSV
        input_file_dist=input_file_dist,
        input_file_ref=input_file_ref,
        framerate=None,  # Not stored in CSV
    )


def load_metrics_file(file_path: str, framerate: Optional[float] = None) -> MetricsData:
    """Load metrics from JSON or CSV file"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() == ".json":
        data = load_json_data(file_path)
    elif path.suffix.lower() == ".csv":
        data = load_csv_data(file_path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    # Set framerate if provided
    if framerate:
        data.framerate = framerate

    return data


def create_overview_tab(data: MetricsData, x_values: List, x_label: str) -> html.Div:
    """Create overview tab with primary metrics - separate chart for each metric"""
    plots = []
    colors = plotly.colors.qualitative.Plotly

    # PSNR chart
    if "psnr" in data.metrics and data.metrics["psnr"]:
        psnr_avg = [frame.get("psnr_avg", None) for frame in data.metrics["psnr"]]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=psnr_avg,
                name="PSNR (avg)",
                mode="lines",
                line=dict(color=colors[0 % len(colors)]),
            )
        )
        fig.update_layout(
            title="PSNR Average",
            xaxis_title=x_label,
            yaxis_title="PSNR (dB)",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    # SSIM chart
    if "ssim" in data.metrics and data.metrics["ssim"]:
        # SSIM is 0-1, scale to 0-100 for better visualization
        ssim_avg = [
            frame.get("ssim_avg", 0.0) * 100
            if frame.get("ssim_avg") is not None
            else None
            for frame in data.metrics["ssim"]
        ]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=ssim_avg,
                name="SSIM (avg)",
                mode="lines",
                line=dict(color=colors[1 % len(colors)]),
            )
        )
        fig.update_layout(
            title="SSIM Average × 100",
            xaxis_title=x_label,
            yaxis_title="SSIM × 100",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    # VMAF chart
    if "vmaf" in data.metrics and data.metrics["vmaf"]:
        vmaf_scores = [frame.get("vmaf", None) for frame in data.metrics["vmaf"]]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=vmaf_scores,
                name="VMAF",
                mode="lines",
                line=dict(color=colors[2 % len(colors)]),
            )
        )
        fig.update_layout(
            title="VMAF",
            xaxis_title=x_label,
            yaxis_title="VMAF Score",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    if not plots:
        return html.Div("No metrics data available")

    return html.Div(plots)


def create_components_tab(data: MetricsData, x_values: List, x_label: str) -> html.Div:
    """Create per-component tab with Y/U/V breakdowns"""
    plots = []

    colors = plotly.colors.qualitative.Plotly

    # PSNR components
    if "psnr" in data.metrics and data.metrics["psnr"]:
        fig = go.Figure()
        for idx, component in enumerate(["psnr_y", "psnr_u", "psnr_v"]):
            values = [frame.get(component, None) for frame in data.metrics["psnr"]]
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=values,
                    name=component.upper(),
                    mode="lines",
                    line=dict(color=colors[idx % len(colors)]),
                )
            )
        fig.update_layout(
            title="PSNR Components (Y/U/V)",
            xaxis_title=x_label,
            yaxis_title="PSNR (dB)",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    # SSIM components
    if "ssim" in data.metrics and data.metrics["ssim"]:
        fig = go.Figure()
        for idx, component in enumerate(["ssim_y", "ssim_u", "ssim_v"]):
            values = [
                frame.get(component, 0.0) * 100
                if frame.get(component) is not None
                else None
                for frame in data.metrics["ssim"]
            ]
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=values,
                    name=component.upper(),
                    mode="lines",
                    line=dict(color=colors[idx % len(colors)]),
                )
            )
        fig.update_layout(
            title="SSIM Components (Y/U/V) × 100",
            xaxis_title=x_label,
            yaxis_title="SSIM × 100",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    # VIF scales
    if "vif" in data.metrics and data.metrics["vif"]:
        fig = go.Figure()
        for idx, scale in enumerate(["scale_0", "scale_1", "scale_2", "scale_3"]):
            values = [frame.get(scale, None) for frame in data.metrics["vif"]]
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=values,
                    name=f"Scale {idx}",
                    mode="lines",
                    line=dict(color=colors[idx % len(colors)]),
                )
            )
        fig.update_layout(
            title="VIF Scales",
            xaxis_title=x_label,
            yaxis_title="VIF Score",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    if not plots:
        return html.Div("No component data available")

    return html.Div(plots)


def create_distribution_tab(data: MetricsData) -> html.Div:
    """Create distribution tab with histograms and box plots"""
    plots = []

    colors = plotly.colors.qualitative.Plotly

    # Create box plots for main metrics
    box_data = []
    color_idx = 0

    if "psnr" in data.metrics and data.metrics["psnr"]:
        psnr_avg = [frame.get("psnr_avg", None) for frame in data.metrics["psnr"]]
        psnr_avg = [v for v in psnr_avg if v is not None]
        if psnr_avg:
            box_data.append(
                go.Box(
                    y=psnr_avg,
                    name="PSNR (avg)",
                    marker_color=colors[color_idx % len(colors)],
                )
            )
            color_idx += 1

    if "ssim" in data.metrics and data.metrics["ssim"]:
        ssim_avg = [
            frame.get("ssim_avg", 0.0) * 100
            if frame.get("ssim_avg") is not None
            else None
            for frame in data.metrics["ssim"]
        ]
        ssim_avg = [v for v in ssim_avg if v is not None]
        if ssim_avg:
            box_data.append(
                go.Box(
                    y=ssim_avg,
                    name="SSIM (avg) × 100",
                    marker_color=colors[color_idx % len(colors)],
                )
            )
            color_idx += 1

    if "vmaf" in data.metrics and data.metrics["vmaf"]:
        vmaf_scores = [frame.get("vmaf", None) for frame in data.metrics["vmaf"]]
        vmaf_scores = [v for v in vmaf_scores if v is not None]
        if vmaf_scores:
            box_data.append(
                go.Box(
                    y=vmaf_scores,
                    name="VMAF",
                    marker_color=colors[color_idx % len(colors)],
                )
            )
            color_idx += 1

    if box_data:
        fig = go.Figure(data=box_data)
        fig.update_layout(
            title="Metric Distributions",
            yaxis_title="Score",
            template="plotly_white",
            height=500,
            showlegend=False,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    if not plots:
        return html.Div("No distribution data available")

    return html.Div(plots)


def create_statistics_tab(data: MetricsData) -> html.Div:
    """Create statistics tab with styled table view"""
    if not data.global_stats:
        return html.Div(
            "No global statistics available (statistics are only available for JSON output)",
            style={"padding": "20px", "fontFamily": "sans-serif"},
        )

    tables = []

    # CSS for styled tables
    table_header_style = {
        "backgroundColor": "#2c3e50",
        "color": "white",
        "padding": "12px",
        "textAlign": "right",
        "fontWeight": "bold",
        "borderBottom": "2px solid #34495e",
    }

    table_header_first_style = {
        **table_header_style,
        "textAlign": "left",
    }

    for metric_name, metric_stats in data.global_stats.items():
        rows = []
        # Header row
        rows.append(
            html.Tr(
                [
                    html.Th("Submetric", style=table_header_first_style),
                    html.Th("Average", style=table_header_style),
                    html.Th("Median", style=table_header_style),
                    html.Th("Std Dev", style=table_header_style),
                    html.Th("Min", style=table_header_style),
                    html.Th("Max", style=table_header_style),
                ],
                style={"backgroundColor": "#2c3e50"},
            )
        )

        # Data rows with banding
        for idx, (submetric, stats) in enumerate(metric_stats.items()):
            row_color = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
            cell_style = {
                "padding": "10px 12px",
                "textAlign": "right",
                "borderBottom": "1px solid #dee2e6",
            }
            first_cell_style = {**cell_style, "textAlign": "left", "fontWeight": "500"}

            rows.append(
                html.Tr(
                    [
                        html.Td(submetric, style=first_cell_style),
                        html.Td(f"{stats.get('average', 0):.3f}", style=cell_style),
                        html.Td(f"{stats.get('median', 0):.3f}", style=cell_style),
                        html.Td(f"{stats.get('stdev', 0):.3f}", style=cell_style),
                        html.Td(f"{stats.get('min', 0):.3f}", style=cell_style),
                        html.Td(f"{stats.get('max', 0):.3f}", style=cell_style),
                    ],
                    style={"backgroundColor": row_color},
                )
            )

        table = html.Div(
            [
                html.H3(
                    metric_name.upper(),
                    style={
                        "color": "#2c3e50",
                        "marginBottom": "15px",
                        "fontFamily": "sans-serif",
                    },
                ),
                html.Table(
                    rows,
                    style={
                        "width": "100%",
                        "borderCollapse": "collapse",
                        "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                        "borderRadius": "8px",
                        "overflow": "hidden",
                        "fontFamily": "sans-serif",
                    },
                ),
                html.Br(),
                html.Br(),
            ]
        )
        tables.append(table)

    return html.Div(
        tables,
        style={
            "fontFamily": "sans-serif",
            "padding": "20px",
        },
    )


def create_data_table_tab(data: MetricsData) -> html.Div:
    """Create filterable data table with all per-frame metrics"""
    # Combine all metrics into a single table
    frame_numbers = data.get_frame_numbers()
    if not frame_numbers:
        return html.Div(
            "No data available",
            style={"padding": "20px", "fontFamily": "sans-serif"},
        )

    # Build data records
    table_data = []
    for frame_num in frame_numbers:
        row: Dict[str, Any] = {"frame": frame_num}

        # Add data from each metric
        for metric_name, metric_frames in data.metrics.items():
            if metric_frames:
                # Find the matching frame
                for frame_data in metric_frames:
                    if int(frame_data.get("n", -1)) == frame_num:
                        # Add all fields from this metric
                        for key, value in frame_data.items():
                            if key != "n":  # Skip frame number
                                # Prefix with metric name to avoid collisions
                                col_name = f"{metric_name}_{key}"
                                if isinstance(value, float):
                                    row[col_name] = round(value, 3)
                                else:
                                    row[col_name] = value
                        break

        table_data.append(row)

    # Get all column names
    if not table_data:
        return html.Div(
            "No data available",
            style={"padding": "20px", "fontFamily": "sans-serif"},
        )

    all_columns = list(table_data[0].keys())

    # Create column definitions for dash_table (store all columns)
    all_column_defs = [
        {
            "name": col,
            "id": col,
            "type": "numeric" if col != "frame" else "numeric",
        }
        for col in all_columns
    ]

    # Build metric filter checkboxes
    available_metrics = [m.upper() for m in data.metric_names]

    metric_filter = html.Div(
        [
            html.Label(
                "Show Metrics:",
                style={
                    "fontWeight": "bold",
                    "marginRight": "15px",
                    "fontFamily": "sans-serif",
                },
            ),
            dcc.Checklist(
                id="metric-filter",
                options=[
                    {"label": metric, "value": metric.lower()}
                    for metric in available_metrics
                ],
                value=[m.lower() for m in data.metric_names],  # All selected by default
                inline=True,
                style={"fontFamily": "sans-serif"},
                labelStyle={"marginRight": "20px", "display": "inline-block"},
            ),
        ],
        style={
            "padding": "15px",
            "backgroundColor": "#f8f9fa",
            "borderRadius": "5px",
            "marginBottom": "20px",
        },
    )

    return html.Div(
        [
            html.H3(
                "Per-Frame Data Table",
                style={
                    "color": "#2c3e50",
                    "marginBottom": "15px",
                    "fontFamily": "sans-serif",
                },
            ),
            html.P(
                "Filter, sort, and export frame-by-frame metrics. Use checkboxes to show/hide metrics. Click column headers to sort.",
                style={
                    "color": "#666",
                    "fontFamily": "sans-serif",
                    "marginBottom": "15px",
                },
            ),
            metric_filter,
            dash_table.DataTable(
                id="data-table",
                columns=all_column_defs,  # Will be filtered by callback
                data=table_data,
                filter_action="native",
                sort_action="native",
                sort_mode="multi",
                page_action="native",
                page_current=0,
                page_size=50,
                export_format="csv",
                export_headers="display",
                style_table={
                    "overflowX": "auto",
                    "fontFamily": "sans-serif",
                },
                style_header={
                    "backgroundColor": "#2c3e50",
                    "color": "white",
                    "fontWeight": "bold",
                    "textAlign": "right",
                    "padding": "12px",
                    "borderBottom": "2px solid #34495e",
                },
                style_cell={
                    "textAlign": "right",
                    "padding": "10px 12px",
                    "fontFamily": "sans-serif",
                    "fontSize": "14px",
                },
                style_cell_conditional=[
                    {
                        "if": {"column_id": "frame"},
                        "textAlign": "left",
                        "fontWeight": "500",
                    }
                ],
                style_data_conditional=[
                    {
                        "if": {"row_index": "odd"},
                        "backgroundColor": "#f8f9fa",
                    },
                    {
                        "if": {"row_index": "even"},
                        "backgroundColor": "#ffffff",
                    },
                ],
                style_filter={
                    "backgroundColor": "#ecf0f1",
                    "fontFamily": "sans-serif",
                },
            ),
        ],
        style={"padding": "20px"},
    )


def create_app(data: MetricsData) -> Dash:
    """Create Dash application"""
    app = Dash(__name__, suppress_callback_exceptions=True)

    # File info section - styled as cards
    file_info = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                "Distorted:",
                                style={
                                    "fontWeight": "bold",
                                    "color": "#2c3e50",
                                    "marginRight": "10px",
                                },
                            ),
                            html.Span(
                                data.input_file_dist or "N/A",
                                style={"color": "#555", "fontFamily": "monospace"},
                            ),
                        ],
                        style={"marginBottom": "10px"},
                    ),
                    html.Div(
                        [
                            html.Span(
                                "Reference:",
                                style={
                                    "fontWeight": "bold",
                                    "color": "#2c3e50",
                                    "marginRight": "10px",
                                },
                            ),
                            html.Span(
                                data.input_file_ref or "N/A",
                                style={"color": "#555", "fontFamily": "monospace"},
                            ),
                        ],
                        style={"marginBottom": "10px"},
                    ),
                    html.Div(
                        [
                            html.Span(
                                "Frame Rate:",
                                style={
                                    "fontWeight": "bold",
                                    "color": "#2c3e50",
                                    "marginRight": "10px",
                                },
                            ),
                            html.Span(
                                f"{data.framerate:.2f} fps"
                                if data.framerate
                                else "Not available (using frame numbers only)",
                                style={"color": "#555"},
                            ),
                        ],
                    ),
                ],
                style={
                    "padding": "20px",
                    "backgroundColor": "#ffffff",
                    "borderLeft": "4px solid #3498db",
                    "borderRadius": "5px",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                    "margin": "20px",
                },
            ),
        ],
    )

    # X-axis selector (in main layout for callback compatibility)
    x_axis_selector = html.Div(
        [
            html.Label(
                "X-axis: ",
                style={
                    "fontWeight": "bold",
                    "marginRight": "10px",
                    "fontFamily": "sans-serif",
                },
            ),
            dcc.RadioItems(
                id="x-axis-selector",
                options=[
                    {"label": "Frame Number", "value": "frame"},
                    {
                        "label": "Time (seconds)",
                        "value": "time",
                        "disabled": not data.framerate,
                    },
                ],
                value="frame",
                inline=True,
                style={"fontFamily": "sans-serif"},
                labelStyle={"marginRight": "15px"},
            ),
        ],
        id="x-axis-container",
        style={
            "padding": "15px",
            "backgroundColor": "#f8f9fa",
            "borderRadius": "5px",
            "margin": "0 20px 20px 20px",
            "display": "block",  # Will be toggled by callback
        },
    )

    # Create tabs
    tabs = dcc.Tabs(
        id="tabs",
        value="overview",
        children=[
            dcc.Tab(label="Overview", value="overview"),
            dcc.Tab(label="Components", value="components"),
            dcc.Tab(label="Distributions", value="distributions"),
            dcc.Tab(label="Statistics", value="statistics"),
            dcc.Tab(label="Data Table", value="data_table"),
        ],
    )

    # Layout
    app.layout = html.Div(
        [
            html.H1(
                "FFmpeg Quality Metrics Dashboard",
                style={
                    "textAlign": "center",
                    "padding": "20px",
                    "fontFamily": "sans-serif",
                },
            ),
            file_info,
            tabs,
            x_axis_selector,
            html.Div(id="tab-content", style={"padding": "20px"}),
        ],
        style={"fontFamily": "sans-serif"},
    )

    # Callbacks
    @app.callback(
        Output("tab-content", "children"),
        [Input("tabs", "value"), Input("x-axis-selector", "value")],
    )
    def render_content(tab: str, x_axis: str = "frame"):  # type: ignore
        # Default to frame if x_axis is None (initial render)
        if x_axis is None:
            x_axis = "frame"

        # Determine x values and label
        x_values: List
        if x_axis == "time" and data.framerate:
            x_values = data.get_time_values()
            x_label = "Time (seconds)"
        else:
            x_values = data.get_frame_numbers()
            x_label = "Frame Number"

        if tab == "overview":
            return create_overview_tab(data, x_values, x_label)
        elif tab == "components":
            return create_components_tab(data, x_values, x_label)
        elif tab == "distributions":
            return create_distribution_tab(data)
        elif tab == "statistics":
            return create_statistics_tab(data)
        elif tab == "data_table":
            return create_data_table_tab(data)

    # Callback to show/hide x-axis selector based on active tab
    @app.callback(
        Output("x-axis-container", "style"),
        [Input("tabs", "value")],
    )
    def toggle_x_axis_selector(tab: str):  # type: ignore
        # Show x-axis selector only for tabs that use time-series data
        base_style = {
            "padding": "15px",
            "backgroundColor": "#f8f9fa",
            "borderRadius": "5px",
            "margin": "0 20px 20px 20px",
        }
        if tab in ["overview", "components"]:
            return {**base_style, "display": "block"}
        else:
            return {**base_style, "display": "none"}

    # Callback for filtering table columns based on metric selection
    @app.callback(
        Output("data-table", "columns"),
        [Input("metric-filter", "value")],
    )
    def update_table_columns(selected_metrics: Optional[List[str]] = None):  # type: ignore
        # Default to all metrics if None
        if selected_metrics is None:
            selected_metrics = [m.lower() for m in data.metric_names]

        # Get all frame data to determine column structure
        frame_numbers = data.get_frame_numbers()
        if not frame_numbers:
            return []

        # Build a sample row to get all columns
        sample_row: Dict[str, Any] = {"frame": frame_numbers[0]}
        for metric_name, metric_frames in data.metrics.items():
            if metric_frames and metric_frames:
                frame_data = metric_frames[0]
                for key, value in frame_data.items():
                    if key != "n":
                        col_name = f"{metric_name}_{key}"
                        sample_row[col_name] = value

        all_columns = list(sample_row.keys())

        # Filter columns based on selected metrics
        if not selected_metrics:
            # If nothing selected, show only frame column
            filtered_columns = ["frame"]
        else:
            filtered_columns = ["frame"]  # Always include frame
            for col in all_columns:
                if col == "frame":
                    continue
                # Check if column belongs to any selected metric
                for metric in selected_metrics:
                    if col.startswith(f"{metric}_"):
                        filtered_columns.append(col)
                        break

        # Create column definitions for filtered columns
        return [
            {
                "name": col,
                "id": col,
                "type": "numeric",
            }
            for col in filtered_columns
        ]

    return app


def run_dashboard(
    data: MetricsData,
    host: str = "127.0.0.1",
    port: int = 8050,
    debug: bool = False,
) -> None:
    """Run the Dash dashboard"""
    import sys

    # Monkey patch click.echo to redirect Flask's startup messages to stderr
    _original_echo = click.echo

    def echo_to_stderr(*args, **kwargs):
        kwargs["err"] = True
        _original_echo(*args, **kwargs)

    click.echo = echo_to_stderr

    # Configure logging to use stderr for werkzeug and dash
    werkzeug_logger = logging.getLogger("werkzeug")
    dash_logger = logging.getLogger("dash")

    # Remove any existing handlers that might write to stdout
    for logger_obj in [werkzeug_logger, dash_logger]:
        logger_obj.handlers.clear()
        stderr_handler = logging.StreamHandler(sys.stderr)
        logger_obj.addHandler(stderr_handler)
        logger_obj.setLevel(logging.INFO)
        logger_obj.propagate = False  # Don't propagate to root logger

    # Temporarily redirect stdout to stderr to catch Dash's startup message
    _original_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        app = create_app(data)
        # Restore stdout before running the server
        # (the server should continue to use our configured loggers)
        sys.stdout = _original_stdout
        app.run(host=host, port=port, debug=debug)
    finally:
        # Restore original click.echo and stdout
        sys.stdout = _original_stdout
        click.echo = _original_echo
