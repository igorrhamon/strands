"""
Advanced Correlation Analysis - Lag Detection, Normalization, Bayesian Confidence

Implementa análise de correlação sofisticada com tratamento de defasagem temporal
e confiança estatística Bayesiana.
"""

import numpy as np
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from scipy import signal
from scipy.stats import pearsonr

logger = logging.getLogger(__name__)


class CorrelationSignificance(str, Enum):
    """Significância estatística da correlação."""
    VERY_SIGNIFICANT = "VERY_SIGNIFICANT"  # p < 0.01
    SIGNIFICANT = "SIGNIFICANT"            # p < 0.05
    WEAK = "WEAK"                          # p < 0.10
    NOT_SIGNIFICANT = "NOT_SIGNIFICANT"    # p >= 0.10


@dataclass
class CorrelationResult:
    """Resultado de análise de correlação."""
    correlation_coefficient: float
    p_value: float
    significance: CorrelationSignificance
    lag_offset: int
    confidence_score: float
    sample_count: int
    is_significant: bool
    details: Dict[str, Any]


class AdvancedCorrelationAnalyzer:
    """
    Analisador avançado de correlação com suporte a lag, normalização e significância.
    """
    
    def __init__(self, min_sample_size: int = 20):
        self.min_sample_size = min_sample_size
    
    def analyze_with_lag(
        self,
        series_1: List[float],
        series_2: List[float],
        max_lag: int = 5,
        normalize: bool = True
    ) -> CorrelationResult:
        """
        Analisa correlação entre duas séries com detecção de lag.
        
        Args:
            series_1: Primeira série temporal
            series_2: Segunda série temporal
            max_lag: Máximo lag a testar (em pontos)
            normalize: Se deve normalizar as séries
        
        Returns:
            CorrelationResult com lag detectado e confiança
        """
        # Validação
        if len(series_1) < self.min_sample_size or len(series_2) < self.min_sample_size:
            return CorrelationResult(
                correlation_coefficient=0.0,
                p_value=1.0,
                significance=CorrelationSignificance.NOT_SIGNIFICANT,
                lag_offset=0,
                confidence_score=0.0,
                sample_count=min(len(series_1), len(series_2)),
                is_significant=False,
                details={"error": "Insufficient samples"}
            )
        
        # Converter para numpy arrays
        s1 = np.array(series_1, dtype=np.float64)
        s2 = np.array(series_2, dtype=np.float64)
        
        # Remover NaN e infinitos
        mask = np.isfinite(s1) & np.isfinite(s2)
        s1 = s1[mask]
        s2 = s2[mask]
        
        if len(s1) < self.min_sample_size:
            return CorrelationResult(
                correlation_coefficient=0.0,
                p_value=1.0,
                significance=CorrelationSignificance.NOT_SIGNIFICANT,
                lag_offset=0,
                confidence_score=0.0,
                sample_count=len(s1),
                is_significant=False,
                details={"error": "Insufficient valid samples after cleaning"}
            )
        
        # Normalizar se solicitado
        if normalize:
            s1 = self._normalize_series(s1)
            s2 = self._normalize_series(s2)
        
        # Encontrar melhor lag
        best_lag, best_correlation, best_p_value = self._find_best_lag(s1, s2, max_lag)
        
        # Alinhar séries com lag detectado
        if best_lag > 0:
            s1_aligned = s1[best_lag:]
            s2_aligned = s2[:-best_lag]
        elif best_lag < 0:
            s1_aligned = s1[:best_lag]
            s2_aligned = s2[-best_lag:]
        else:
            s1_aligned = s1
            s2_aligned = s2
        
        # Calcular significância
        significance = self._get_significance(best_p_value)
        is_significant = significance != CorrelationSignificance.NOT_SIGNIFICANT
        
        # Calcular confidence score (combinação de correlação e significância)
        confidence = self._calculate_confidence_score(
            best_correlation,
            best_p_value,
            len(s1_aligned)
        )
        
        return CorrelationResult(
            correlation_coefficient=best_correlation,
            p_value=best_p_value,
            significance=significance,
            lag_offset=best_lag,
            confidence_score=confidence,
            sample_count=len(s1_aligned),
            is_significant=is_significant,
            details={
                "normalized": normalize,
                "max_lag_tested": max_lag,
                "series_1_mean": float(np.mean(s1)),
                "series_1_std": float(np.std(s1)),
                "series_2_mean": float(np.mean(s2)),
                "series_2_std": float(np.std(s2))
            }
        )
    
    def detect_anomalies(
        self,
        series: List[float],
        threshold_std: float = 3.0
    ) -> Tuple[List[int], List[float]]:
        """
        Detecta anomalias em série usando desvio padrão.
        
        Args:
            series: Série temporal
            threshold_std: Quantos desvios padrão para considerar anomalia
        
        Returns:
            Tupla (índices_anomalias, valores_anomalias)
        """
        s = np.array(series, dtype=np.float64)
        s = s[np.isfinite(s)]
        
        if len(s) < 2:
            return [], []
        
        mean = np.mean(s)
        std = np.std(s)
        
        if std == 0:
            return [], []
        
        # Calcular z-score
        z_scores = np.abs((s - mean) / std)
        anomaly_indices = np.where(z_scores > threshold_std)[0].tolist()
        anomaly_values = [s[i] for i in anomaly_indices]
        
        return anomaly_indices, anomaly_values
    
    def detrend_series(self, series: List[float]) -> List[float]:
        """
        Remove tendência linear de série.
        
        Args:
            series: Série temporal
        
        Returns:
            Série sem tendência
        """
        s = np.array(series, dtype=np.float64)
        
        # Remover NaN
        valid_mask = np.isfinite(s)
        if not np.any(valid_mask):
            return series
        
        # Usar detrend do scipy
        detrended = signal.detrend(s[valid_mask])
        
        # Reconstruir array com NaN nos locais originais
        result = np.full_like(s, np.nan)
        result[valid_mask] = detrended
        
        return result.tolist()
    
    def _normalize_series(self, series: np.ndarray) -> np.ndarray:
        """Normaliza série (z-score)."""
        mean = np.mean(series)
        std = np.std(series)
        
        if std == 0:
            return series - mean
        
        return (series - mean) / std
    
    def _find_best_lag(
        self,
        s1: np.ndarray,
        s2: np.ndarray,
        max_lag: int
    ) -> Tuple[int, float, float]:
        """Encontra lag com melhor correlação."""
        best_lag = 0
        best_correlation = 0.0
        best_p_value = 1.0
        
        for lag in range(-max_lag, max_lag + 1):
            if lag > 0:
                s1_aligned = s1[lag:]
                s2_aligned = s2[:-lag]
            elif lag < 0:
                s1_aligned = s1[:lag]
                s2_aligned = s2[-lag:]
            else:
                s1_aligned = s1
                s2_aligned = s2
            
            if len(s1_aligned) < self.min_sample_size:
                continue
            
            try:
                correlation, p_value = pearsonr(s1_aligned, s2_aligned)
                
                # Usar valor absoluto para encontrar melhor correlação (positiva ou negativa)
                if abs(correlation) > abs(best_correlation):
                    best_lag = lag
                    best_correlation = correlation
                    best_p_value = p_value
            except (ValueError, RuntimeWarning):
                continue
        
        return best_lag, best_correlation, best_p_value
    
    def _get_significance(self, p_value: float) -> CorrelationSignificance:
        """Classifica significância baseado em p-value."""
        if p_value < 0.01:
            return CorrelationSignificance.VERY_SIGNIFICANT
        elif p_value < 0.05:
            return CorrelationSignificance.SIGNIFICANT
        elif p_value < 0.10:
            return CorrelationSignificance.WEAK
        else:
            return CorrelationSignificance.NOT_SIGNIFICANT
    
    def _calculate_confidence_score(
        self,
        correlation: float,
        p_value: float,
        sample_count: int
    ) -> float:
        """
        Calcula confidence score combinando correlação e significância.
        
        Score = |correlação| * (1 - p_value) * sample_factor
        """
        # Fator baseado em tamanho de amostra (mais amostras = mais confiança)
        sample_factor = min(1.0, sample_count / self.min_sample_size)
        
        # Combinar: correlação forte + p-value baixo + amostra grande
        confidence = abs(correlation) * (1.0 - p_value) * sample_factor
        
        return min(1.0, confidence)


