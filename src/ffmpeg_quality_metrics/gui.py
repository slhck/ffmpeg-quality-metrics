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

# Import plotly early for color palette
try:
    import plotly.colors
    import plotly.graph_objects as go
except ImportError:
    raise ImportError(
        "GUI dependencies not installed. Install with: pip install 'ffmpeg-quality-metrics[gui]'"
    )

logger = logging.getLogger("ffmpeg-quality-metrics")


class MetricsData:
    """Container for parsed metrics data from a single clip"""

    def __init__(
        self,
        metrics: Dict[str, List[Dict[str, float]]],
        global_stats: Optional[Dict[str, Any]] = None,
        input_file_dist: Optional[str] = None,
        input_file_ref: Optional[str] = None,
        framerate: Optional[float] = None,
        clip_name: Optional[str] = None,
    ):
        self.metrics = metrics
        self.global_stats = global_stats or {}
        self.input_file_dist = input_file_dist
        self.input_file_ref = input_file_ref
        self.framerate = framerate
        self.clip_name = clip_name or input_file_dist or "Unknown"

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


class MultiClipData:
    """Container for multiple clips for comparison"""

    def __init__(self, clips: List[MetricsData]):
        self.clips = clips
        self.colors = self._assign_colors()

    def _assign_colors(self) -> Dict[str, str]:
        """Assign consistent colors to each clip"""
        color_palette = plotly.colors.qualitative.Plotly
        return {
            clip.clip_name: color_palette[i % len(color_palette)]
            for i, clip in enumerate(self.clips)
        }

    @property
    def all_metric_names(self) -> List[str]:
        """Get union of all metrics across all clips"""
        all_metrics = set()
        for clip in self.clips:
            all_metrics.update(clip.metric_names)
        return sorted(all_metrics)

    def get_max_frame_count(self) -> int:
        """Get maximum frame count across all clips"""
        return max((len(clip.get_frame_numbers()) for clip in self.clips), default=0)


def load_json_data(file_path: str, clip_name: Optional[str] = None) -> MetricsData:
    """Load metrics from JSON file"""
    with open(file_path, "r") as f:
        data = json.load(f)

    # Extract metrics (exclude special keys)
    metrics = {}
    for key in ["psnr", "ssim", "vmaf", "vif", "msad"]:
        if key in data and data[key]:
            metrics[key] = data[key]

    # Use provided clip_name or fall back to basename of input_file_dist from JSON
    input_file_dist = data.get("input_file_dist")
    if clip_name:
        effective_clip_name = clip_name
    elif input_file_dist:
        effective_clip_name = Path(input_file_dist).name  # Use basename only
    else:
        effective_clip_name = Path(file_path).stem

    return MetricsData(
        metrics=metrics,
        global_stats=data.get("global", {}),
        input_file_dist=input_file_dist,
        input_file_ref=data.get("input_file_ref"),
        framerate=None,  # Not stored in JSON
        clip_name=effective_clip_name,
    )


def load_csv_data(file_path: str, clip_name: Optional[str] = None) -> MetricsData:
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

    # Use provided clip_name or fall back to basename of input_file_dist from CSV
    if clip_name:
        effective_clip_name = clip_name
    elif input_file_dist:
        effective_clip_name = Path(input_file_dist).name  # Use basename only
    else:
        effective_clip_name = Path(file_path).stem

    return MetricsData(
        metrics=metrics,
        global_stats={},  # Not available in CSV
        input_file_dist=input_file_dist,
        input_file_ref=input_file_ref,
        framerate=None,  # Not stored in CSV
        clip_name=effective_clip_name,
    )


