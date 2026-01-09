"""
Statistical Utilities for Metrics Analysis

Provides p95 percentile-based outlier filtering for time-series data.
Part of MetricsAnalysisAgent enhancement (FR-011).
"""

import numpy as np
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def filter_outliers_p95(data_points: List[float]) -> Tuple[List[float], List[float]]:
    """
    Filter outliers using p95 percentile threshold.
    
    Removes the top 5% of data points (above 95th percentile) to reduce noise
    from transient spikes while preserving genuine trend signals.
    
    Args:
        data_points: List of metric values to filter
    
    Returns:
        Tuple of (filtered_data, outliers):
            - filtered_data: Values at or below p95 threshold
            - outliers: Values above p95 threshold (removed)
    
    Example:
        >>> data = [1.0, 2.0, 3.0, 100.0]  # 100.0 is outlier
        >>> filtered, outliers = filter_outliers_p95(data)
        >>> filtered
        [1.0, 2.0, 3.0]
        >>> outliers
        [100.0]
    """
    # Insufficient data for meaningful filtering
    if len(data_points) < 5:
        logger.debug(f"Insufficient data for p95 filtering: {len(data_points)} points")
        return data_points, []
    
    # Convert to numpy array for efficient computation
    arr = np.array(data_points)
    
    # Compute p95 threshold using linear interpolation
    p95_threshold = np.percentile(arr, 95)
    
    # Split into filtered data and outliers
    filtered = arr[arr <= p95_threshold].tolist()
    outliers = arr[arr > p95_threshold].tolist()
    
    if outliers:
        logger.info(
            f"p95 filtering: removed {len(outliers)} outliers "
            f"(threshold={p95_threshold:.2f}, max outlier={max(outliers):.2f})"
        )
    
    return filtered, outliers


def compute_linear_trend(data_points: List[float]) -> Tuple[float, float]:
    """
    Compute linear regression slope and R² for trend detection.
    
    Args:
        data_points: Time-series values (assumed evenly spaced)
    
    Returns:
        Tuple of (slope, r_squared):
            - slope: Linear regression slope (positive = increasing)
            - r_squared: Coefficient of determination (0-1, higher = better fit)
    
    Raises:
        ValueError: If less than 2 data points provided
    """
    if len(data_points) < 2:
        raise ValueError(f"Need at least 2 points for trend, got {len(data_points)}")
    
    # Create time index (0, 1, 2, ...)
    x = np.arange(len(data_points))
    y = np.array(data_points)
    
    # Linear regression using least squares
    coefficients = np.polyfit(x, y, deg=1)
    slope = coefficients[0]
    
    # Compute R² (coefficient of determination)
    y_pred = np.poly1d(coefficients)(x)
    ss_res = np.sum((y - y_pred) ** 2)  # Residual sum of squares
    ss_tot = np.sum((y - np.mean(y)) ** 2)  # Total sum of squares
    
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    
    return float(slope), float(r_squared)


def compute_variance_coefficient(data_points: List[float]) -> float:
    """
    Compute coefficient of variation (CV) for stability detection.
    
    CV = standard_deviation / mean
    Used to classify STABLE trends (low CV, typically < 0.10).
    
    Args:
        data_points: Time-series values
    
    Returns:
        Coefficient of variation (0.0 = perfectly stable, higher = more variable)
    
    Raises:
        ValueError: If less than 2 data points or mean is zero
    """
    if len(data_points) < 2:
        raise ValueError(f"Need at least 2 points for variance, got {len(data_points)}")
    
    arr = np.array(data_points)
    mean = np.mean(arr)
    
    if mean == 0:
        # Handle zero mean case (all values are zero)
        return 0.0 if np.std(arr) == 0 else float('inf')
    
    std_dev = np.std(arr)
    cv = std_dev / abs(mean)
    
    return float(cv)


def validate_data_points(data_points: List[float]) -> List[float]:
    """
    Validate and clean data points by removing NaN/Inf values.
    
    Args:
        data_points: Raw metric values
    
    Returns:
        Cleaned list with only finite values
    
    Logs:
        Warning if any invalid values removed
    """
    if not data_points:
        return []
    
    arr = np.array(data_points)
    valid_mask = np.isfinite(arr)
    valid_data = arr[valid_mask].tolist()
    
    invalid_count = len(data_points) - len(valid_data)
    if invalid_count > 0:
        logger.warning(
            f"Removed {invalid_count} invalid values (NaN/Inf) from data "
            f"({len(valid_data)}/{len(data_points)} valid)"
        )
    
    return valid_data
