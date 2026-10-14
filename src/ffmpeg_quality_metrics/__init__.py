import importlib.metadata

from .ffmpeg_quality_metrics import (
    FfmpegQualityMetrics,
    FfmpegQualityMetricsError,
    GlobalStats,
    GlobalStatsData,
    InputInfo,
    MetricData,
    MetricName,
    SingleMetricData,
    VmafOptions,
)

__version__ = importlib.metadata.version("ffmpeg-quality-metrics")
__all__ = [
    "FfmpegQualityMetrics",
    "FfmpegQualityMetricsError",
    "VmafOptions",
    "MetricName",
    "SingleMetricData",
    "GlobalStatsData",
    "GlobalStats",
    "MetricData",
    "InputInfo",
    "__version__",
]