def load_metrics_file(
    file_path: str, framerate: Optional[float] = None, clip_name: Optional[str] = None
) -> MetricsData:
    """Load metrics from JSON or CSV file"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if path.suffix.lower() == ".json":
        data = load_json_data(file_path, clip_name=clip_name)
    elif path.suffix.lower() == ".csv":
        data = load_csv_data(file_path, clip_name=clip_name)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    # Set framerate if provided
    if framerate:
        data.framerate = framerate

    return data


def load_multiple_metrics_files(
    file_paths: List[str], framerate: Optional[float] = None
) -> MultiClipData:
    """Load multiple metrics files for comparison"""
    clips = []
    for file_path in file_paths:
        clip_data = load_metrics_file(file_path, framerate=framerate)
        clips.append(clip_data)
    return MultiClipData(clips)


def create_overview_tab(
    data: MultiClipData, x_axis: str, selected_clips: Optional[List[str]] = None
):
    """Create overview tab with primary metrics - separate chart for each metric"""
    from dash import dcc, html

    plots = []

    # Filter clips based on selection
    if selected_clips is None:
        clips_to_show = data.clips
    else:
        clips_to_show = [c for c in data.clips if c.clip_name in selected_clips]

    if not clips_to_show:
        return html.Div("No clips selected")

    # PSNR chart
    psnr_fig = go.Figure()
    has_psnr = False
    for clip in clips_to_show:
        if "psnr" in clip.metrics and clip.metrics["psnr"]:
            x_values = (
                clip.get_time_values()
                if x_axis == "time" and clip.framerate
                else clip.get_frame_numbers()
            )
            psnr_avg = [frame.get("psnr_avg", None) for frame in clip.metrics["psnr"]]
            psnr_fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=psnr_avg,
                    name=clip.clip_name,
                    mode="lines",
                    line=dict(color=data.colors[clip.clip_name]),
                )
            )
            has_psnr = True

    if has_psnr:
        x_label = "Time (seconds)" if x_axis == "time" else "Frame Number"
        psnr_fig.update_layout(
            title="PSNR Average",
            xaxis_title=x_label,
            yaxis_title="PSNR (dB)",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=psnr_fig, config={"displayModeBar": True}))

    # SSIM chart
    ssim_fig = go.Figure()
    has_ssim = False
    for clip in clips_to_show:
        if "ssim" in clip.metrics and clip.metrics["ssim"]:
            x_values = (
                clip.get_time_values()
                if x_axis == "time" and clip.framerate
                else clip.get_frame_numbers()
            )
            ssim_avg = [
                frame.get("ssim_avg", 0.0) * 100
                if frame.get("ssim_avg") is not None
                else None
                for frame in clip.metrics["ssim"]
            ]
            ssim_fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=ssim_avg,
                    name=clip.clip_name,
                    mode="lines",
                    line=dict(color=data.colors[clip.clip_name]),
                )
            )
            has_ssim = True

    if has_ssim:
        x_label = "Time (seconds)" if x_axis == "time" else "Frame Number"
        ssim_fig.update_layout(
            title="SSIM Average × 100",
            xaxis_title=x_label,
            yaxis_title="SSIM × 100",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=ssim_fig, config={"displayModeBar": True}))

    # VMAF chart
    vmaf_fig = go.Figure()
    has_vmaf = False
    for clip in clips_to_show:
        if "vmaf" in clip.metrics and clip.metrics["vmaf"]:
            x_values = (
                clip.get_time_values()
                if x_axis == "time" and clip.framerate
                else clip.get_frame_numbers()
            )
            vmaf_scores = [frame.get("vmaf", None) for frame in clip.metrics["vmaf"]]
            vmaf_fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=vmaf_scores,
                    name=clip.clip_name,
                    mode="lines",
                    line=dict(color=data.colors[clip.clip_name]),
                )
            )
            has_vmaf = True

    if has_vmaf:
        x_label = "Time (seconds)" if x_axis == "time" else "Frame Number"
        vmaf_fig.update_layout(
            title="VMAF",
            xaxis_title=x_label,
            yaxis_title="VMAF Score",
            hovermode="x unified",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=vmaf_fig, config={"displayModeBar": True}))

    if not plots:
        return html.Div("No metrics data available for selected clips")

    return html.Div(plots)


def create_components_tab(
    data: MultiClipData, x_axis: str, selected_clips: Optional[List[str]] = None
):
    """Create per-component tab with Y/U/V breakdowns - one chart per clip"""
    from dash import dcc, html

    plots = []

    # Filter clips based on selection
    if selected_clips is None:
        clips_to_show = data.clips
    else:
        clips_to_show = [c for c in data.clips if c.clip_name in selected_clips]

    if not clips_to_show:
        return html.Div("No clips selected")

    # Line styles for components
    line_styles = ["solid", "dash", "dot"]

    # For each clip, create a section with its component charts
    for clip in clips_to_show:
        clip_plots = []
        x_values = (
            clip.get_time_values()
            if x_axis == "time" and clip.framerate
            else clip.get_frame_numbers()
        )
        x_label = "Time (seconds)" if x_axis == "time" else "Frame Number"
        clip_color = data.colors[clip.clip_name]

        # PSNR components for this clip
        if "psnr" in clip.metrics and clip.metrics["psnr"]:
            fig = go.Figure()
            for idx, component in enumerate(["psnr_y", "psnr_u", "psnr_v"]):
                values = [frame.get(component, None) for frame in clip.metrics["psnr"]]
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=values,
                        name=component.upper(),
                        mode="lines",
                        line=dict(color=clip_color, dash=line_styles[idx]),
                    )
                )
            fig.update_layout(
                title=f"PSNR Components (Y/U/V) - {clip.clip_name}",
                xaxis_title=x_label,
                yaxis_title="PSNR (dB)",
                hovermode="x unified",
                template="plotly_white",
                height=400,
                font=dict(family="sans-serif"),
            )
            clip_plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

        # SSIM components for this clip
        if "ssim" in clip.metrics and clip.metrics["ssim"]:
            fig = go.Figure()
            for idx, component in enumerate(["ssim_y", "ssim_u", "ssim_v"]):
                values = [
                    frame.get(component, 0.0) * 100
                    if frame.get(component) is not None
                    else None
                    for frame in clip.metrics["ssim"]
                ]
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=values,
                        name=component.upper(),
                        mode="lines",
                        line=dict(color=clip_color, dash=line_styles[idx]),
                    )
                )
            fig.update_layout(
                title=f"SSIM Components (Y/U/V) × 100 - {clip.clip_name}",
                xaxis_title=x_label,
                yaxis_title="SSIM × 100",
                hovermode="x unified",
                template="plotly_white",
                height=400,
                font=dict(family="sans-serif"),
            )
            clip_plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

        # VIF scales for this clip
        if "vif" in clip.metrics and clip.metrics["vif"]:
            fig = go.Figure()
            for idx, scale in enumerate(["scale_0", "scale_1", "scale_2", "scale_3"]):
                values = [frame.get(scale, None) for frame in clip.metrics["vif"]]
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=values,
                        name=f"Scale {idx}",
                        mode="lines",
                        line=dict(color=clip_color, dash=line_styles[idx % 3]),
                    )
                )
            fig.update_layout(
                title=f"VIF Scales - {clip.clip_name}",
                xaxis_title=x_label,
                yaxis_title="VIF Score",
                hovermode="x unified",
                template="plotly_white",
                height=400,
                font=dict(family="sans-serif"),
            )
            clip_plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

        if clip_plots:
            plots.extend(clip_plots)

    if not plots:
        return html.Div("No component data available for selected clips")

    return html.Div(plots)


def create_distribution_tab(
    data: MultiClipData, selected_clips: Optional[List[str]] = None
):
    """Create distribution tab with grouped box plots for clip comparison"""
    from dash import dcc, html

    plots = []

    # Filter clips based on selection
    if selected_clips is None:
        clips_to_show = data.clips
    else:
        clips_to_show = [c for c in data.clips if c.clip_name in selected_clips]

    if not clips_to_show:
        return html.Div("No clips selected")

    # Create separate grouped box plots for each metric
    # PSNR
    psnr_boxes = []
    for clip in clips_to_show:
        if "psnr" in clip.metrics and clip.metrics["psnr"]:
            psnr_avg = [frame.get("psnr_avg", None) for frame in clip.metrics["psnr"]]
            psnr_avg = [v for v in psnr_avg if v is not None]
            if psnr_avg:
                psnr_boxes.append(
                    go.Box(
                        y=psnr_avg,
                        name=clip.clip_name,
                        marker_color=data.colors[clip.clip_name],
                    )
                )

    if psnr_boxes:
        fig = go.Figure(data=psnr_boxes)
        fig.update_layout(
            title="PSNR Distribution by Clip",
            yaxis_title="PSNR (dB)",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    # SSIM
    ssim_boxes = []
    for clip in clips_to_show:
        if "ssim" in clip.metrics and clip.metrics["ssim"]:
            ssim_avg = [
                frame.get("ssim_avg", 0.0) * 100
                if frame.get("ssim_avg") is not None
                else None
                for frame in clip.metrics["ssim"]
            ]
            ssim_avg = [v for v in ssim_avg if v is not None]
            if ssim_avg:
                ssim_boxes.append(
                    go.Box(
                        y=ssim_avg,
                        name=clip.clip_name,
                        marker_color=data.colors[clip.clip_name],
                    )
                )

    if ssim_boxes:
        fig = go.Figure(data=ssim_boxes)
        fig.update_layout(
            title="SSIM Distribution by Clip",
            yaxis_title="SSIM × 100",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    # VMAF
    vmaf_boxes = []
    for clip in clips_to_show:
        if "vmaf" in clip.metrics and clip.metrics["vmaf"]:
            vmaf_scores = [frame.get("vmaf", None) for frame in clip.metrics["vmaf"]]
            vmaf_scores = [v for v in vmaf_scores if v is not None]
            if vmaf_scores:
                vmaf_boxes.append(
                    go.Box(
                        y=vmaf_scores,
                        name=clip.clip_name,
                        marker_color=data.colors[clip.clip_name],
                    )
                )

    if vmaf_boxes:
        fig = go.Figure(data=vmaf_boxes)
        fig.update_layout(
            title="VMAF Distribution by Clip",
            yaxis_title="VMAF Score",
            template="plotly_white",
            height=400,
            font=dict(family="sans-serif"),
        )
        plots.append(dcc.Graph(figure=fig, config={"displayModeBar": True}))

    if not plots:
        return html.Div("No distribution data available for selected clips")

    return html.Div(plots)


def create_statistics_tab(
    data: MultiClipData, selected_clips: Optional[List[str]] = None
):
    """Create statistics tab with comparison table grouped by statistic type"""
    from dash import html

    # Filter clips based on selection
    if selected_clips is None:
        clips_to_show = data.clips
    else:
        clips_to_show = [c for c in data.clips if c.clip_name in selected_clips]

    if not clips_to_show:
        return html.Div("No clips selected")

    # Check if any clip has global stats
    has_stats = any(clip.global_stats for clip in clips_to_show)
    if not has_stats:
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

    # Collect all metrics across all clips
    all_metrics: set[str] = set()
    for clip in clips_to_show:
        all_metrics.update(clip.global_stats.keys())

    # For each metric, create a comparison table
    for metric_name in sorted(all_metrics):
        # Collect all submetrics across all clips for this metric
        all_submetrics = set()
        for clip in clips_to_show:
            if metric_name in clip.global_stats:
                all_submetrics.update(clip.global_stats[metric_name].keys())

        if not all_submetrics:
            continue

        # Build header row: Submetric | Avg (Clip1) | Avg (Clip2) | ... | Median (Clip1) | Median (Clip2) | ...
        stat_types = ["average", "median", "stdev", "min", "max"]
        header_cells = [html.Th("Submetric", style=table_header_first_style)]

        for stat_type in stat_types:
            for clip in clips_to_show:
                if metric_name in clip.global_stats:
                    header_cells.append(
                        html.Th(
                            f"{stat_type.capitalize()}\n({clip.clip_name})",
                            style={
                                **table_header_style,
                                "backgroundColor": data.colors[clip.clip_name],
                                "whiteSpace": "pre-line",
                            },
                        )
                    )

        rows = [html.Tr(header_cells, style={"backgroundColor": "#2c3e50"})]

        # Data rows
        for idx, submetric in enumerate(sorted(all_submetrics)):
            row_color = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
            cell_style = {
                "padding": "10px 12px",
                "textAlign": "right",
                "borderBottom": "1px solid #dee2e6",
            }
            first_cell_style = {**cell_style, "textAlign": "left", "fontWeight": "500"}

            row_cells = [html.Td(submetric, style=first_cell_style)]

            for stat_type in stat_types:
                for clip in clips_to_show:
                    if (
                        metric_name in clip.global_stats
                        and submetric in clip.global_stats[metric_name]
                    ):
                        value = clip.global_stats[metric_name][submetric].get(
                            stat_type, 0
                        )
                        row_cells.append(html.Td(f"{value:.3f}", style=cell_style))
                    else:
                        row_cells.append(html.Td("—", style=cell_style))

            rows.append(html.Tr(row_cells, style={"backgroundColor": row_color}))

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


def create_data_table_tab(
    data: MultiClipData, selected_clips: Optional[List[str]] = None
):
    """Create filterable data table with all per-frame metrics from all clips"""
    from dash import dcc, dash_table, html

    # Filter clips based on selection
    if selected_clips is None:
        clips_to_show = data.clips
    else:
        clips_to_show = [c for c in data.clips if c.clip_name in selected_clips]

    if not clips_to_show:
        return html.Div("No clips selected")

    # Build data records from all clips
    table_data = []
    for clip in clips_to_show:
        frame_numbers = clip.get_frame_numbers()
        for frame_num in frame_numbers:
            row: Dict[str, Any] = {"clip": clip.clip_name, "frame": frame_num}

            # Add data from each metric
            for metric_name, metric_frames in clip.metrics.items():
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
            "type": "text" if col == "clip" else "numeric",
        }
        for col in all_columns
    ]

    # Build filters
    available_metrics = list(data.all_metric_names)
    available_clips = [clip.clip_name for clip in data.clips]

    filters = html.Div(
        [
            html.Div(
                [
                    html.Label(
                        "Show Clips:",
                        style={
                            "fontWeight": "bold",
                            "marginRight": "15px",
                            "fontFamily": "sans-serif",
                        },
                    ),
                    dcc.Checklist(
                        id="clip-filter-table",
                        options=available_clips,
                        value=available_clips,  # All selected by default
                        inline=True,
                        style={"fontFamily": "sans-serif"},
                        labelStyle={"marginRight": "20px", "display": "inline-block"},
                    ),
                ],
                style={"marginBottom": "10px"},
            ),
            html.Div(
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
                        options=available_metrics,
                        value=available_metrics,  # All selected by default
                        inline=True,
                        style={"fontFamily": "sans-serif"},
                        labelStyle={"marginRight": "20px", "display": "inline-block"},
                    ),
                ],
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
            filters,
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
                    },
                    {
                        "if": {"column_id": "clip"},
                        "textAlign": "left",
                        "fontWeight": "500",
                    },
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


def create_app(data: MultiClipData):
    """Create Dash application for multi-clip comparison"""
    from dash import Dash, Input, Output, dcc, html

    app = Dash(__name__, suppress_callback_exceptions=True)

    # Clip info section - show all loaded clips with color indicators
    clip_cards = []
    for clip in data.clips:
        # Show full path in loaded clips section
        display_name = clip.input_file_dist if clip.input_file_dist else clip.clip_name

        clip_card = html.Div(
            [
                html.Div(
                    style={
                        "width": "20px",
                        "height": "20px",
                        "backgroundColor": data.colors[clip.clip_name],
                        "borderRadius": "50%",
                        "display": "inline-block",
                        "marginRight": "10px",
                        "verticalAlign": "middle",
                    }
                ),
                html.Span(
                    display_name,
                    style={
                        "fontWeight": "bold",
                        "color": "#2c3e50",
                        "marginRight": "15px",
                        "verticalAlign": "middle",
                    },
                ),
                html.Span(
                    f"({len(clip.get_frame_numbers())} frames)",
                    style={
                        "color": "#666",
                        "fontSize": "0.9em",
                        "verticalAlign": "middle",
                    },
                ),
            ],
            style={"marginBottom": "10px"},
        )
        clip_cards.append(clip_card)

    file_info = html.Div(
        [
            html.H3(
                f"Loaded Clips: {len(data.clips)}",
                style={
                    "color": "#2c3e50",
                    "marginBottom": "15px",
                    "fontFamily": "sans-serif",
                },
            ),
            html.Div(clip_cards),
        ],
        style={
            "padding": "20px",
            "backgroundColor": "#ffffff",
            "borderLeft": "4px solid #3498db",
            "borderRadius": "5px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
            "margin": "20px",
        },
    )

    # Clip selector for filtering visualizations
    clip_selector = html.Div(
        [
            html.Label(
                "Show Clips:",
                style={
                    "fontWeight": "bold",
                    "marginRight": "15px",
                    "fontFamily": "sans-serif",
                },
            ),
            dcc.Checklist(
                id="clip-selector",
                options=[clip.clip_name for clip in data.clips],
                value=[
                    clip.clip_name for clip in data.clips
                ],  # All selected by default
                inline=True,
                style={"fontFamily": "sans-serif"},
                labelStyle={"marginRight": "20px", "display": "inline-block"},
            ),
        ],
        style={
            "padding": "15px",
            "backgroundColor": "#f8f9fa",
            "borderRadius": "5px",
            "margin": "0 20px 20px 20px",
        },
    )

    # X-axis selector (in main layout for callback compatibility)
    # Check if any clip has framerate
    any_framerate = any(clip.framerate for clip in data.clips)
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
                        "disabled": not any_framerate,
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
    title_text = (
        "FFmpeg Quality Metrics Dashboard - Multi-Clip Comparison"
        if len(data.clips) > 1
        else "FFmpeg Quality Metrics Dashboard"
    )
    app.layout = html.Div(
        [
            html.H1(
                title_text,
                style={
                    "textAlign": "center",
                    "padding": "20px",
                    "fontFamily": "sans-serif",
                },
            ),
            file_info,
            clip_selector,
            tabs,
            x_axis_selector,
            html.Div(id="tab-content", style={"padding": "20px"}),
        ],
        style={"fontFamily": "sans-serif"},
    )

    # Callbacks
    @app.callback(
        Output("tab-content", "children"),
        [
            Input("tabs", "value"),
            Input("x-axis-selector", "value"),
            Input("clip-selector", "value"),
        ],
    )
    def render_content(
        tab: str, x_axis: str = "frame", selected_clips: Optional[List[str]] = None
    ):
        # Default to frame if x_axis is None (initial render)
        if x_axis is None:
            x_axis = "frame"

        if tab == "overview":
            return create_overview_tab(data, x_axis, selected_clips)
        elif tab == "components":
            return create_components_tab(data, x_axis, selected_clips)
        elif tab == "distributions":
            return create_distribution_tab(data, selected_clips)
        elif tab == "statistics":
            return create_statistics_tab(data, selected_clips)
        elif tab == "data_table":
            return create_data_table_tab(data, selected_clips)

    # Callback to show/hide x-axis selector based on active tab
    @app.callback(
        Output("x-axis-container", "style"),
        [Input("tabs", "value")],
    )
    def toggle_x_axis_selector(tab: str):
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

    # Callback for filtering table columns based on metric and clip selection
    @app.callback(
        Output("data-table", "columns"),
        [Input("metric-filter", "value"), Input("clip-filter-table", "value")],
    )
    def update_table_columns(
        selected_metrics: Optional[List[str]] = None,
        selected_clips: Optional[List[str]] = None,
    ):
        # Default to all if None
        if selected_metrics is None:
            selected_metrics = list(data.all_metric_names)
        if selected_clips is None:
            selected_clips = [clip.clip_name for clip in data.clips]

        # Build a sample row to get all columns
        sample_row: Dict[str, Any] = {"clip": "sample", "frame": 1}
        for clip in data.clips:
            for metric_name, metric_frames in clip.metrics.items():
                if metric_frames:
                    frame_data = metric_frames[0]
                    for key, value in frame_data.items():
                        if key != "n":
                            col_name = f"{metric_name}_{key}"
                            sample_row[col_name] = value
                    break
            if len(sample_row) > 2:  # Found some metrics
                break

        all_columns = list(sample_row.keys())

        # Filter columns based on selected metrics
        if not selected_metrics:
            # If nothing selected, show only clip and frame columns
            filtered_columns = ["clip", "frame"]
        else:
            filtered_columns = ["clip", "frame"]  # Always include clip and frame
            for col in all_columns:
                if col in ["clip", "frame"]:
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
                "type": "text" if col == "clip" else "numeric",
            }
            for col in filtered_columns
        ]

    return app


def run_dashboard(
    data: MultiClipData,
    host: str = "127.0.0.1",
    port: int = 8050,
    debug: bool = False,
) -> None:
    """Run the Dash dashboard for multi-clip comparison"""
    import sys
    import click

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
