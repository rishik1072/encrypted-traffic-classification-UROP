"""
Real-time Feature Buffer and Incremental Feature Computation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
import pandas as pd
from flows.flow_generator import Flow
from preprocessing.feature_extractor import FeatureExtractor
from preprocessing.preprocessing import FeaturePreprocessor

logger = logging.getLogger(__name__)


class RealTimeFeaturePipeline:
    """
    Transforms live active Flow objects into scaled numerical vectors ready for low-latency inference.
    """

    def __init__(
        self,
        extractor: FeatureExtractor,
        preprocessor: FeaturePreprocessor,
    ) -> None:
        self.extractor = extractor
        self.preprocessor = preprocessor

    def extract_and_transform(self, flow: Flow) -> Any:
        """Extracts tabular features from flow and transforms them using fitted preprocessor."""
        raw_features: Dict[str, Any] = self.extractor.extract_features(flow)
        df = pd.DataFrame([raw_features])
        return self.preprocessor.transform(df)