class BayesianConfidenceCalculator:
    """
    Calcula confiança usando modelo Bayesiano simples.
    
    P(Correlação Real | Dados) = P(Dados | Correlação Real) * P(Correlação Real) / P(Dados)
    """
    
    def __init__(
        self,
        prior_probability: float = 0.3,
        likelihood_true_positive: float = 0.95,
        likelihood_false_positive: float = 0.05
    ):
        self.prior = prior_probability
        self.likelihood_tp = likelihood_true_positive
        self.likelihood_fp = likelihood_false_positive
    
    def calculate_posterior(
        self,
        correlation_coefficient: float,
        p_value: float,
        sample_count: int
    ) -> float:
        """
        Calcula probabilidade posterior de correlação real.
        
        Args:
            correlation_coefficient: Coeficiente de correlação de Pearson
            p_value: P-value do teste
            sample_count: Número de amostras
        
        Returns:
            Probabilidade posterior (0.0 a 1.0)
        """
        # Likelihood baseado em p-value
        if p_value < 0.05:
            likelihood = self.likelihood_tp
        else:
            likelihood = self.likelihood_fp
        
        # Ajustar likelihood baseado em magnitude de correlação
        likelihood *= abs(correlation_coefficient)
        
        # Ajustar likelihood baseado em tamanho de amostra
        sample_factor = min(1.0, sample_count / 20.0)
        likelihood *= sample_factor
        
        # Aplicar Bayes
        numerator = likelihood * self.prior
        denominator = (likelihood * self.prior) + ((1 - likelihood) * (1 - self.prior))
        
        if denominator == 0:
            return 0.0
        
        posterior = numerator / denominator
        return min(1.0, max(0.0, posterior))
    
    def update_prior(self, new_observations: int, successes: int):
        """Atualiza prior baseado em observações."""
        if new_observations == 0:
            return
        
        success_rate = successes / new_observations
        self.prior = (self.prior + success_rate) / 2.0
        self.prior = min(1.0, max(0.0, self.prior))
