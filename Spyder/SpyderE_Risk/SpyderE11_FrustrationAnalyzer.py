#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE11_FrustrationAnalyzer.py
Purpose: Spin Glass Theory Implementation for Market Frustration Detection

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-01-04

Module Description:
    Implements Giorgio Parisi's spin glass theory for financial markets.
    The S&P 500 is modeled as a frustrated system where stocks (spins)
    interact through correlations (couplings). This module detects:

    1. Frustration Index - Conflicting correlation triangles
    2. System Energy (Hamiltonian) - Market stress level
    3. Phase Transitions - Regime shift detection
    4. Replica Symmetry Breaking - Divergence of market states
    5. Ultrametric Collapse - MST length monitoring

    These physics-based metrics provide early warning signals for
    market instability before traditional indicators react.

References:
    - Parisi, G. (1979) "Infinite Number of Order Parameters for Spin-Glasses"
    - Bouchaud, J.P. & Potters, M. "Theory of Financial Risk and Derivative Pricing"
    - Nobel Prize in Physics 2021 - Giorgio Parisi (spin glasses)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
from collections import deque
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.cluster import hierarchy
from scipy.spatial.distance import pdist, squareform

# Optional: HMM for regime detection
try:
    from hmmlearn.hmm import GaussianHMM
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    warnings.warn("hmmlearn not installed. HMM regime detection disabled.")

# Optional: EVT for tail risk
try:
    from scipy.stats import genpareto
    EVT_AVAILABLE = True
except ImportError:
    EVT_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Frustration thresholds
LOW_FRUSTRATION_THRESHOLD = 0.10      # <10% frustrated triangles = stable
MODERATE_FRUSTRATION_THRESHOLD = 0.20  # 10-20% = building tension
HIGH_FRUSTRATION_THRESHOLD = 0.30      # 20-30% = elevated risk
CRITICAL_FRUSTRATION_THRESHOLD = 0.40  # >40% = phase transition likely

# Energy thresholds (normalized Hamiltonian)
LOW_ENERGY_THRESHOLD = -0.3           # Deeply stable state
TRANSITION_ENERGY_THRESHOLD = -0.1    # Near transition barrier
HIGH_ENERGY_THRESHOLD = 0.1           # Unstable, transition imminent

# Phase transition detection
ENERGY_SPIKE_THRESHOLD = 0.15         # 15% energy increase = potential transition
FRUSTRATION_SPIKE_THRESHOLD = 0.10    # 10% frustration increase
RSB_DIVERGENCE_THRESHOLD = 0.20       # 20% overlap divergence

# MST/Ultrametric parameters
MST_COLLAPSE_THRESHOLD = 0.7          # Tree length ratio indicating collapse
MST_WINDOW = 20                       # Days to track MST evolution

# HMM parameters
HMM_N_STATES = 2                      # Calm (Replica Symmetric) vs Glassy (RSB)
HMM_MIN_OBSERVATIONS = 100            # Minimum data points for HMM training
HMM_COVARIANCE_TYPE = "full"

# Analysis windows
SHORT_WINDOW = 5                      # Short-term analysis
MEDIUM_WINDOW = 20                    # Medium-term analysis
LONG_WINDOW = 60                      # Long-term baseline

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketPhase(Enum):
    """Market phase based on spin glass theory"""
    REPLICA_SYMMETRIC = "replica_symmetric"      # Calm, equilibrium state
    MARGINALLY_STABLE = "marginally_stable"      # Near transition
    REPLICA_SYMMETRY_BREAKING = "rsb"            # Glassy, multiple states
    PHASE_TRANSITION = "phase_transition"        # Active regime shift
    CRISIS = "crisis"                            # Full correlation breakdown

class FrustrationLevel(Enum):
    """Frustration level classification"""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"

class TransitionType(Enum):
    """Type of phase transition detected"""
    NONE = "none"
    GRADUAL = "gradual"                          # Slow regime shift
    SUDDEN = "sudden"                            # Sharp transition
    CRITICAL = "critical"                        # Crisis-level jump

class TradingImplication(Enum):
    """Trading strategy implications from spin glass analysis"""
    SELL_VOLATILITY = "sell_volatility"          # Iron condors, credit spreads
    NEUTRAL = "neutral"                          # Balanced approach
    REDUCE_EXPOSURE = "reduce_exposure"          # Tighten positions
    BUY_CONVEXITY = "buy_convexity"              # Put spreads, long vol
    DEFENSIVE = "defensive"                      # Maximum protection

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class FrustrationMetrics:
    """Core frustration analysis metrics"""
    timestamp: datetime

    # Frustration Index
    frustration_index: float              # Ratio of frustrated triangles
    frustrated_triangle_count: int        # Absolute count
    total_triangle_count: int             # Total triangles analyzed
    frustration_level: FrustrationLevel

    # Frustration breakdown by magnitude
    weak_frustration: float               # |product| < 0.1
    moderate_frustration: float           # 0.1 <= |product| < 0.3
    strong_frustration: float             # |product| >= 0.3

    # Sector frustration (if sector data available)
    sector_frustration: Dict[str, float] = field(default_factory=dict)
    most_frustrated_pairs: List[Tuple[str, str, float]] = field(default_factory=list)

@dataclass
class EnergyMetrics:
    """System energy (Hamiltonian) metrics"""
    timestamp: datetime

    # Core energy metrics
    hamiltonian: float                    # Total system energy
    normalized_energy: float              # Energy normalized to [-1, 1]
    energy_per_spin: float                # Average energy per asset

    # Energy components
    alignment_energy: float               # From positive correlations
    anti_alignment_energy: float          # From negative correlations
    frustration_energy: float             # From frustrated interactions

    # Energy dynamics
    energy_trend: float                   # Rate of energy change
    energy_volatility: float              # Volatility of energy
    energy_percentile: float              # Historical percentile

    # Stability assessment
    barrier_height: float                 # Estimated transition barrier
    stability_score: float                # 0-100 stability score

@dataclass
class PhaseTransitionMetrics:
    """Phase transition detection metrics"""
    timestamp: datetime

    # Current phase
    current_phase: MarketPhase
    phase_probability: float
    days_in_phase: int

    # Transition detection
    transition_detected: bool
    transition_type: TransitionType
    transition_probability: float

    # Early warning signals
    energy_warning: bool
    frustration_warning: bool
    rsb_warning: bool
    mst_warning: bool

    # Combined warning score
    warning_score: float                  # 0-100, higher = more danger

    # Trading implication
    trading_implication: TradingImplication

