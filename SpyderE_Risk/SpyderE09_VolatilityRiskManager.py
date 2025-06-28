#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE08_VolatilityRiskManager.py
Group: E (Risk Management)
Purpose: Volatility-specific risk management and protection protocols

Description:
    This module provides specialized risk management for volatility trading,
    including VIX spike protection protocols, volatility regime-based position
    sizing, gamma scalping automation, and comprehensive vol surface risk metrics.
    It integrates with existing risk management systems to add volatility-specific
    controls and protections.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-12-28
Last Updated: 2025-12-28 Time: 11:30:00
"""

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityRegime(Enum):
    """Volatility regime classifications"""
    ULTRA_LOW = "ULTRA_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class ProtectionLevel(Enum):
    """Risk protection levels"""
    NONE = "NONE"
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    HEAVY = "HEAVY"
    MAXIMUM = "MAXIMUM"

class VolRiskSignal(Enum):
    """Volatility risk signals"""
    ALL_CLEAR = auto()
    CAUTION = auto()
    WARNING = auto()
    DANGER = auto()
    CRITICAL = auto()

class GammaScalpAction(Enum):
    """Gamma scalping actions"""
    BUY_STOCK = "BUY_STOCK"
    SELL_STOCK = "SELL_STOCK"
    NO_ACTION = "NO_ACTION"
    REBALANCE = "REBALANCE"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VolatilityMetrics:
    """Comprehensive volatility metrics"""
    timestamp: datetime
    spot_vol: float  # Realized volatility
    implied_vol: float  # ATM implied volatility
    vix_level: float
    vix_change: float
    vol_of_vol: float  # VVIX or vol of vol
    term_structure_slope: float
    skew_level: float
    regime: VolatilityRegime
    
@dataclass
class VolatilityRisk:
    """Volatility risk assessment"""
    timestamp: datetime
    vega_exposure: float
    volga_exposure: float
    vanna_exposure: float
    total_vol_risk: float
    risk_signal: VolRiskSignal
    protection_needed: ProtectionLevel
    hedge_ratio: float
    risk_factors: List[str]

@dataclass
class GammaScalpingPlan:
    """Gamma scalping execution plan"""
    timestamp: datetime
    current_delta: float
    target_delta: float
    hedge_needed: float
    action: GammaScalpAction
    band_limits: Tuple[float, float]  # (lower, upper)
    expected_profit: float
    last_scalp_price: Optional[float]

@dataclass
class VolProtocolAction:
    """Volatility protection protocol action"""
    timestamp: datetime
    action_type: str  # 'REDUCE_SIZE', 'ADD_HEDGE', 'CLOSE_POSITION', etc.
    urgency: str  # 'IMMEDIATE', 'SOON', 'MONITOR'
    details: Dict[str, Any]
    reason: str

@dataclass
class VolRiskProfile:
    """Complete volatility risk profile"""
    timestamp: datetime
    metrics: VolatilityMetrics
    risk_assessment: VolatilityRisk
    position_adjustments: Dict[str, float]  # Symbol -> size multiplier
    scalping_plans: List[GammaScalpingPlan]
    protection_actions: List[VolProtocolAction]
    overall_health: str  # 'HEALTHY', 'STRESSED', 'CRITICAL'

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class VolatilityRiskManager:
    """
    Volatility-specific risk management and protection system.
    
    This class provides comprehensive volatility risk management including
    VIX spike protection, regime-based position sizing, gamma scalping
    automation, and vol surface risk monitoring.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        
    Example:
        >>> vol_risk_mgr = VolatilityRiskManager()
        >>> risk_profile = vol_risk_mgr.assess_volatility_risk()
        >>> if risk_profile.risk_assessment.risk_signal == VolRiskSignal.DANGER:
        >>>     vol_risk_mgr.activate_protection_protocol()
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize volatility risk manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        
        # Configuration
        self.config = config or {}
        self.max_vega = self.config.get('max_vega', MAX_VEGA_EXPOSURE)
        self.max_volga = self.config.get('max_volga', MAX_VOLGA_EXPOSURE)
        self.max_vanna = self.config.get('max_vanna', MAX_VANNA_EXPOSURE)
        
        # Component integration
        self.risk_manager = get_risk_manager()
        self.position_sizer = get_position_sizer()
        self.vix_analyzer = VIXAnalyzer()
        self.vol_surface_analyzer = VolatilitySurfaceAnalyzer()
        self.gex_calculator = GammaExposureCalculator()
        
        # Risk tracking
        self.current_regime = VolatilityRegime.NORMAL
        self.protection_level = ProtectionLevel.NONE
        self.active_protocols: List[VolProtocolAction] = []
        
        # Gamma scalping state
        self.scalping_positions: Dict[str, GammaScalpingPlan] = {}
        self.scalp_history: deque = deque(maxlen=100)
        
        # Historical data
        self.vol_history: deque = deque(maxlen=1000)
        self.risk_history: deque = deque(maxlen=1000)
        
        # Threading
        self._lock = threading.Lock()
        self._monitoring_thread: Optional[threading.Thread] = None
        self._running = False
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS - RISK ASSESSMENT
    # ==========================================================================
    def assess_volatility_risk(self) -> VolRiskProfile:
        """
        Perform comprehensive volatility risk assessment.
        
        Returns:
            Complete VolRiskProfile
        """
        # Get current volatility metrics
        metrics = self._calculate_volatility_metrics()
        
        # Assess risk levels
        risk_assessment = self._assess_risk_levels(metrics)
        
        # Calculate position adjustments
        position_adjustments = self._calculate_position_adjustments(metrics)
        
        # Generate gamma scalping plans
        scalping_plans = self._generate_scalping_plans()
        
        # Determine protection actions
        protection_actions = self._determine_protection_actions(risk_assessment)
        
        # Overall health assessment
        overall_health = self._assess_overall_health(risk_assessment, metrics)
        
        profile = VolRiskProfile(
            timestamp=datetime.now(),
            metrics=metrics,
            risk_assessment=risk_assessment,
            position_adjustments=position_adjustments,
            scalping_plans=scalping_plans,
            protection_actions=protection_actions,
            overall_health=overall_health
        )
        
        # Store history
        with self._lock:
            self.vol_history.append(metrics)
            self.risk_history.append(risk_assessment)
            
        return profile
        
    def get_vix_protection_status(self) -> Dict[str, Any]:
        """
        Get current VIX spike protection status.
        
        Returns:
            VIX protection analysis
        """
        vix_analysis = self.vix_analyzer.get_vix_analysis()
        current_vix = vix_analysis['current_vix']
        
        # Determine protection level
        if current_vix >= VIX_EXTREME_SPIKE:
            protection = ProtectionLevel.MAXIMUM
            hedge_ratio = HEDGING_LEVELS['EXTREME']
        elif current_vix >= VIX_SPIKE_THRESHOLD:
            protection = ProtectionLevel.HEAVY
            hedge_ratio = HEDGING_LEVELS['HIGH']
        elif current_vix >= VIX_ELEVATED:
            protection = ProtectionLevel.MODERATE
            hedge_ratio = HEDGING_LEVELS['ELEVATED']
        else:
            protection = ProtectionLevel.NONE
            hedge_ratio = HEDGING_LEVELS['NORMAL']
            
        # Check rate of change
        vix_roc = self._calculate_vix_rate_of_change()
        spike_risk = abs(vix_roc) > VIX_RATE_OF_CHANGE_THRESHOLD
        
        return {
            'current_vix': current_vix,
            'protection_level': protection.value,
            'hedge_ratio': hedge_ratio,
            'spike_risk': spike_risk,
            'vix_rate_of_change': vix_roc,
            'term_structure': vix_analysis.get('term_structure', 'NORMAL'),
            'recommendations': self._generate_vix_recommendations(current_vix, vix_roc, protection)
        }
        
    def calculate_regime_position_size(self, base_size: int) -> int:
        """
        Calculate position size adjusted for volatility regime.
        
        Args:
            base_size: Base position size
            
        Returns:
            Adjusted position size
        """
        # Get current regime
        regime = self._determine_volatility_regime()
        
        # Apply multiplier
        multiplier = VOL_POSITION_MULTIPLIERS.get(regime.value, 1.0)
        adjusted_size = int(base_size * multiplier)
        
        # Apply additional constraints in extreme conditions
        if regime == VolatilityRegime.EXTREME:
            # Further reduce if multiple risk factors present
            risk_factors = self._count_risk_factors()
            if risk_factors >= 3:
                adjusted_size = int(adjusted_size * 0.5)
                
        self.logger.info(f"Position size adjusted from {base_size} to {adjusted_size} "
                        f"(regime: {regime.value}, multiplier: {multiplier})")
        
        return adjusted_size
        
    # ==========================================================================
    # PUBLIC METHODS - GAMMA SCALPING
    # ==========================================================================
    def get_gamma_scalping_signal(self, position_id: str) -> Optional[GammaScalpingPlan]:
        """
        Get gamma scalping signal for a position.
        
        Args:
            position_id: Position identifier
            
        Returns:
            GammaScalpingPlan if action needed
        """
        # Get position Greeks
        position_greeks = self._get_position_greeks(position_id)
        if not position_greeks:
            return None
            
        current_delta = position_greeks['delta']
        current_gamma = position_greeks['gamma']
        
        # Check if gamma scalping is appropriate
        if abs(current_gamma) < 0.01:  # Too little gamma
            return None
            
        # Calculate bands
        spot_price = self._get_spot_price()
        band_width = spot_price * GAMMA_BAND_WIDTH
        
        # Determine if rebalancing needed
        target_delta = 0.0  # Delta neutral target
        delta_difference = current_delta - target_delta
        
        if abs(delta_difference) < 0.1:  # Close enough to neutral
            action = GammaScalpAction.NO_ACTION
            hedge_needed = 0
        elif delta_difference > 0:
            action = GammaScalpAction.SELL_STOCK
            hedge_needed = -delta_difference * 100  # Convert to shares
        else:
            action = GammaScalpAction.BUY_STOCK
            hedge_needed = -delta_difference * 100
            
        # Calculate expected profit
        expected_profit = self._calculate_scalp_profit(current_gamma, band_width)
        
        # Check if profitable
        if expected_profit < MIN_SCALP_PROFIT and action != GammaScalpAction.NO_ACTION:
            action = GammaScalpAction.NO_ACTION
            hedge_needed = 0
            
        plan = GammaScalpingPlan(
            timestamp=datetime.now(),
            current_delta=current_delta,
            target_delta=target_delta,
            hedge_needed=hedge_needed,
            action=action,
            band_limits=(spot_price - band_width, spot_price + band_width),
            expected_profit=expected_profit,
            last_scalp_price=self._get_last_scalp_price(position_id)
        )
        
        # Store plan
        with self._lock:
            self.scalping_positions[position_id] = plan
            
        return plan
        
    def execute_gamma_scalp(self, position_id: str, plan: GammaScalpingPlan) -> Dict[str, Any]:
        """
        Execute gamma scalping trade.
        
        Args:
            position_id: Position identifier
            plan: Scalping plan to execute
            
        Returns:
            Execution results
        """
        if plan.action == GammaScalpAction.NO_ACTION:
            return {'status': 'NO_ACTION_NEEDED'}
            
        try:
            # Prepare order
            order_details = {
                'symbol': 'SPY',
                'quantity': abs(int(plan.hedge_needed)),
                'side': 'BUY' if plan.action == GammaScalpAction.BUY_STOCK else 'SELL',
                'order_type': 'LIMIT',
                'limit_price': self._calculate_scalp_limit_price(plan.action)
            }
            
            # Execute through risk manager
            execution_result = self.risk_manager.execute_hedge_order(order_details)
            
            # Record scalp
            if execution_result.get('status') == 'FILLED':
                self._record_scalp(position_id, plan, execution_result)
                
            return execution_result
            
        except Exception as e:
            self.logger.error(f"Error executing gamma scalp: {e}")
            return {'status': 'ERROR', 'error': str(e)}
            
    # ==========================================================================
    # PUBLIC METHODS - PROTECTION PROTOCOLS
    # ==========================================================================
    def activate_protection_protocol(self, level: Optional[ProtectionLevel] = None) -> List[VolProtocolAction]:
        """
        Activate volatility protection protocols.
        
        Args:
            level: Protection level to activate (auto-determined if None)
            
        Returns:
            List of protocol actions taken
        """
        # Determine protection level if not specified
        if level is None:
            current_risk = self.assess_volatility_risk()
            level = current_risk.risk_assessment.protection_needed
            
        if level == ProtectionLevel.NONE:
            self.logger.info("No protection needed")
            return []
            
        actions = []
        
        # Level-based actions
        if level.value >= ProtectionLevel.LIGHT.value:
            actions.extend(self._apply_light_protection())
            
        if level.value >= ProtectionLevel.MODERATE.value:
            actions.extend(self._apply_moderate_protection())
            
        if level.value >= ProtectionLevel.HEAVY.value:
            actions.extend(self._apply_heavy_protection())
            
        if level == ProtectionLevel.MAXIMUM:
            actions.extend(self._apply_maximum_protection())
            
        # Store active protocols
        with self._lock:
            self.active_protocols.extend(actions)
            self.protection_level = level
            
        # Emit protection event
        self._emit_protection_event(level, actions)
        
        self.logger.warning(f"Protection protocol activated: {level.value}")
        return actions
        
    def get_vol_surface_risks(self) -> Dict[str, Any]:
        """
        Analyze volatility surface risks.
        
        Returns:
            Vol surface risk analysis
        """
        # Get surface metrics
        surface = self.vol_surface_analyzer.build_surface()
        
        # Calculate Greeks exposures
        vega_exposure = self._calculate_vega_exposure()
        volga_exposure = self._calculate_volga_exposure()
        vanna_exposure = self._calculate_vanna_exposure()
        
        # Check limits
        vega_breach = abs(vega_exposure) > self.max_vega
        volga_breach = abs(volga_exposure) > self.max_volga
        vanna_breach = abs(vanna_exposure) > self.max_vanna
        
        # Analyze skew risk
        skew_risk = self._analyze_skew_risk(surface)
        
        # Term structure risk
        term_risk = self._analyze_term_structure_risk(surface)
        
        return {
            'timestamp': datetime.now(),
            'exposures': {
                'vega': vega_exposure,
                'volga': volga_exposure,
                'vanna': vanna_exposure
            },
            'limit_breaches': {
                'vega': vega_breach,
                'volga': volga_breach,
                'vanna': vanna_breach
            },
            'skew_risk': skew_risk,
            'term_structure_risk': term_risk,
            'surface_stability': self._assess_surface_stability(surface),
            'recommendations': self._generate_surface_recommendations(
                vega_breach, volga_breach, vanna_breach, skew_risk
            )
        }
        
    # ==========================================================================
    # PRIVATE METHODS - METRICS CALCULATION
    # ==========================================================================
    def _calculate_volatility_metrics(self) -> VolatilityMetrics:
        """Calculate current volatility metrics."""
        # Get VIX data
        vix_analysis = self.vix_analyzer.get_vix_analysis()
        
        # Calculate realized volatility
        spot_vol = self._calculate_realized_volatility()
        
        # Get implied volatility
        implied_vol = self._get_atm_implied_volatility()
        
        # Vol of vol (simplified)
        vol_of_vol = self._calculate_vol_of_vol()
        
        # Term structure
        term_slope = self._calculate_term_structure_slope()
        
        # Skew
        skew = self._calculate_current_skew()
        
        # Determine regime
        regime = self._determine_volatility_regime()
        
        return VolatilityMetrics(
            timestamp=datetime.now(),
            spot_vol=spot_vol,
            implied_vol=implied_vol,
            vix_level=vix_analysis['current_vix'],
            vix_change=vix_analysis.get('vix_change', 0),
            vol_of_vol=vol_of_vol,
            term_structure_slope=term_slope,
            skew_level=skew,
            regime=regime
        )
        
    def _assess_risk_levels(self, metrics: VolatilityMetrics) -> VolatilityRisk:
        """Assess volatility risk levels."""
        # Calculate Greek exposures
        vega = self._calculate_vega_exposure()
        volga = self._calculate_volga_exposure()
        vanna = self._calculate_vanna_exposure()
        
        # Total risk score
        total_risk = abs(vega) + abs(volga) * 0.5 + abs(vanna) * 0.7
        
        # Determine risk signal
        risk_factors = []
        
        if metrics.vix_level > VIX_SPIKE_THRESHOLD:
            risk_factors.append("VIX spike level")
            
        if abs(metrics.vix_change) > VIX_RATE_OF_CHANGE_THRESHOLD:
            risk_factors.append("Rapid VIX change")
            
        if abs(vega) > self.max_vega:
            risk_factors.append("Vega limit breach")
            
        if metrics.vol_of_vol > 100:  # High VVIX
            risk_factors.append("Elevated vol of vol")
            
        if abs(metrics.skew_level) > SKEW_RISK_THRESHOLD:
            risk_factors.append("Extreme skew")
            
        # Determine signal
        if len(risk_factors) >= 4:
            signal = VolRiskSignal.CRITICAL
        elif len(risk_factors) >= 3:
            signal = VolRiskSignal.DANGER
        elif len(risk_factors) >= 2:
            signal = VolRiskSignal.WARNING
        elif len(risk_factors) >= 1:
            signal = VolRiskSignal.CAUTION
        else:
            signal = VolRiskSignal.ALL_CLEAR
            
        # Protection level
        protection = self._determine_protection_level(signal, metrics)
        
        # Hedge ratio
        hedge_ratio = self._calculate_optimal_hedge_ratio(metrics, signal)
        
        return VolatilityRisk(
            timestamp=datetime.now(),
            vega_exposure=vega,
            volga_exposure=volga,
            vanna_exposure=vanna,
            total_vol_risk=total_risk,
            risk_signal=signal,
            protection_needed=protection,
            hedge_ratio=hedge_ratio,
            risk_factors=risk_factors
        )
        
    def _calculate_position_adjustments(self, metrics: VolatilityMetrics) -> Dict[str, float]:
        """Calculate position size adjustments by strategy."""
        adjustments = {}
        
        # Base multiplier from regime
        base_multiplier = VOL_POSITION_MULTIPLIERS.get(metrics.regime.value, 1.0)
        
        # Strategy-specific adjustments
        # Short volatility strategies need more adjustment
        adjustments['iron_condor'] = base_multiplier * 0.8
        adjustments['credit_spread'] = base_multiplier * 0.9
        adjustments['naked_puts'] = base_multiplier * 0.7
        
        # Long volatility strategies can increase in high vol
        if metrics.regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            adjustments['long_straddle'] = 1.5
            adjustments['long_strangle'] = 1.3
        else:
            adjustments['long_straddle'] = base_multiplier
            adjustments['long_strangle'] = base_multiplier
            
        # Neutral strategies
        adjustments['butterfly'] = base_multiplier * 0.95
        adjustments['calendar'] = base_multiplier
        
        return adjustments
        
    def _generate_scalping_plans(self) -> List[GammaScalpingPlan]:
        """Generate gamma scalping plans for current positions."""
        plans = []
        
        # Get positions with significant gamma
        positions = self._get_gamma_positions()
        
        for position_id, position_data in positions.items():
            plan = self.get_gamma_scalping_signal(position_id)
            if plan and plan.action != GammaScalpAction.NO_ACTION:
                plans.append(plan)
                
        return plans
        
    def _determine_protection_actions(self, risk: VolatilityRisk) -> List[VolProtocolAction]:
        """Determine protection actions based on risk assessment."""
        actions = []
        
        # VIX spike protection
        if 'VIX spike level' in risk.risk_factors:
            actions.append(VolProtocolAction(
                timestamp=datetime.now(),
                action_type='ADD_VIX_HEDGE',
                urgency='IMMEDIATE',
                details={
                    'hedge_size': risk.hedge_ratio,
                    'instrument': 'VIX_CALLS'
                },
                reason='VIX spike protection'
            ))
            
        # Vega limit breach
        if abs(risk.vega_exposure) > self.max_vega:
            actions.append(VolProtocolAction(
                timestamp=datetime.now(),
                action_type='REDUCE_VEGA',
                urgency='SOON',
                details={
                    'current_vega': risk.vega_exposure,
                    'target_vega': self.max_vega * 0.8,
                    'reduction_needed': abs(risk.vega_exposure) - self.max_vega
                },
                reason='Vega exposure limit breach'
            ))
            
        # Position size reduction
        if risk.risk_signal in [VolRiskSignal.DANGER, VolRiskSignal.CRITICAL]:
            actions.append(VolProtocolAction(
                timestamp=datetime.now(),
                action_type='REDUCE_SIZE',
                urgency='IMMEDIATE' if risk.risk_signal == VolRiskSignal.CRITICAL else 'SOON',
                details={
                    'reduction_percent': 0.5 if risk.risk_signal == VolRiskSignal.CRITICAL else 0.25
                },
                reason=f'High volatility risk: {risk.risk_signal.name}'
            ))
            
        return actions
        
    # ==========================================================================
    # PRIVATE METHODS - REGIME ANALYSIS
    # ==========================================================================
    def _determine_volatility_regime(self) -> VolatilityRegime:
        """Determine current volatility regime."""
        vix_analysis = self.vix_analyzer.get_vix_analysis()
        current_vix = vix_analysis['current_vix']
        
        for regime, threshold in sorted(VOL_REGIME_THRESHOLDS.items(), 
                                      key=lambda x: x[1], reverse=True):
            if current_vix >= threshold:
                return VolatilityRegime[regime]
                
        return VolatilityRegime.ULTRA_LOW
        
    def _calculate_vix_rate_of_change(self) -> float:
        """Calculate VIX rate of change."""
        if len(self.vol_history) < 2:
            return 0.0
            
        current_vix = self.vol_history[-1].vix_level
        previous_vix = self.vol_history[-2].vix_level
        
        if previous_vix == 0:
            return 0.0
            
        return (current_vix - previous_vix) / previous_vix
        
    def _count_risk_factors(self) -> int:
        """Count active risk factors."""
        if not self.risk_history:
            return 0
            
        return len(self.risk_history[-1].risk_factors)
        
    # ==========================================================================
    # PRIVATE METHODS - GREEK CALCULATIONS
    # ==========================================================================
    def _calculate_vega_exposure(self) -> float:
        """Calculate total vega exposure."""
        # This would aggregate vega across all positions
        # Placeholder for demonstration
        return np.random.normal(50000, 20000)
        
    def _calculate_volga_exposure(self) -> float:
        """Calculate total volga (vega convexity) exposure."""
        # Volga = dVega/dVol
        # Placeholder for demonstration
        return np.random.normal(20000, 10000)
        
    def _calculate_vanna_exposure(self) -> float:
        """Calculate total vanna exposure."""
        # Vanna = dVega/dSpot = dDelta/dVol
        # Placeholder for demonstration
        return np.random.normal(30000, 15000)
        
    def _get_position_greeks(self, position_id: str) -> Optional[Dict[str, float]]:
        """Get Greeks for a specific position."""
        # This would fetch actual position Greeks
        # Placeholder for demonstration
        return {
            'delta': np.random.normal(0, 50),
            'gamma': np.random.normal(5, 2),
            'vega': np.random.normal(1000, 500),
            'theta': np.random.normal(-100, 50)
        }
        
    # ==========================================================================
    # PRIVATE METHODS - VOL SURFACE ANALYSIS
    # ==========================================================================
    def _calculate_realized_volatility(self, period: int = 20) -> float:
        """Calculate realized volatility."""
        # This would use actual price data
        # Placeholder returning synthetic value
        return np.random.normal(15, 3)
        
    def _get_atm_implied_volatility(self) -> float:
        """Get ATM implied volatility."""
        # This would fetch from option chain
        return np.random.normal(16, 2)
        
    def _calculate_vol_of_vol(self) -> float:
        """Calculate volatility of volatility (VVIX proxy)."""
        if len(self.vol_history) < 20:
            return 80.0  # Default
            
        recent_vols = [v.implied_vol for v in self.vol_history[-20:]]
        return np.std(recent_vols) * np.sqrt(252) * 100
        
    def _calculate_term_structure_slope(self) -> float:
        """Calculate vol term structure slope."""
        # This would analyze actual term structure
        # Placeholder
        return np.random.normal(0, 0.02)
        
    def _calculate_current_skew(self) -> float:
        """Calculate current volatility skew."""
        # 25-delta put - 25-delta call IV
        return np.random.normal(0.05, 0.03)
        
    def _analyze_skew_risk(self, surface) -> Dict[str, Any]:
        """Analyze skew risk from vol surface."""
        # Placeholder analysis
        current_skew = self._calculate_current_skew()
        
        return {
            'current_skew': current_skew,
            'skew_percentile': stats.percentileofscore([0.05], current_skew),
            'risk_level': 'HIGH' if abs(current_skew) > SKEW_RISK_THRESHOLD else 'NORMAL',
            'directional_bias': 'PUT_SKEW' if current_skew > 0 else 'CALL_SKEW'
        }
        
    def _analyze_term_structure_risk(self, surface) -> Dict[str, Any]:
        """Analyze term structure risks."""
        slope = self._calculate_term_structure_slope()
        
        return {
            'slope': slope,
            'shape': 'CONTANGO' if slope > 0 else 'BACKWARDATION',
            'steepness': 'STEEP' if abs(slope) > 0.05 else 'NORMAL',
            'calendar_risk': 'HIGH' if abs(slope) > 0.1 else 'NORMAL'
        }
        
    def _assess_surface_stability(self, surface) -> str:
        """Assess volatility surface stability."""
        # This would analyze surface dynamics
        # Placeholder
        vol_of_vol = self._calculate_vol_of_vol()
        
        if vol_of_vol > 120:
            return 'UNSTABLE'
        elif vol_of_vol > 90:
            return 'CHOPPY'
        else:
            return 'STABLE'
            
    # ==========================================================================
    # PRIVATE METHODS - GAMMA SCALPING
    # ==========================================================================
    def _calculate_scalp_profit(self, gamma: float, band_width: float) -> float:
        """Calculate expected profit from gamma scalp."""
        # Profit = 0.5 * Gamma * (Move)^2
        expected_move = band_width / 2
        return 0.5 * abs(gamma) * expected_move ** 2
        
    def _get_last_scalp_price(self, position_id: str) -> Optional[float]:
        """Get last scalp price for position."""
        for scalp in reversed(self.scalp_history):
            if scalp.get('position_id') == position_id:
                return scalp.get('price')
        return None
        
    def _calculate_scalp_limit_price(self, action: GammaScalpAction) -> float:
        """Calculate limit price for scalp order."""
        spot = self._get_spot_price()
        
        # Place limit slightly better than mid
        if action == GammaScalpAction.BUY_STOCK:
            return spot - 0.02  # Buy 2 cents below
        else:
            return spot + 0.02  # Sell 2 cents above
            
    def _record_scalp(self, position_id: str, plan: GammaScalpingPlan, 
                     execution: Dict[str, Any]) -> None:
        """Record gamma scalp execution."""
        scalp_record = {
            'timestamp': datetime.now(),
            'position_id': position_id,
            'action': plan.action.value,
            'quantity': execution.get('filled_quantity'),
            'price': execution.get('fill_price'),
            'expected_profit': plan.expected_profit
        }
        
        with self._lock:
            self.scalp_history.append(scalp_record)
            
    def _get_gamma_positions(self) -> Dict[str, Any]:
        """Get positions with significant gamma exposure."""
        # This would fetch actual positions
        # Placeholder
        return {
            'position_1': {'gamma': 10, 'delta': 25},
            'position_2': {'gamma': -15, 'delta': -30}
        }
        
    def _get_spot_price(self) -> float:
        """Get current spot price."""
        return 450.0  # Placeholder
        
    # ==========================================================================
    # PRIVATE METHODS - PROTECTION PROTOCOLS
    # ==========================================================================
    def _apply_light_protection(self) -> List[VolProtocolAction]:
        """Apply light protection measures."""
        return [
            VolProtocolAction(
                timestamp=datetime.now(),
                action_type='TIGHTEN_STOPS',
                urgency='SOON',
                details={'stop_tightening': 0.2},  # 20% tighter
                reason='Light protection protocol'
            )
        ]
        
    def _apply_moderate_protection(self) -> List[VolProtocolAction]:
        """Apply moderate protection measures."""
        actions = []
        
        # Reduce position sizes
        actions.append(VolProtocolAction(
            timestamp=datetime.now(),
            action_type='REDUCE_SIZE',
            urgency='SOON',
            details={'reduction_percent': 0.25},
            reason='Moderate protection protocol'
        ))
        
        # Add volatility hedge
        actions.append(VolProtocolAction(
            timestamp=datetime.now(),
            action_type='ADD_VOL_HEDGE',
            urgency='SOON',
            details={
                'hedge_type': 'VIX_CALLS',
                'hedge_size': 0.25
            },
            reason='Volatility hedge for protection'
        ))
        
        return actions
        
    def _apply_heavy_protection(self) -> List[VolProtocolAction]:
        """Apply heavy protection measures."""
        actions = []
        
        # Significant position reduction
        actions.append(VolProtocolAction(
            timestamp=datetime.now(),
            action_type='REDUCE_SIZE',
            urgency='IMMEDIATE',
            details={'reduction_percent': 0.50},
            reason='Heavy protection protocol'
        ))
        
        # Close risky positions
        actions.append(VolProtocolAction(
            timestamp=datetime.now(),
            action_type='CLOSE_RISKY',
            urgency='IMMEDIATE',
            details={'risk_threshold': 'HIGH'},
            reason='Close high-risk positions'
        ))
        
        return actions
        
    def _apply_maximum_protection(self) -> List[VolProtocolAction]:
        """Apply maximum protection measures."""
        return [
            VolProtocolAction(
                timestamp=datetime.now(),
                action_type='EMERGENCY_LIQUIDATION',
                urgency='IMMEDIATE',
                details={
                    'liquidate_percent': 0.75,
                    'preserve_hedges': True
                },
                reason='Maximum protection - emergency conditions'
            )
        ]
        
    def _determine_protection_level(self, signal: VolRiskSignal, 
                                   metrics: VolatilityMetrics) -> ProtectionLevel:
        """Determine appropriate protection level."""
        if signal == VolRiskSignal.CRITICAL:
            return ProtectionLevel.MAXIMUM
        elif signal == VolRiskSignal.DANGER:
            return ProtectionLevel.HEAVY
        elif signal == VolRiskSignal.WARNING:
            return ProtectionLevel.MODERATE
        elif signal == VolRiskSignal.CAUTION:
            return ProtectionLevel.LIGHT
        else:
            return ProtectionLevel.NONE
            
    def _calculate_optimal_hedge_ratio(self, metrics: VolatilityMetrics,
                                     signal: VolRiskSignal) -> float:
        """Calculate optimal hedge ratio based on conditions."""
        base_ratio = 0.0
        
        # VIX level component
        if metrics.vix_level > VIX_SPIKE_THRESHOLD:
            base_ratio += 0.5
        elif metrics.vix_level > VIX_ELEVATED:
            base_ratio += 0.25
            
        # Risk signal component
        if signal == VolRiskSignal.CRITICAL:
            base_ratio += 0.25
        elif signal == VolRiskSignal.DANGER:
            base_ratio += 0.15
            
        # Vol of vol component
        if metrics.vol_of_vol > 100:
            base_ratio += 0.1
            
        return min(base_ratio, 0.75)  # Cap at 75% hedge
        
    # ==========================================================================
    # PRIVATE METHODS - RECOMMENDATIONS
    # ==========================================================================
    def _generate_vix_recommendations(self, vix: float, roc: float, 
                                    protection: ProtectionLevel) -> List[str]:
        """Generate VIX-based recommendations."""
        recommendations = []
        
        if vix > VIX_SPIKE_THRESHOLD:
            recommendations.append("VIX spike detected - reduce short vol exposure")
            recommendations.append("Consider VIX puts for mean reversion")
            
        if abs(roc) > VIX_RATE_OF_CHANGE_THRESHOLD:
            if roc > 0:
                recommendations.append("Rapid VIX increase - add protection")
            else:
                recommendations.append("Rapid VIX decrease - potential vol selling opportunity")
                
        if protection == ProtectionLevel.MAXIMUM:
            recommendations.append("Maximum protection active - avoid new positions")
            
        return recommendations
        
    def _generate_surface_recommendations(self, vega_breach: bool, volga_breach: bool,
                                        vanna_breach: bool, skew_risk: Dict) -> List[str]:
        """Generate vol surface recommendations."""
        recommendations = []
        
        if vega_breach:
            recommendations.append("Vega limit breach - reduce volatility exposure")
            
        if volga_breach:
            recommendations.append("High volga exposure - risk from vol-of-vol changes")
            
        if vanna_breach:
            recommendations.append("High vanna exposure - risk from spot/vol correlation")
            
        if skew_risk['risk_level'] == 'HIGH':
            recommendations.append(f"Extreme skew detected - {skew_risk['directional_bias']}")
            
        return recommendations
        
    def _assess_overall_health(self, risk: VolatilityRisk, 
                             metrics: VolatilityMetrics) -> str:
        """Assess overall volatility health status."""
        if risk.risk_signal == VolRiskSignal.CRITICAL:
            return 'CRITICAL'
        elif risk.risk_signal == VolRiskSignal.DANGER:
            return 'STRESSED'
        elif metrics.regime == VolatilityRegime.EXTREME:
            return 'STRESSED'
        else:
            return 'HEALTHY'
            
    def _emit_protection_event(self, level: ProtectionLevel, 
                             actions: List[VolProtocolAction]) -> None:
        """Emit protection protocol event."""
        event_data = {
            'type': 'volatility_protection',
            'timestamp': datetime.now(),
            'protection_level': level.value,
            'actions_count': len(actions),
            'actions': [
                {
                    'type': a.action_type,
                    'urgency': a.urgency,
                    'reason': a.reason
                }
                for a in actions
            ]
        }
        
        self.event_manager.emit(Event(EventType.RISK_ALERT, event_data))
        
    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start volatility risk monitoring."""
        if self._running:
            self.logger.warning("Volatility monitoring already running")
            return
            
        self._running = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="VolRiskMonitor"
        )
        self._monitoring_thread.start()
        self.logger.info("Volatility risk monitoring started")
        
    def stop_monitoring(self) -> None:
        """Stop volatility risk monitoring."""
        self._running = False
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
            
        self.logger.info("Volatility risk monitoring stopped")
        
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Assess risk
                risk_profile = self.assess_volatility_risk()
                
                # Check for critical conditions
                if risk_profile.risk_assessment.risk_signal == VolRiskSignal.CRITICAL:
                    self.logger.critical("CRITICAL volatility risk detected!")
                    self.activate_protection_protocol(ProtectionLevel.MAXIMUM)
                    
                # Check for protection triggers
                elif risk_profile.risk_assessment.protection_needed != self.protection_level:
                    self.activate_protection_protocol(risk_profile.risk_assessment.protection_needed)
                    
                # Sleep based on regime
                if risk_profile.metrics.regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
                    time.sleep(30)  # More frequent in high vol
                else:
                    time.sleep(60)  # Normal frequency
                    
            except Exception as e:
                self.logger.error(f"Error in volatility monitoring: {e}")
                time.sleep(60)
                
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_monitoring()
        self.logger.info("Volatility risk manager cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_volatility_risk_manager(config: Optional[Dict] = None) -> VolatilityRiskManager:
    """
    Create and return a VolatilityRiskManager instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured VolatilityRiskManager instance
    """
    return VolatilityRiskManager(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    vol_risk_mgr = create_volatility_risk_manager()
    
    try:
        vol_risk_mgr.start_monitoring()
        
        # Assess current risk
        risk_profile = vol_risk_mgr.assess_volatility_risk()
        
        print("\n📊 Volatility Risk Profile:")
        print(f"  Regime: {risk_profile.metrics.regime.value}")
        print(f"  VIX Level: {risk_profile.metrics.vix_level:.1f}")
        print(f"  Risk Signal: {risk_profile.risk_assessment.risk_signal.name}")
        print(f"  Protection: {risk_profile.risk_assessment.protection_needed.value}")
        print(f"  Overall Health: {risk_profile.overall_health}")
        
        # Show risk factors
        if risk_profile.risk_assessment.risk_factors:
            print("\n⚠️ Risk Factors:")
            for factor in risk_profile.risk_assessment.risk_factors:
                print(f"  - {factor}")
                
        # Show Greek exposures
        print(f"\n📈 Greek Exposures:")
        print(f"  Vega: ${risk_profile.risk_assessment.vega_exposure:,.0f}")
        print(f"  Volga: ${risk_profile.risk_assessment.volga_exposure:,.0f}")
        print(f"  Vanna: ${risk_profile.risk_assessment.vanna_exposure:,.0f}")
        
        # Test position sizing
        print(f"\n📏 Position Size Adjustments:")
        base_size = 100
        adjusted = vol_risk_mgr.calculate_regime_position_size(base_size)
        print(f"  Base Size: {base_size}")
        print(f"  Adjusted Size: {adjusted}")
        print(f"  Multiplier: {adjusted/base_size:.2f}x")
        
        # Test VIX protection
        vix_status = vol_risk_mgr.get_vix_protection_status()
        print(f"\n🛡️ VIX Protection Status:")
        print(f"  Current VIX: {vix_status['current_vix']:.1f}")
        print(f"  Protection Level: {vix_status['protection_level']}")
        print(f"  Hedge Ratio: {vix_status['hedge_ratio']:.1%}")
        
        # Test gamma scalping
        print(f"\n🎯 Gamma Scalping Plans:")
        for plan in risk_profile.scalping_plans[:3]:
            print(f"  Action: {plan.action.value}")
            print(f"  Current Delta: {plan.current_delta:+.1f}")
            print(f"  Hedge Needed: {plan.hedge_needed:+.0f} shares")
            print(f"  Expected Profit: ${plan.expected_profit:.0f}")
            print()
            
        # Test protection actions
        if risk_profile.protection_actions:
            print(f"\n🚨 Protection Actions Required:")
            for action in risk_profile.protection_actions:
                print(f"  Type: {action.action_type}")
                print(f"  Urgency: {action.urgency}")
                print(f"  Reason: {action.reason}")
                print()
                
        time.sleep(5)
        
    finally:
        vol_risk_mgr.cleanup()
        print("\n✅ Volatility risk manager test completed")============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import PositionSide, TimeFrame
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from SpyderE_Risk.SpyderE02_PositionSizer import get_position_sizer
from SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer
from SpyderN_OptionsAnalytics.SpyderN08_VolatilitySurface import VolatilitySurfaceAnalyzer
from SpyderN_OptionsAnalytics.SpyderN09_GammaExposure import GammaExposureCalculator
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# VIX Spike Protection
VIX_NORMAL_RANGE = (12, 20)
VIX_ELEVATED = 25
VIX_SPIKE_THRESHOLD = 30
VIX_EXTREME_SPIKE = 40
VIX_RATE_OF_CHANGE_THRESHOLD = 0.20  # 20% daily change

# Volatility Regimes
VOL_REGIME_THRESHOLDS = {
    'ULTRA_LOW': 10,
    'LOW': 15,
    'NORMAL': 20,
    'ELEVATED': 25,
    'HIGH': 30,
    'EXTREME': 40
}

# Position Sizing Adjustments
VOL_POSITION_MULTIPLIERS = {
    'ULTRA_LOW': 1.5,   # Increase size in low vol
    'LOW': 1.2,
    'NORMAL': 1.0,
    'ELEVATED': 0.8,
    'HIGH': 0.5,
    'EXTREME': 0.25     # Dramatically reduce in extreme vol
}

# Gamma Scalping Parameters
GAMMA_SCALP_THRESHOLD = 0.002  # 0.2% move triggers scalp
GAMMA_BAND_WIDTH = 0.005       # 0.5% bands
MIN_SCALP_PROFIT = 50          # Minimum profit per scalp

# Vol Surface Risk Limits
MAX_VEGA_EXPOSURE = 100000     # $100K vega limit
MAX_VOLGA_EXPOSURE = 50000     # $50K volga limit
MAX_VANNA_EXPOSURE = 75000     # $75K vanna limit
SKEW_RISK_THRESHOLD = 0.15    # 15% skew considered risky

# Protection Protocols
HEDGING_LEVELS = {
    'NORMAL': 0.0,      # No hedge
    'ELEVATED': 0.25,   # 25% hedge
    'HIGH': 0.50,       # 50% hedge
    'EXTREME': 0.75     # 75% hedge
}

# ==