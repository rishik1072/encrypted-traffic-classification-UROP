"""Preprocessing package initialization."""

from preprocessing.feature_extractor import FeatureExtractor

try:
    from preprocessing.preprocessing import FeaturePreprocessor
    __all__ = ["FeatureExtractor", "FeaturePreprocessor"]
except ImportError:
    __all__ = ["FeatureExtractor"]