@dataclass
class ReplicaSymmetryMetrics:
    """Replica Symmetry Breaking detection"""
    timestamp: datetime

    # Overlap distribution
    overlap_mean: float                   # Average overlap between time windows
    overlap_variance: float               # Variance of overlaps
    overlap_distribution: List[float] = field(default_factory=list)

    # RSB detection
    rsb_detected: bool
    rsb_strength: float                   # 0-1, strength of symmetry breaking

    # Parisi order parameter (simplified)
    order_parameter: float                # q(x) approximation

    # Divergence metrics
    short_long_divergence: float          # Short vs long-term correlation divergence
    sector_divergence: float              # Cross-sector divergence

@dataclass
class UltrametricMetrics:
    """Ultrametricity and MST analysis"""
    timestamp: datetime

    # MST metrics
    mst_total_length: float               # Sum of MST edge weights
    mst_normalized_length: float          # Normalized by N-1
    mst_length_ratio: float               # Current / historical average

    # Ultrametric properties
    ultrametric_score: float              # How tree-like is the structure
    hierarchy_depth: int                  # Depth of correlation hierarchy

    # Collapse detection
    collapse_detected: bool
    collapse_magnitude: float             # How much tree has shrunk

    # Cluster analysis
    n_clusters: int                       # Number of correlation clusters
    largest_cluster_size: int             # Size of dominant cluster
    cluster_concentration: float          # Concentration in top clusters

@dataclass
class SpinGlassAnalysis:
    """Complete spin glass analysis result"""
    timestamp: datetime

    # Component metrics
    frustration: FrustrationMetrics
    energy: EnergyMetrics
    phase_transition: PhaseTransitionMetrics
    replica_symmetry: ReplicaSymmetryMetrics
    ultrametric: UltrametricMetrics

    # HMM regime (if available)
    hmm_regime: Optional[str] = None
    hmm_regime_probability: Optional[float] = None

    # EVT tail risk (if available)
    evt_shape_parameter: Optional[float] = None
    evt_tail_probability: Optional[float] = None

    # Overall assessment
    market_stability: str                 # "stable", "unstable", "critical"
    confidence: float                     # Confidence in assessment

    # Actionable signals
    signals: List[str] = field(default_factory=list)
    trading_recommendation: TradingImplication = TradingImplication.NEUTRAL

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class FrustrationAnalyzer:
    """
    Spin Glass Theory Implementation for Market Analysis.

    Models the S&P 500 / SPY as a frustrated spin glass system where
    individual stocks are "spins" coupled through correlations. Detects
    market instability through frustration, energy, and phase transition
    metrics derived from statistical physics.

    Key Concepts:
        - Frustration: Conflicting correlations that cannot all be satisfied
        - Hamiltonian: Total "energy" of the market system
        - Phase Transition: Sudden regime shifts between metastable states
        - Replica Symmetry Breaking: Divergence of market "replicas"
        - Ultrametricity: Hierarchical structure of correlations

    Example:
        >>> analyzer = FrustrationAnalyzer()
        >>> analyzer.initialize()
        >>> analysis = analyzer.analyze(returns_data, correlation_matrix)
        >>> print(f"Frustration: {analysis.frustration.frustration_index:.1%}")
        >>> print(f"Phase: {analysis.phase_transition.current_phase.value}")
    """

    def __init__(self, use_hmm: bool = True, use_evt: bool = True):
        """
        Initialize the Frustration Analyzer.

        Args:
            use_hmm: Enable HMM-based regime detection
            use_evt: Enable EVT tail risk analysis
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.use_hmm = use_hmm and HMM_AVAILABLE
        self.use_evt = use_evt and EVT_AVAILABLE

        # HMM model
        self.hmm_model: Optional[GaussianHMM] = None
        self.hmm_trained = False
        self.regime_map: Dict[int, str] = {}

        # Historical tracking
        self.frustration_history: deque = deque(maxlen=500)
        self.energy_history: deque = deque(maxlen=500)
        self.mst_history: deque = deque(maxlen=500)
        self.phase_history: deque = deque(maxlen=100)

        # Baseline statistics (computed on initialization)
        self.baseline_frustration: Optional[float] = None
        self.baseline_energy: Optional[float] = None
        self.baseline_mst_length: Optional[float] = None

        self.logger.info("FrustrationAnalyzer initialized")
        if not HMM_AVAILABLE:
            self.logger.warning("HMM not available - install hmmlearn for regime detection")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================

    def initialize(self, historical_returns: Optional[pd.DataFrame] = None) -> bool:
        """
        Initialize the analyzer, optionally with historical data for baseline.

        Args:
            historical_returns: Historical returns for baseline calculation

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing FrustrationAnalyzer...")

            # Initialize HMM if enabled
            if self.use_hmm:
                self.hmm_model = GaussianHMM(
                    n_components=HMM_N_STATES,
                    covariance_type=HMM_COVARIANCE_TYPE,
                    n_iter=100,
                    random_state=42
                )
                self.logger.info("HMM model initialized")

            # Compute baselines if historical data provided
            if historical_returns is not None and len(historical_returns) >= LONG_WINDOW:
                self._compute_baselines(historical_returns)

            self.logger.info("FrustrationAnalyzer initialized successfully")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "FrustrationAnalyzer.initialize")
            return False

    def analyze(
        self,
        returns_data: pd.DataFrame,
        correlation_matrix: Optional[np.ndarray] = None,
        weights: Optional[np.ndarray] = None,
        sector_mapping: Optional[Dict[str, str]] = None
    ) -> SpinGlassAnalysis:
        """
        Perform complete spin glass analysis on market data.

        Args:
            returns_data: Asset returns DataFrame (time x assets)
            correlation_matrix: Pre-computed correlation matrix (optional)
            weights: Portfolio weights (optional, equal-weight if None)
            sector_mapping: Asset to sector mapping (optional)

        Returns:
            Complete spin glass analysis
        """
        try:
            timestamp = datetime.now()
            n_assets = len(returns_data.columns)

            # Compute correlation matrix if not provided
            if correlation_matrix is None:
                correlation_matrix = returns_data.corr().values

            # Default to equal weights
            if weights is None:
                weights = np.ones(n_assets) / n_assets

            # 1. Frustration Analysis
            frustration = self._calculate_frustration(
                correlation_matrix,
                returns_data.columns.tolist(),
                sector_mapping
            )

            # 2. Energy/Hamiltonian Analysis
            energy = self._calculate_energy(correlation_matrix, weights)

            # 3. Replica Symmetry Analysis
            replica_symmetry = self._calculate_replica_symmetry(returns_data)

            # 4. Ultrametric/MST Analysis
            ultrametric = self._calculate_ultrametric(correlation_matrix)

            # 5. Phase Transition Detection
            phase_transition = self._detect_phase_transition(
                frustration, energy, replica_symmetry, ultrametric
            )

            # 6. HMM Regime Detection (if enabled)
            hmm_regime = None
            hmm_probability = None
            if self.use_hmm and self.hmm_trained:
                hmm_regime, hmm_probability = self._detect_hmm_regime(returns_data)

            # 7. EVT Tail Risk (if enabled)
            evt_shape = None
            evt_tail_prob = None
            if self.use_evt:
                evt_shape, evt_tail_prob = self._calculate_evt_tail_risk(returns_data)

            # 8. Generate trading signals
            signals, recommendation = self._generate_signals(
                frustration, energy, phase_transition, ultrametric
            )

            # 9. Overall stability assessment
            stability = self._assess_stability(
                frustration, energy, phase_transition
            )

            # Create complete analysis
            analysis = SpinGlassAnalysis(
                timestamp=timestamp,
                frustration=frustration,
                energy=energy,
                phase_transition=phase_transition,
                replica_symmetry=replica_symmetry,
                ultrametric=ultrametric,
                hmm_regime=hmm_regime,
                hmm_regime_probability=hmm_probability,
                evt_shape_parameter=evt_shape,
                evt_tail_probability=evt_tail_prob,
                market_stability=stability,
                confidence=self._calculate_confidence(frustration, energy),
                signals=signals,
                trading_recommendation=recommendation
            )

            # Update history
            self._update_history(analysis)

            self.logger.debug(
                f"Spin glass analysis: frustration={frustration.frustration_index:.1%}, "
                f"phase={phase_transition.current_phase.value}, "
                f"stability={stability}"
            )

            return analysis

        except Exception as e:
            self.error_handler.handle_error(e, "FrustrationAnalyzer.analyze")
            return self._get_default_analysis()

    def train_hmm(self, returns_data: pd.DataFrame) -> bool:
        """
        Train the HMM model on historical returns data.

        Args:
            returns_data: Historical returns DataFrame

        Returns:
            bool: True if training successful
        """
        if not self.use_hmm or self.hmm_model is None:
            self.logger.warning("HMM not available or not enabled")
            return False

        try:
            # Calculate portfolio returns
            portfolio_returns = returns_data.mean(axis=1).values

            if len(portfolio_returns) < HMM_MIN_OBSERVATIONS:
                self.logger.warning(
                    f"Insufficient data for HMM training "
                    f"(need {HMM_MIN_OBSERVATIONS}, got {len(portfolio_returns)})"
                )
                return False

            # Reshape for HMM
            X = portfolio_returns.reshape(-1, 1)

            # Fit HMM
            self.hmm_model.fit(X)

            # Identify regimes based on variance
            # Higher variance state = Glassy (RSB)
            variances = [self.hmm_model.covars_[i][0][0] for i in range(HMM_N_STATES)]
            glassy_state = np.argmax(variances)
            calm_state = np.argmin(variances)

            self.regime_map = {
                calm_state: "REPLICA_SYMMETRIC",
                glassy_state: "REPLICA_SYMMETRY_BREAKING"
            }

            self.hmm_trained = True
            self.logger.info(
                f"HMM trained successfully. "
                f"Calm variance: {variances[calm_state]:.6f}, "
                f"Glassy variance: {variances[glassy_state]:.6f}"
            )

            return True

        except Exception as e:
            self.error_handler.handle_error(e, "FrustrationAnalyzer.train_hmm")
            return False

    def get_frustration_history(self, periods: int = 30) -> pd.DataFrame:
        """Get historical frustration metrics."""
        if not self.frustration_history:
            return pd.DataFrame()

        history = list(self.frustration_history)[-periods:]
        return pd.DataFrame([
            {
                'timestamp': h['timestamp'],
                'frustration_index': h['frustration_index'],
                'level': h['level']
            }
            for h in history
        ])

    def get_energy_history(self, periods: int = 30) -> pd.DataFrame:
        """Get historical energy metrics."""
        if not self.energy_history:
            return pd.DataFrame()

        history = list(self.energy_history)[-periods:]
        return pd.DataFrame([
            {
                'timestamp': h['timestamp'],
                'hamiltonian': h['hamiltonian'],
                'normalized_energy': h['normalized_energy']
            }
            for h in history
        ])

    # ==========================================================================
    # FRUSTRATION CALCULATION
    # ==========================================================================

    def _calculate_frustration(
        self,
        correlation_matrix: np.ndarray,
        asset_names: List[str],
        sector_mapping: Optional[Dict[str, str]] = None
    ) -> FrustrationMetrics:
        """
        Calculate frustration index and related metrics.

        Frustration occurs when three assets form a "frustrated triangle":
        - A correlates positively with B
        - B correlates positively with C
        - But A correlates negatively with C

        This is impossible to satisfy simultaneously - the hallmark of
        a spin glass system.
        """
        n = correlation_matrix.shape[0]

        frustrated_count = 0
        weak_frustrated = 0
        moderate_frustrated = 0
        strong_frustrated = 0
        total_triangles = 0

        frustrated_pairs: List[Tuple[str, str, float]] = []

        # Iterate through all triangles
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    rho_ij = correlation_matrix[i, j]
                    rho_jk = correlation_matrix[j, k]
                    rho_ik = correlation_matrix[i, k]

                    # Product of three correlations
                    product = rho_ij * rho_jk * rho_ik

                    total_triangles += 1

                    if product < 0:  # Frustrated triangle
                        frustrated_count += 1
                        abs_product = abs(product)

                        if abs_product < 0.1:
                            weak_frustrated += 1
                        elif abs_product < 0.3:
                            moderate_frustrated += 1
                        else:
                            strong_frustrated += 1

                            # Track strongly frustrated pairs
                            if len(frustrated_pairs) < 10:
                                # Find the most conflicting edge
                                edges = [
                                    (asset_names[i], asset_names[j], rho_ij),
                                    (asset_names[j], asset_names[k], rho_jk),
                                    (asset_names[i], asset_names[k], rho_ik)
                                ]
                                # The negative correlation in a positive context
                                for a1, a2, rho in edges:
                                    if rho < 0:
                                        frustrated_pairs.append((a1, a2, rho))

        # Calculate frustration index
        frustration_index = frustrated_count / total_triangles if total_triangles > 0 else 0.0

        # Classify frustration level
        if frustration_index < LOW_FRUSTRATION_THRESHOLD / 2:
            level = FrustrationLevel.MINIMAL
        elif frustration_index < LOW_FRUSTRATION_THRESHOLD:
            level = FrustrationLevel.LOW
        elif frustration_index < MODERATE_FRUSTRATION_THRESHOLD:
            level = FrustrationLevel.MODERATE
        elif frustration_index < HIGH_FRUSTRATION_THRESHOLD:
            level = FrustrationLevel.ELEVATED
        elif frustration_index < CRITICAL_FRUSTRATION_THRESHOLD:
            level = FrustrationLevel.HIGH
        else:
            level = FrustrationLevel.CRITICAL

        # Sector frustration (if mapping provided)
        sector_frustration = {}
        if sector_mapping:
            sector_frustration = self._calculate_sector_frustration(
                correlation_matrix, asset_names, sector_mapping
            )

        return FrustrationMetrics(
            timestamp=datetime.now(),
            frustration_index=frustration_index,
            frustrated_triangle_count=frustrated_count,
            total_triangle_count=total_triangles,
            frustration_level=level,
            weak_frustration=weak_frustrated / total_triangles if total_triangles > 0 else 0,
            moderate_frustration=moderate_frustrated / total_triangles if total_triangles > 0 else 0,
            strong_frustration=strong_frustrated / total_triangles if total_triangles > 0 else 0,
            sector_frustration=sector_frustration,
            most_frustrated_pairs=frustrated_pairs[:5]
        )

    def _calculate_sector_frustration(
        self,
        correlation_matrix: np.ndarray,
        asset_names: List[str],
        sector_mapping: Dict[str, str]
    ) -> Dict[str, float]:
        """Calculate frustration by sector."""
        # Group assets by sector
        sectors: Dict[str, List[int]] = {}
        for i, asset in enumerate(asset_names):
            sector = sector_mapping.get(asset, "Unknown")
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(i)

        sector_frustration = {}

        for sector, indices in sectors.items():
            if len(indices) < 3:
                continue

            frustrated = 0
            total = 0

            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    for k in range(j + 1, len(indices)):
                        idx_i, idx_j, idx_k = indices[i], indices[j], indices[k]
                        product = (
                            correlation_matrix[idx_i, idx_j] *
                            correlation_matrix[idx_j, idx_k] *
                            correlation_matrix[idx_i, idx_k]
                        )
                        total += 1
                        if product < 0:
                            frustrated += 1

            if total > 0:
                sector_frustration[sector] = frustrated / total

        return sector_frustration

    # ==========================================================================
    # ENERGY/HAMILTONIAN CALCULATION
    # ==========================================================================

    def _calculate_energy(
        self,
        correlation_matrix: np.ndarray,
        weights: np.ndarray
    ) -> EnergyMetrics:
        """
        Calculate the system Hamiltonian (energy).

        In spin glass theory, the Hamiltonian is:
        H = -Σ J_ij * s_i * s_j

        For markets, we use correlations as couplings (J_ij = ρ_ij)
        and weights as spin magnitudes. Lower energy = more stable.
        """
        n = correlation_matrix.shape[0]

        # Calculate weighted Hamiltonian
        # H = -Σ w_i * w_j * ρ_ij
        hamiltonian = 0.0
        alignment_energy = 0.0
        anti_alignment_energy = 0.0

        for i in range(n):
            for j in range(i + 1, n):
                coupling = correlation_matrix[i, j]
                interaction = weights[i] * weights[j] * coupling

                hamiltonian -= interaction  # Negative because aligned = low energy

                if coupling > 0:
                    alignment_energy -= interaction
                else:
                    anti_alignment_energy -= interaction

        # Normalize energy to [-1, 1] range
        max_possible_energy = np.sum(weights) ** 2 / 2
        normalized_energy = hamiltonian / max_possible_energy if max_possible_energy > 0 else 0

        # Energy per spin
        energy_per_spin = hamiltonian / n if n > 0 else 0

        # Calculate frustration energy (energy from frustrated triangles)
        frustration_energy = self._calculate_frustration_energy(correlation_matrix, weights)

        # Energy dynamics from history
        energy_trend = 0.0
        energy_volatility = 0.0
        energy_percentile = 50.0

        if len(self.energy_history) >= 5:
            recent_energies = [h['normalized_energy'] for h in list(self.energy_history)[-20:]]
            if len(recent_energies) >= 2:
                energy_trend = recent_energies[-1] - recent_energies[0]
                energy_volatility = np.std(recent_energies)
            if self.baseline_energy is not None:
                all_energies = recent_energies + [self.baseline_energy]
                energy_percentile = stats.percentileofscore(all_energies, normalized_energy)

        # Estimate transition barrier (simplified)
        barrier_height = self._estimate_barrier_height(correlation_matrix, weights)

        # Stability score (0-100)
        # Lower energy + higher barrier = more stable
        stability_score = 50 + (barrier_height * 25) - (normalized_energy * 25)
        stability_score = max(0, min(100, stability_score))

        return EnergyMetrics(
            timestamp=datetime.now(),
            hamiltonian=hamiltonian,
            normalized_energy=normalized_energy,
            energy_per_spin=energy_per_spin,
            alignment_energy=alignment_energy,
            anti_alignment_energy=anti_alignment_energy,
            frustration_energy=frustration_energy,
            energy_trend=energy_trend,
            energy_volatility=energy_volatility,
            energy_percentile=energy_percentile,
            barrier_height=barrier_height,
            stability_score=stability_score
        )

    def _calculate_frustration_energy(
        self,
        correlation_matrix: np.ndarray,
        weights: np.ndarray
    ) -> float:
        """Calculate energy contribution from frustrated interactions."""
        n = correlation_matrix.shape[0]
        frustration_energy = 0.0

        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    product = (
                        correlation_matrix[i, j] *
                        correlation_matrix[j, k] *
                        correlation_matrix[i, k]
                    )

                    if product < 0:  # Frustrated
                        # Energy contribution proportional to frustration
                        weight_factor = weights[i] * weights[j] * weights[k]
                        frustration_energy += abs(product) * weight_factor

        return frustration_energy

    def _estimate_barrier_height(
        self,
        correlation_matrix: np.ndarray,
        weights: np.ndarray
    ) -> float:
        """
        Estimate the energy barrier height between current state and transition.

        Higher barrier = harder to transition = more stable.
        """
        # Use eigenvalue analysis of correlation matrix
        eigenvalues = np.linalg.eigvalsh(correlation_matrix)

        # Largest eigenvalue dominates (market factor)
        # Gap between largest and second largest indicates stability
        sorted_eigenvalues = np.sort(eigenvalues)[::-1]

        if len(sorted_eigenvalues) >= 2:
            spectral_gap = sorted_eigenvalues[0] - sorted_eigenvalues[1]
            # Normalize to [0, 1]
            barrier = spectral_gap / sorted_eigenvalues[0] if sorted_eigenvalues[0] > 0 else 0
        else:
            barrier = 0.5

        return barrier

    # ==========================================================================
    # REPLICA SYMMETRY BREAKING DETECTION
    # ==========================================================================

    def _calculate_replica_symmetry(
        self,
        returns_data: pd.DataFrame
    ) -> ReplicaSymmetryMetrics:
        """
        Detect Replica Symmetry Breaking (RSB).

        RSB occurs when different "replicas" of the system (correlation
        matrices computed over different windows) diverge significantly.
        This indicates the market has multiple possible states.
        """
        n_periods = len(returns_data)

        if n_periods < LONG_WINDOW:
            return ReplicaSymmetryMetrics(
                timestamp=datetime.now(),
                overlap_mean=1.0,
                overlap_variance=0.0,
                rsb_detected=False,
                rsb_strength=0.0,
                order_parameter=1.0,
                short_long_divergence=0.0,
                sector_divergence=0.0
            )

        # Calculate correlation matrices for different windows
        short_corr = returns_data.iloc[-SHORT_WINDOW:].corr().values
        medium_corr = returns_data.iloc[-MEDIUM_WINDOW:].corr().values
        long_corr = returns_data.iloc[-LONG_WINDOW:].corr().values

        # Calculate overlaps (similarity between correlation matrices)
        overlap_short_medium = self._calculate_overlap(short_corr, medium_corr)
        overlap_medium_long = self._calculate_overlap(medium_corr, long_corr)
        overlap_short_long = self._calculate_overlap(short_corr, long_corr)

        overlaps = [overlap_short_medium, overlap_medium_long, overlap_short_long]

        overlap_mean = np.mean(overlaps)
        overlap_variance = np.var(overlaps)

        # RSB detected if overlaps diverge significantly
        rsb_detected = overlap_variance > 0.01 or overlap_short_long < 0.8
        rsb_strength = 1.0 - overlap_mean if overlap_mean < 1.0 else 0.0

        # Parisi order parameter (simplified as 1 - average overlap)
        order_parameter = 1.0 - overlap_mean

        # Short-long divergence
        short_long_divergence = 1.0 - overlap_short_long

        return ReplicaSymmetryMetrics(
            timestamp=datetime.now(),
            overlap_mean=overlap_mean,
            overlap_variance=overlap_variance,
            overlap_distribution=overlaps,
            rsb_detected=rsb_detected,
            rsb_strength=rsb_strength,
            order_parameter=order_parameter,
            short_long_divergence=short_long_divergence,
            sector_divergence=0.0  # Would need sector data
        )

    def _calculate_overlap(
        self,
        matrix_a: np.ndarray,
        matrix_b: np.ndarray
    ) -> float:
        """
        Calculate overlap between two correlation matrices.

        Overlap q = (1/N²) Σ_ij ρ_ij^A * ρ_ij^B
        """
        n = matrix_a.shape[0]
        overlap = np.sum(matrix_a * matrix_b) / (n * n)
        return overlap

    # ==========================================================================
    # ULTRAMETRIC/MST ANALYSIS
    # ==========================================================================

    def _calculate_ultrametric(
        self,
        correlation_matrix: np.ndarray
    ) -> UltrametricMetrics:
        """
        Analyze ultrametric properties via Minimum Spanning Tree.

        In a spin glass, states are organized hierarchically (ultrametrically).
        The MST of the correlation distance matrix captures this structure.
        A shrinking MST indicates correlation collapse (crisis precursor).
        """
        n = correlation_matrix.shape[0]

        # Convert correlation to distance: d = sqrt(2(1 - ρ))
        distance_matrix = np.sqrt(2 * (1 - np.abs(correlation_matrix)))
        np.fill_diagonal(distance_matrix, 0)

        # Compute MST
        mst = minimum_spanning_tree(distance_matrix)
        mst_array = mst.toarray()

        # Total MST length
        mst_total_length = np.sum(mst_array[mst_array > 0])

        # Normalized by N-1 edges
        mst_normalized_length = mst_total_length / (n - 1) if n > 1 else 0

        # Compare to historical average
        mst_length_ratio = 1.0
        if self.baseline_mst_length is not None and self.baseline_mst_length > 0:
            mst_length_ratio = mst_normalized_length / self.baseline_mst_length

        # Collapse detection
        collapse_detected = mst_length_ratio < MST_COLLAPSE_THRESHOLD
        collapse_magnitude = 1.0 - mst_length_ratio if collapse_detected else 0.0

        # Ultrametric score (how tree-like is the structure)
        ultrametric_score = self._calculate_ultrametric_score(correlation_matrix, mst_array)

        # Cluster analysis from MST
        n_clusters, largest_cluster, concentration = self._analyze_mst_clusters(mst_array)

        # Hierarchy depth (approximate from MST)
        hierarchy_depth = self._estimate_hierarchy_depth(mst_array)

        return UltrametricMetrics(
            timestamp=datetime.now(),
            mst_total_length=mst_total_length,
            mst_normalized_length=mst_normalized_length,
            mst_length_ratio=mst_length_ratio,
            ultrametric_score=ultrametric_score,
            hierarchy_depth=hierarchy_depth,
            collapse_detected=collapse_detected,
            collapse_magnitude=collapse_magnitude,
            n_clusters=n_clusters,
            largest_cluster_size=largest_cluster,
            cluster_concentration=concentration
        )

    def _calculate_ultrametric_score(
        self,
        correlation_matrix: np.ndarray,
        mst_array: np.ndarray
    ) -> float:
        """
        Calculate how well the data satisfies ultrametric inequality.

        For ultrametric: d(A,C) <= max(d(A,B), d(B,C))
        """
        n = correlation_matrix.shape[0]
        if n < 3:
            return 1.0

        distance_matrix = np.sqrt(2 * (1 - np.abs(correlation_matrix)))

        violations = 0
        total = 0

        # Sample triangles for efficiency
        sample_size = min(1000, n * (n - 1) * (n - 2) // 6)

        for _ in range(sample_size):
            i, j, k = np.random.choice(n, 3, replace=False)

            d_ij = distance_matrix[i, j]
            d_jk = distance_matrix[j, k]
            d_ik = distance_matrix[i, k]

            # Check ultrametric inequality
            max_pair = max(d_ij, d_jk)
            if d_ik > max_pair * 1.01:  # Small tolerance
                violations += 1

            total += 1

        return 1.0 - (violations / total) if total > 0 else 1.0

    def _analyze_mst_clusters(
        self,
        mst_array: np.ndarray
    ) -> Tuple[int, int, float]:
        """Analyze cluster structure from MST."""
        n = mst_array.shape[0]

        # Find connected components at different thresholds
        # Use hierarchical clustering on MST
        condensed = pdist(mst_array)
        linkage = hierarchy.linkage(condensed, method='average')

        # Cut tree to get clusters
        clusters = hierarchy.fcluster(linkage, t=3, criterion='maxclust')

        unique, counts = np.unique(clusters, return_counts=True)
        n_clusters = len(unique)
        largest_cluster = max(counts)
        concentration = largest_cluster / n if n > 0 else 1.0

        return n_clusters, largest_cluster, concentration

    def _estimate_hierarchy_depth(self, mst_array: np.ndarray) -> int:
        """Estimate depth of hierarchy from MST."""
        n = mst_array.shape[0]
        if n <= 1:
            return 0

        # Use degree distribution as proxy for depth
        degrees = np.sum(mst_array > 0, axis=1)
        max_degree = np.max(degrees)

        # Approximate depth as log of max degree
        depth = int(np.log2(max_degree + 1)) + 1
        return depth

    # ==========================================================================
    # PHASE TRANSITION DETECTION
    # ==========================================================================

    def _detect_phase_transition(
        self,
        frustration: FrustrationMetrics,
        energy: EnergyMetrics,
        replica_symmetry: ReplicaSymmetryMetrics,
        ultrametric: UltrametricMetrics
    ) -> PhaseTransitionMetrics:
        """
        Detect phase transitions between market regimes.

        Combines multiple signals:
        - Energy spikes
        - Frustration increases
        - RSB onset
        - MST collapse
        """
        # Individual warning signals
        energy_warning = energy.normalized_energy > TRANSITION_ENERGY_THRESHOLD
        frustration_warning = frustration.frustration_index > HIGH_FRUSTRATION_THRESHOLD
        rsb_warning = replica_symmetry.rsb_detected
        mst_warning = ultrametric.collapse_detected

        # Count active warnings
        warning_count = sum([energy_warning, frustration_warning, rsb_warning, mst_warning])

        # Combined warning score (0-100)
        warning_score = (
            (energy.normalized_energy + 1) * 15 +        # Energy contribution
            frustration.frustration_index * 30 +          # Frustration contribution
            replica_symmetry.rsb_strength * 25 +          # RSB contribution
            ultrametric.collapse_magnitude * 30           # MST contribution
        )
        warning_score = max(0, min(100, warning_score))

        # Determine current phase
        if warning_score < 20:
            current_phase = MarketPhase.REPLICA_SYMMETRIC
        elif warning_score < 40:
            current_phase = MarketPhase.MARGINALLY_STABLE
        elif warning_score < 60:
            current_phase = MarketPhase.REPLICA_SYMMETRY_BREAKING
        elif warning_score < 80:
            current_phase = MarketPhase.PHASE_TRANSITION
        else:
            current_phase = MarketPhase.CRISIS

        # Detect if transition is occurring
        transition_detected = False
        transition_type = TransitionType.NONE
        transition_probability = 0.0

        if len(self.phase_history) >= 2:
            prev_phase = self.phase_history[-1]['phase']
            if current_phase != prev_phase:
                transition_detected = True

                # Classify transition type
                phase_jump = abs(
                    list(MarketPhase).index(current_phase) -
                    list(MarketPhase).index(prev_phase)
                )

                if phase_jump >= 2:
                    transition_type = TransitionType.SUDDEN
                    transition_probability = 0.9
                else:
                    transition_type = TransitionType.GRADUAL
                    transition_probability = 0.7

        # Days in current phase
        days_in_phase = 1
        if self.phase_history:
            for entry in reversed(self.phase_history):
                if entry['phase'] == current_phase:
                    days_in_phase += 1
                else:
                    break

        # Determine trading implication
        trading_implication = self._determine_trading_implication(
            current_phase, warning_score, transition_detected
        )

        return PhaseTransitionMetrics(
            timestamp=datetime.now(),
            current_phase=current_phase,
            phase_probability=1.0 - (warning_score / 200),  # Confidence
            days_in_phase=days_in_phase,
            transition_detected=transition_detected,
            transition_type=transition_type,
            transition_probability=transition_probability,
            energy_warning=energy_warning,
            frustration_warning=frustration_warning,
            rsb_warning=rsb_warning,
            mst_warning=mst_warning,
            warning_score=warning_score,
            trading_implication=trading_implication
        )

    def _determine_trading_implication(
        self,
        phase: MarketPhase,
        warning_score: float,
        transition_detected: bool
    ) -> TradingImplication:
        """Determine trading strategy based on phase."""
        if phase == MarketPhase.REPLICA_SYMMETRIC and warning_score < 25:
            return TradingImplication.SELL_VOLATILITY
        elif phase == MarketPhase.MARGINALLY_STABLE:
            return TradingImplication.NEUTRAL
        elif phase == MarketPhase.REPLICA_SYMMETRY_BREAKING:
            return TradingImplication.REDUCE_EXPOSURE
        elif phase == MarketPhase.PHASE_TRANSITION:
            return TradingImplication.BUY_CONVEXITY
        else:  # CRISIS
            return TradingImplication.DEFENSIVE

    # ==========================================================================
    # HMM REGIME DETECTION
    # ==========================================================================

    def _detect_hmm_regime(
        self,
        returns_data: pd.DataFrame
    ) -> Tuple[Optional[str], Optional[float]]:
        """Detect regime using trained HMM."""
        if not self.hmm_trained or self.hmm_model is None:
            return None, None

        try:
            # Get recent returns
            portfolio_returns = returns_data.mean(axis=1).values[-HMM_MIN_OBSERVATIONS:]
            X = portfolio_returns.reshape(-1, 1)

            # Predict states
            states = self.hmm_model.predict(X)
            current_state = states[-1]

            # Get posterior probability
            posteriors = self.hmm_model.predict_proba(X)
            current_probability = posteriors[-1, current_state]

            regime = self.regime_map.get(current_state, "UNKNOWN")

            return regime, current_probability

        except Exception as e:
            self.logger.error(f"HMM prediction error: {e}")
            return None, None

    # ==========================================================================
    # EVT TAIL RISK
    # ==========================================================================

    def _calculate_evt_tail_risk(
        self,
        returns_data: pd.DataFrame,
        threshold_quantile: float = 0.95
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate tail risk using Extreme Value Theory (Peaks Over Threshold).
        """
        if not EVT_AVAILABLE:
            return None, None

        try:
            # Get portfolio returns
            portfolio_returns = returns_data.mean(axis=1).values

            # Focus on negative returns (left tail)
            losses = -portfolio_returns[portfolio_returns < 0]

            if len(losses) < 20:
                return None, None

            # Threshold (95th percentile of losses)
            threshold = np.quantile(losses, threshold_quantile)

            # Exceedances over threshold
            exceedances = losses[losses > threshold] - threshold

            if len(exceedances) < 10:
                return None, None

            # Fit Generalized Pareto Distribution
            shape, loc, scale = genpareto.fit(exceedances)

            # Probability of extreme loss (e.g., 3x threshold)
            extreme_threshold = threshold * 3
            tail_probability = 1 - genpareto.cdf(
                extreme_threshold - threshold, shape, loc, scale
            )

            return shape, tail_probability

        except Exception as e:
            self.logger.error(f"EVT calculation error: {e}")
            return None, None

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================

    def _generate_signals(
        self,
        frustration: FrustrationMetrics,
        energy: EnergyMetrics,
        phase: PhaseTransitionMetrics,
        ultrametric: UltrametricMetrics
    ) -> Tuple[List[str], TradingImplication]:
        """Generate actionable trading signals."""
        signals = []

        # Frustration signals
        if frustration.frustration_level == FrustrationLevel.CRITICAL:
            signals.append("CRITICAL: Frustration at crisis levels - maximum defensive posture")
        elif frustration.frustration_level == FrustrationLevel.HIGH:
            signals.append("WARNING: High frustration detected - reduce risk exposure")
        elif frustration.frustration_level == FrustrationLevel.ELEVATED:
            signals.append("CAUTION: Elevated frustration - monitor closely")

        # Energy signals
        if energy.energy_trend > ENERGY_SPIKE_THRESHOLD:
            signals.append("ALERT: Energy rising rapidly - transition likely")
        if energy.stability_score < 30:
            signals.append("WARNING: Low stability score - unstable regime")

        # Phase signals
        if phase.transition_detected:
            signals.append(f"TRANSITION: {phase.transition_type.value} phase change detected")
        if phase.current_phase == MarketPhase.CRISIS:
            signals.append("CRISIS: Market in crisis phase - defensive only")

        # Ultrametric signals
        if ultrametric.collapse_detected:
            signals.append("WARNING: Correlation structure collapsing - diversification failing")

        # Positive signals
        if phase.current_phase == MarketPhase.REPLICA_SYMMETRIC and energy.stability_score > 70:
            signals.append("STABLE: Market in calm regime - premium selling favorable")

        # Determine overall recommendation
        recommendation = phase.trading_implication

        return signals, recommendation

    def _assess_stability(
        self,
        frustration: FrustrationMetrics,
        energy: EnergyMetrics,
        phase: PhaseTransitionMetrics
    ) -> str:
        """Assess overall market stability."""
        if phase.current_phase in [MarketPhase.CRISIS, MarketPhase.PHASE_TRANSITION]:
            return "critical"
        elif phase.current_phase == MarketPhase.REPLICA_SYMMETRY_BREAKING:
            return "unstable"
        elif phase.warning_score > 40:
            return "unstable"
        elif energy.stability_score < 50:
            return "unstable"
        else:
            return "stable"

    def _calculate_confidence(
        self,
        frustration: FrustrationMetrics,
        energy: EnergyMetrics
    ) -> float:
        """Calculate confidence in the analysis."""
        # Base confidence on data quality and consistency
        confidence = 0.7  # Base confidence

        # Higher confidence with more history
        if len(self.frustration_history) > 50:
            confidence += 0.1
        if len(self.energy_history) > 50:
            confidence += 0.1

        # Lower confidence during transitions
        if energy.energy_volatility > 0.1:
            confidence -= 0.1

        return max(0.3, min(0.95, confidence))

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _compute_baselines(self, returns_data: pd.DataFrame) -> None:
        """Compute baseline metrics from historical data."""
        try:
            correlation_matrix = returns_data.corr().values
            n = correlation_matrix.shape[0]
            weights = np.ones(n) / n

            # Baseline frustration
            frustration = self._calculate_frustration(
                correlation_matrix, returns_data.columns.tolist(), None
            )
            self.baseline_frustration = frustration.frustration_index

            # Baseline energy
            energy = self._calculate_energy(correlation_matrix, weights)
            self.baseline_energy = energy.normalized_energy

            # Baseline MST length
            ultrametric = self._calculate_ultrametric(correlation_matrix)
            self.baseline_mst_length = ultrametric.mst_normalized_length

            self.logger.info(
                f"Baselines computed: frustration={self.baseline_frustration:.3f}, "
                f"energy={self.baseline_energy:.3f}, mst={self.baseline_mst_length:.3f}"
            )

        except Exception as e:
            self.logger.error(f"Error computing baselines: {e}")

    def _update_history(self, analysis: SpinGlassAnalysis) -> None:
        """Update historical tracking."""
        self.frustration_history.append({
            'timestamp': analysis.timestamp,
            'frustration_index': analysis.frustration.frustration_index,
            'level': analysis.frustration.frustration_level.value
        })

        self.energy_history.append({
            'timestamp': analysis.timestamp,
            'hamiltonian': analysis.energy.hamiltonian,
            'normalized_energy': analysis.energy.normalized_energy
        })

        self.mst_history.append({
            'timestamp': analysis.timestamp,
            'mst_length': analysis.ultrametric.mst_normalized_length,
            'collapse': analysis.ultrametric.collapse_detected
        })

        self.phase_history.append({
            'timestamp': analysis.timestamp,
            'phase': analysis.phase_transition.current_phase,
            'warning_score': analysis.phase_transition.warning_score
        })

    def _get_default_analysis(self) -> SpinGlassAnalysis:
        """Return default analysis for error cases."""
        timestamp = datetime.now()

        return SpinGlassAnalysis(
            timestamp=timestamp,
            frustration=FrustrationMetrics(
                timestamp=timestamp,
                frustration_index=0.15,
                frustrated_triangle_count=0,
                total_triangle_count=1,
                frustration_level=FrustrationLevel.LOW,
                weak_frustration=0.1,
                moderate_frustration=0.05,
                strong_frustration=0.0
            ),
            energy=EnergyMetrics(
                timestamp=timestamp,
                hamiltonian=0.0,
                normalized_energy=0.0,
                energy_per_spin=0.0,
                alignment_energy=0.0,
                anti_alignment_energy=0.0,
                frustration_energy=0.0,
                energy_trend=0.0,
                energy_volatility=0.0,
                energy_percentile=50.0,
                barrier_height=0.5,
                stability_score=50.0
            ),
            phase_transition=PhaseTransitionMetrics(
                timestamp=timestamp,
                current_phase=MarketPhase.REPLICA_SYMMETRIC,
                phase_probability=0.5,
                days_in_phase=1,
                transition_detected=False,
                transition_type=TransitionType.NONE,
                transition_probability=0.0,
                energy_warning=False,
                frustration_warning=False,
                rsb_warning=False,
                mst_warning=False,
                warning_score=25.0,
                trading_implication=TradingImplication.NEUTRAL
            ),
            replica_symmetry=ReplicaSymmetryMetrics(
                timestamp=timestamp,
                overlap_mean=0.9,
                overlap_variance=0.01,
                rsb_detected=False,
                rsb_strength=0.0,
                order_parameter=0.1,
                short_long_divergence=0.0,
                sector_divergence=0.0
            ),
            ultrametric=UltrametricMetrics(
                timestamp=timestamp,
                mst_total_length=1.0,
                mst_normalized_length=0.5,
                mst_length_ratio=1.0,
                ultrametric_score=0.8,
                hierarchy_depth=3,
                collapse_detected=False,
                collapse_magnitude=0.0,
                n_clusters=3,
                largest_cluster_size=5,
                cluster_concentration=0.3
            ),
            market_stability="stable",
            confidence=0.5
        )


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_sample_data(n_assets: int = 20, n_periods: int = 200) -> pd.DataFrame:
    """Create sample returns data for testing."""
    np.random.seed(42)

    # Market factor
    market = np.random.normal(0, 0.015, n_periods)

    # Create correlated assets with some frustration
    returns = {}
    for i in range(n_assets):
        # Random market beta
        beta = 0.5 + 0.5 * np.random.random()

        # Sector factor (creates frustration between sectors)
        sector = i // 5
        sector_factor = np.random.normal(0, 0.01, n_periods) * ((-1) ** sector)

        # Idiosyncratic
        idio = np.random.normal(0, 0.02, n_periods)

        returns[f'Asset_{i}'] = beta * market + sector_factor + idio

    dates = pd.date_range(end=datetime.now(), periods=n_periods, freq='D')
    return pd.DataFrame(returns, index=dates)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

async def main():
    """Test the FrustrationAnalyzer."""
    print("=" * 80)
    print("SPYDER E11 - Frustration Analyzer (Spin Glass Theory)")
    print("=" * 80)

    # Create analyzer
    analyzer = FrustrationAnalyzer()

    # Initialize
    print("\n1. Initializing analyzer...")
    if not analyzer.initialize():
        print("   Failed to initialize")
        return
    print("   Initialized successfully")

    # Create sample data
    print("\n2. Creating sample market data...")
    returns_data = create_sample_data(n_assets=15, n_periods=150)
    print(f"   Created: {len(returns_data)} periods, {len(returns_data.columns)} assets")

    # Train HMM if available
    if analyzer.use_hmm:
        print("\n3. Training HMM regime detector...")
        if analyzer.train_hmm(returns_data):
            print("   HMM trained successfully")
        else:
            print("   HMM training failed (insufficient data or not available)")

    # Run analysis
    print("\n4. Running spin glass analysis...")
    analysis = analyzer.analyze(returns_data)

    # Print results
    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)

    print(f"\nFRUSTRATION METRICS:")
    print(f"  Frustration Index: {analysis.frustration.frustration_index:.1%}")
    print(f"  Frustrated Triangles: {analysis.frustration.frustrated_triangle_count}/{analysis.frustration.total_triangle_count}")
    print(f"  Level: {analysis.frustration.frustration_level.value.upper()}")
    print(f"  Strong Frustration: {analysis.frustration.strong_frustration:.1%}")

    print(f"\nENERGY METRICS:")
    print(f"  Hamiltonian: {analysis.energy.hamiltonian:.4f}")
    print(f"  Normalized Energy: {analysis.energy.normalized_energy:.3f}")
    print(f"  Barrier Height: {analysis.energy.barrier_height:.3f}")
    print(f"  Stability Score: {analysis.energy.stability_score:.1f}/100")

    print(f"\nPHASE TRANSITION:")
    print(f"  Current Phase: {analysis.phase_transition.current_phase.value.upper()}")
    print(f"  Warning Score: {analysis.phase_transition.warning_score:.1f}/100")
    print(f"  Transition Detected: {analysis.phase_transition.transition_detected}")
    print(f"  Trading Implication: {analysis.phase_transition.trading_implication.value.upper()}")

    print(f"\nREPLICA SYMMETRY:")
    print(f"  RSB Detected: {analysis.replica_symmetry.rsb_detected}")
    print(f"  RSB Strength: {analysis.replica_symmetry.rsb_strength:.3f}")
    print(f"  Order Parameter: {analysis.replica_symmetry.order_parameter:.3f}")

    print(f"\nULTRAMETRIC ANALYSIS:")
    print(f"  MST Length (normalized): {analysis.ultrametric.mst_normalized_length:.3f}")
    print(f"  Collapse Detected: {analysis.ultrametric.collapse_detected}")
    print(f"  Ultrametric Score: {analysis.ultrametric.ultrametric_score:.3f}")
    print(f"  Clusters: {analysis.ultrametric.n_clusters}")

    if analysis.hmm_regime:
        print(f"\nHMM REGIME:")
        print(f"  Current: {analysis.hmm_regime}")
        print(f"  Probability: {analysis.hmm_regime_probability:.1%}")

    if analysis.evt_shape_parameter is not None:
        print(f"\nEVT TAIL RISK:")
        print(f"  Shape Parameter (xi): {analysis.evt_shape_parameter:.3f}")
        print(f"  Tail Probability: {analysis.evt_tail_probability:.4f}")

    print(f"\nOVERALL ASSESSMENT:")
    print(f"  Market Stability: {analysis.market_stability.upper()}")
    print(f"  Confidence: {analysis.confidence:.1%}")
    print(f"  Recommendation: {analysis.trading_recommendation.value.upper()}")

    if analysis.signals:
        print(f"\nSIGNALS:")
        for signal in analysis.signals:
            print(f"  - {signal}")

    print("\n" + "=" * 80)
    print("Test completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
