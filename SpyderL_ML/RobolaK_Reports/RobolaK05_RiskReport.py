#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderK05_RiskReport.py
Group: K (Reporting)
Purpose: Risk metrics reporting and analysis

Description:
    This module generates comprehensive risk reports including position
    analysis, portfolio Greeks, margin utilization, stress testing,
    and risk-adjusted performance metrics.

Author: Mohamed Talib
Date: 2025-05-30
Version: 1.0.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
CHART_DPI = 100
CHART_SIZE = (10, 6)

# Risk thresholds
MAX_PORTFOLIO_DELTA = 100
MAX_POSITION_SIZE_PCT = 0.20  # 20% of portfolio
MAX_SECTOR_EXPOSURE = 0.30    # 30% in one sector
MAX_MARGIN_USAGE = 0.70       # 70% margin utilization

# Stress test scenarios
STRESS_SCENARIOS = {
    'market_crash': {'spy_move': -0.10, 'vix_spike': 2.0},
    'correction': {'spy_move': -0.05, 'vix_spike': 1.5},
    'volatility_spike': {'spy_move': 0, 'vix_spike': 2.0},
    'rally': {'spy_move': 0.05, 'vix_spike': -0.5},
    'flash_crash': {'spy_move': -0.07, 'vix_spike': 3.0}
}

# Risk score weights
RISK_WEIGHTS = {
    'position_concentration': 0.20,
    'margin_utilization': 0.25,
    'portfolio_greeks': 0.20,
    'volatility_exposure': 0.15,
    'correlation_risk': 0.10,
    'liquidity_risk': 0.10
}

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk levels for categorization"""
    LOW = auto()
    MODERATE = auto()
    ELEVATED = auto()
    HIGH = auto()
    CRITICAL = auto()

class ReportType(Enum):
    """Types of risk reports"""
    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    ON_DEMAND = auto()

class RiskCategory(Enum):
    """Risk categories"""
    MARKET_RISK = auto()
    CONCENTRATION_RISK = auto()
    LIQUIDITY_RISK = auto()
    OPERATIONAL_RISK = auto()
    COUNTERPARTY_RISK = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class PositionRisk:
    """Risk metrics for individual position"""
    symbol: str
    quantity: int
    market_value: float
    delta: float
    gamma: float
    theta: float
    vega: float
    position_pnl: float
    unrealized_pnl: float
    percent_of_portfolio: float
    days_held: int
    stop_loss_distance: float
    risk_score: float

class PortfolioRisk:
    """Portfolio-level risk metrics"""
    total_market_value: float
    net_liquidation_value: float
    gross_position_value: float
    net_position_value: float
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_theta: float
    portfolio_vega: float
    portfolio_beta: float
    correlation_risk: float
    concentration_risk: float
    var_95: float  # Value at Risk
    cvar_95: float  # Conditional VaR
    max_drawdown: float
    margin_used: float
    margin_available: float
    buying_power: float

class StressTestResult:
    """Results from stress testing"""
    scenario_name: str
    spy_move: float
    vix_change: float
    portfolio_impact: float
    position_impacts: Dict[str, float]
    margin_impact: float
    would_trigger_margin_call: bool
    worst_case_loss: float

class RiskAlert:
    """Risk alert/warning"""
    alert_type: str
    severity: RiskLevel
    message: str
    metric_value: float
    threshold_value: float
    recommended_action: str

class RiskReportData:
    """Complete risk report data"""
    report_timestamp: datetime
    report_type: ReportType
    portfolio_risk: PortfolioRisk
    position_risks: List[PositionRisk]
    stress_test_results: List[StressTestResult]
    risk_alerts: List[RiskAlert]
    risk_score: float
    risk_level: RiskLevel
    historical_metrics: pd.DataFrame
    recommendations: List[str]

# ==============================================================================
# RISK REPORT GENERATOR CLASS
# ==============================================================================
class RiskReportGenerator:
    """
    Generates comprehensive risk analysis reports.
    
    Features:
    - Position-level risk analysis
    - Portfolio Greeks aggregation
    - Stress testing
    - Risk scoring
    - Historical risk trends
    - Actionable recommendations
    """
    
    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize risk report generator.
        
        Args:
            database_manager: Database manager instance
        """
        self.db = database_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.greeks_calculator = GreeksCalculator()
        
        # Setup output directory
        REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Chart settings
        plt.style.use('seaborn-v0_8-darkgrid')
        warnings.filterwarnings('ignore', category=FutureWarning)
        
        self.logger.info("RiskReportGenerator initialized")
    
    # ==========================================================================
    # MAIN REPORT GENERATION
    # ==========================================================================
    def generate_report(
        self,
        report_type: ReportType = ReportType.DAILY,
        output_formats: List[str] = None
    ) -> Dict[str, Path]:
        """
        Generate risk report in specified formats.
        
        Args:
            report_type: Type of report to generate
            output_formats: List of output formats (pdf, html, json)
            
        Returns:
            Dictionary mapping format to file path
        """
        try:
            # Default formats
            if output_formats is None:
                output_formats = ['pdf', 'html']
            
            self.logger.info(f"Generating {report_type.name} risk report")
            
            # Collect risk data
            report_data = self._collect_risk_data(report_type)
            
            # Generate reports
            output_files = {}
            
            if 'pdf' in output_formats:
                output_files['pdf'] = self._generate_pdf_report(report_data)
            
            if 'html' in output_formats:
                output_files['html'] = self._generate_html_report(report_data)
            
            if 'json' in output_formats:
                output_files['json'] = self._generate_json_report(report_data)
            
            # Send alerts if critical risks found
            self._check_and_send_alerts(report_data)
            
            self.logger.info(f"Risk report generated: {list(output_files.values())}")
            
            return output_files
            
        except Exception as e:
            self.logger.error(f"Error generating risk report: {e}")
            self.error_handler.handle_error(e, "generate_report")
            return {}
    
    # ==========================================================================
    # DATA COLLECTION
    # ==========================================================================
    def _collect_risk_data(self, report_type: ReportType) -> RiskReportData:
        """Collect all risk-related data"""
        timestamp = datetime.now()
        
        # Get current positions
        positions = self.db.get_positions(timestamp)
        positions_df = pd.DataFrame(positions)
        
        # Get account data
        account_data = self.db.get_account_snapshot(timestamp)
        
        # Calculate portfolio risk
        portfolio_risk = self._calculate_portfolio_risk(positions_df, account_data)
        
        # Calculate position risks
        position_risks = self._calculate_position_risks(positions_df, portfolio_risk)
        
        # Run stress tests
        stress_results = self._run_stress_tests(positions_df, portfolio_risk)
        
        # Generate risk alerts
        risk_alerts = self._generate_risk_alerts(
            portfolio_risk,
            position_risks,
            stress_results
        )
        
        # Calculate overall risk score
        risk_score = self._calculate_risk_score(
            portfolio_risk,
            position_risks,
            stress_results
        )
        
        # Determine risk level
        risk_level = self._determine_risk_level(risk_score)
        
        # Get historical metrics
        historical_metrics = self._get_historical_risk_metrics(report_type)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            portfolio_risk,
            position_risks,
            risk_alerts,
            risk_level
        )
        
        return RiskReportData(
            report_timestamp=timestamp,
            report_type=report_type,
            portfolio_risk=portfolio_risk,
            position_risks=position_risks,
            stress_test_results=stress_results,
            risk_alerts=risk_alerts,
            risk_score=risk_score,
            risk_level=risk_level,
            historical_metrics=historical_metrics,
            recommendations=recommendations
        )
    
    def _calculate_portfolio_risk(
        self,
        positions: pd.DataFrame,
        account_data: Dict[str, Any]
    ) -> PortfolioRisk:
        """Calculate portfolio-level risk metrics"""
        if positions.empty:
            return PortfolioRisk(
                total_market_value=account_data.get('net_liquidation_value', 0),
                net_liquidation_value=account_data.get('net_liquidation_value', 0),
                gross_position_value=0,
                net_position_value=0,
                portfolio_delta=0,
                portfolio_gamma=0,
                portfolio_theta=0,
                portfolio_vega=0,
                portfolio_beta=1.0,
                correlation_risk=0,
                concentration_risk=0,
                var_95=0,
                cvar_95=0,
                max_drawdown=0,
                margin_used=account_data.get('margin_used', 0),
                margin_available=account_data.get('margin_available', 0),
                buying_power=account_data.get('buying_power', 0)
            )
        
        # Calculate position values
        positions['market_value'] = positions['quantity'] * positions['current_price']
        gross_value = positions['market_value'].abs().sum()
        net_value = positions['market_value'].sum()
        
        # Aggregate Greeks
        portfolio_delta = positions['delta'].sum() if 'delta' in positions else 0
        portfolio_gamma = positions['gamma'].sum() if 'gamma' in positions else 0
        portfolio_theta = positions['theta'].sum() if 'theta' in positions else 0
        portfolio_vega = positions['vega'].sum() if 'vega' in positions else 0
        
        # Calculate concentration risk
        max_position = positions['market_value'].abs().max()
        concentration_risk = max_position / gross_value if gross_value > 0 else 0
        
        # Calculate VaR (simplified)
        # Would use historical returns in production
        portfolio_vol = 0.02  # 2% daily volatility assumption
        var_95 = account_data['net_liquidation_value'] * portfolio_vol * 1.645
        cvar_95 = var_95 * 1.2  # Simplified CVaR
        
        # Get historical max drawdown
        max_drawdown = self._calculate_max_drawdown()
        
        return PortfolioRisk(
            total_market_value=account_data.get('net_liquidation_value', 0),
            net_liquidation_value=account_data.get('net_liquidation_value', 0),
            gross_position_value=gross_value,
            net_position_value=net_value,
            portfolio_delta=portfolio_delta,
            portfolio_gamma=portfolio_gamma,
            portfolio_theta=portfolio_theta,
            portfolio_vega=portfolio_vega,
            portfolio_beta=1.0,  # Would calculate vs SPY
            correlation_risk=self._calculate_correlation_risk(positions),
            concentration_risk=concentration_risk,
            var_95=var_95,
            cvar_95=cvar_95,
            max_drawdown=max_drawdown,
            margin_used=account_data.get('margin_used', 0),
            margin_available=account_data.get('margin_available', 0),
            buying_power=account_data.get('buying_power', 0)
        )
    
    def _calculate_position_risks(
        self,
        positions: pd.DataFrame,
        portfolio_risk: PortfolioRisk
    ) -> List[PositionRisk]:
        """Calculate risk metrics for each position"""
        position_risks = []
        
        for _, position in positions.iterrows():
            market_value = position['quantity'] * position['current_price']
            
            # Calculate position-specific metrics
            percent_of_portfolio = (
                abs(market_value) / portfolio_risk.total_market_value
                if portfolio_risk.total_market_value > 0 else 0
            )
            
            # Days held
            if 'entry_time' in position:
                days_held = (datetime.now() - pd.to_datetime(position['entry_time'])).days
            else:
                days_held = 0
            
            # Stop loss distance
            if 'stop_loss' in position and position['stop_loss'] > 0:
                stop_distance = abs(position['current_price'] - position['stop_loss']) / position['current_price']
            else:
                stop_distance = 0.10  # Default 10%
            
            # Position risk score
            position_risk_score = self._calculate_position_risk_score(
                percent_of_portfolio,
                stop_distance,
                days_held,
                position.get('unrealized_pnl', 0)
            )
            
            position_risk = PositionRisk(
                symbol=position['symbol'],
                quantity=position['quantity'],
                market_value=market_value,
                delta=position.get('delta', 0),
                gamma=position.get('gamma', 0),
                theta=position.get('theta', 0),
                vega=position.get('vega', 0),
                position_pnl=position.get('realized_pnl', 0),
                unrealized_pnl=position.get('unrealized_pnl', 0),
                percent_of_portfolio=percent_of_portfolio,
                days_held=days_held,
                stop_loss_distance=stop_distance,
                risk_score=position_risk_score
            )
            
            position_risks.append(position_risk)
        
        # Sort by risk score
        position_risks.sort(key=lambda x: x.risk_score, reverse=True)
        
        return position_risks
    
    def _run_stress_tests(
        self,
        positions: pd.DataFrame,
        portfolio_risk: PortfolioRisk
    ) -> List[StressTestResult]:
        """Run stress test scenarios"""
        stress_results = []
        
        for scenario_name, scenario in STRESS_SCENARIOS.items():
            spy_move = scenario['spy_move']
            vix_spike = scenario['vix_spike']
            
            # Calculate portfolio impact
            # Simplified: use delta for SPY move, vega for VIX
            spy_impact = portfolio_risk.portfolio_delta * spy_move * 450  # Assume SPY at 450
            
            # VIX impact (1 point VIX = ~3% IV change)
            iv_change = vix_spike * 0.03
            vix_impact = portfolio_risk.portfolio_vega * iv_change
            
            portfolio_impact = spy_impact + vix_impact
            
            # Position-level impacts
            position_impacts = {}
            for _, position in positions.iterrows():
                pos_spy_impact = position.get('delta', 0) * spy_move * position['current_price']
                pos_vix_impact = position.get('vega', 0) * iv_change
                position_impacts[position['symbol']] = pos_spy_impact + pos_vix_impact
            
            # Margin impact
            margin_impact = abs(portfolio_impact) * 0.5  # Assume 50% margin requirement
            new_margin_used = portfolio_risk.margin_used + margin_impact
            
            # Check margin call
            total_margin = portfolio_risk.margin_used + portfolio_risk.margin_available
            would_trigger_margin_call = new_margin_used > total_margin * 0.9
            
            # Worst case loss (portfolio impact + forced liquidation)
            worst_case_loss = portfolio_impact
            if would_trigger_margin_call:
                worst_case_loss *= 1.2  # 20% additional loss from forced liquidation
            
            result = StressTestResult(
                scenario_name=scenario_name,
                spy_move=spy_move,
                vix_change=vix_spike,
                portfolio_impact=portfolio_impact,
                position_impacts=position_impacts,
                margin_impact=margin_impact,
                would_trigger_margin_call=would_trigger_margin_call,
                worst_case_loss=worst_case_loss
            )
            
            stress_results.append(result)
        
        return stress_results
    
    def _generate_risk_alerts(
        self,
        portfolio_risk: PortfolioRisk,
        position_risks: List[PositionRisk],
        stress_results: List[StressTestResult]
    ) -> List[RiskAlert]:
        """Generate risk alerts based on thresholds"""
        alerts = []
        
        # Portfolio delta alert
        if abs(portfolio_risk.portfolio_delta) > MAX_PORTFOLIO_DELTA:
            alerts.append(RiskAlert(
                alert_type='portfolio_delta',
                severity=RiskLevel.HIGH,
                message=f"Portfolio delta ({portfolio_risk.portfolio_delta:.0f}) exceeds limit",
                metric_value=portfolio_risk.portfolio_delta,
                threshold_value=MAX_PORTFOLIO_DELTA,
                recommended_action="Consider delta hedging or reducing directional exposure"
            ))
        
        # Margin utilization alert
        margin_utilization = portfolio_risk.margin_used / (
            portfolio_risk.margin_used + portfolio_risk.margin_available
        ) if portfolio_risk.margin_available > 0 else 1.0
        
        if margin_utilization > MAX_MARGIN_USAGE:
            alerts.append(RiskAlert(
                alert_type='margin_utilization',
                severity=RiskLevel.CRITICAL if margin_utilization > 0.85 else RiskLevel.HIGH,
                message=f"High margin utilization ({margin_utilization:.1%})",
                metric_value=margin_utilization,
                threshold_value=MAX_MARGIN_USAGE,
                recommended_action="Reduce positions or add capital to avoid margin call"
            ))
        
        # Position concentration alerts
        for position in position_risks:
            if position.percent_of_portfolio > MAX_POSITION_SIZE_PCT:
                alerts.append(RiskAlert(
                    alert_type='position_concentration',
                    severity=RiskLevel.ELEVATED,
                    message=f"{position.symbol} is {position.percent_of_portfolio:.1%} of portfolio",
                    metric_value=position.percent_of_portfolio,
                    threshold_value=MAX_POSITION_SIZE_PCT,
                    recommended_action=f"Consider reducing {position.symbol} position size"
                ))
        
        # Stress test alerts
        for result in stress_results:
            loss_pct = abs(result.worst_case_loss) / portfolio_risk.total_market_value
            if loss_pct > 0.10:  # 10% loss threshold
                alerts.append(RiskAlert(
                    alert_type='stress_test',
                    severity=RiskLevel.HIGH if loss_pct > 0.15 else RiskLevel.ELEVATED,
                    message=f"{result.scenario_name} scenario: {loss_pct:.1%} potential loss",
                    metric_value=loss_pct,
                    threshold_value=0.10,
                    recommended_action="Review hedging strategies for tail risk protection"
                ))
        
        # Sort by severity
        severity_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.ELEVATED: 2,
            RiskLevel.MODERATE: 3,
            RiskLevel.LOW: 4
        }
        alerts.sort(key=lambda x: severity_order[x.severity])
        
        return alerts
    
    def _calculate_risk_score(
        self,
        portfolio_risk: PortfolioRisk,
        position_risks: List[PositionRisk],
        stress_results: List[StressTestResult]
    ) -> float:
        """Calculate overall risk score (0-100)"""
        scores = {}
        
        # Position concentration score
        if position_risks:
            max_concentration = max(p.percent_of_portfolio for p in position_risks)
            scores['position_concentration'] = min(100, max_concentration / MAX_POSITION_SIZE_PCT * 100)
        else:
            scores['position_concentration'] = 0
        
        # Margin utilization score
        margin_util = portfolio_risk.margin_used / (
            portfolio_risk.margin_used + portfolio_risk.margin_available
        ) if portfolio_risk.margin_available > 0 else 1.0
        scores['margin_utilization'] = min(100, margin_util / MAX_MARGIN_USAGE * 100)
        
        # Portfolio Greeks score
        delta_score = min(100, abs(portfolio_risk.portfolio_delta) / MAX_PORTFOLIO_DELTA * 100)
        scores['portfolio_greeks'] = delta_score
        
        # Volatility exposure score (based on vega)
        vega_score = min(100, abs(portfolio_risk.portfolio_vega) / 1000 * 100)  # $1000 vega as max
        scores['volatility_exposure'] = vega_score
        
        # Correlation risk score
        scores['correlation_risk'] = portfolio_risk.correlation_risk * 100
        
        # Liquidity risk score (placeholder)
        scores['liquidity_risk'] = 20  # Would calculate based on position sizes vs avg volume
        
        # Calculate weighted average
        total_score = 0
        for category, weight in RISK_WEIGHTS.items():
            total_score += scores.get(category, 0) * weight
        
        return min(100, total_score)
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level based on score"""
        if risk_score < 20:
            return RiskLevel.LOW
        elif risk_score < 40:
            return RiskLevel.MODERATE
        elif risk_score < 60:
            return RiskLevel.ELEVATED
        elif risk_score < 80:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _get_historical_risk_metrics(self, report_type: ReportType) -> pd.DataFrame:
        """Get historical risk metrics"""
        # Determine lookback period
        if report_type == ReportType.DAILY:
            lookback_days = 30
        elif report_type == ReportType.WEEKLY:
            lookback_days = 90
        else:
            lookback_days = 365
        
        # This would fetch from database
        # For now, generate sample data
        dates = pd.date_range(
            end=datetime.now(),
            periods=lookback_days,
            freq='D'
        )
        
        np.random.seed(42)
        data = {
            'date': dates,
            'risk_score': np.random.uniform(20, 60, lookback_days),
            'portfolio_delta': np.random.normal(0, 50, lookback_days),
            'margin_utilization': np.random.uniform(0.3, 0.7, lookback_days),
            'var_95': np.random.uniform(5000, 15000, lookback_days)
        }
        
        return pd.DataFrame(data)
    
    def _generate_recommendations(
        self,
        portfolio_risk: PortfolioRisk,
        position_risks: List[PositionRisk],
        risk_alerts: List[RiskAlert],
        risk_level: RiskLevel
    ) -> List[str]:
        """Generate actionable risk management recommendations"""
        recommendations = []
        
        # Risk level based recommendations
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("⚠️ IMMEDIATE ACTION REQUIRED: Risk levels are elevated")
            recommendations.append("Consider reducing overall position sizes by 30-50%")
        
        # Alert-based recommendations
        for alert in risk_alerts[:3]:  # Top 3 alerts
            recommendations.append(f"• {alert.recommended_action}")
        
        # Portfolio delta recommendations
        if abs(portfolio_risk.portfolio_delta) > 50:
            if portfolio_risk.portfolio_delta > 0:
                recommendations.append("Portfolio is too bullish - consider buying puts or selling calls")
            else:
                recommendations.append("Portfolio is too bearish - consider buying calls or selling puts")
        
        # Margin recommendations
        margin_util = portfolio_risk.margin_used / (
            portfolio_risk.margin_used + portfolio_risk.margin_available
        ) if portfolio_risk.margin_available > 0 else 1.0
        
        if margin_util > 0.5:
            recommendations.append(f"Margin utilization at {margin_util:.0%} - maintain buffer for market moves")
        
        # Concentration recommendations
        concentrated_positions = [p for p in position_risks if p.percent_of_portfolio > 0.15]
        if concentrated_positions:
            symbols = ', '.join([p.symbol for p in concentrated_positions[:3]])
            recommendations.append(f"Reduce concentration in: {symbols}")
        
        # Greeks recommendations
        if abs(portfolio_risk.portfolio_gamma) > 10:
            recommendations.append("High gamma exposure - consider gamma hedging")
        
        if portfolio_risk.portfolio_theta < -100:
            recommendations.append("Significant theta decay - review time-sensitive positions")
        
        return recommendations
    
    # ==========================================================================
    # UTILITY CALCULATIONS
    # ==========================================================================
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from historical data"""
        # This would use actual equity curve
        # For now, return placeholder
        return 0.08  # 8% max drawdown
    
    def _calculate_correlation_risk(self, positions: pd.DataFrame) -> float:
        """Calculate portfolio correlation risk"""
        # This would calculate actual correlations
        # For now, return placeholder based on position count
        if len(positions) < 3:
            return 0.8  # High correlation risk with few positions
        elif len(positions) < 10:
            return 0.5
        else:
            return 0.3
    
    def _calculate_position_risk_score(
        self,
        percent_of_portfolio: float,
        stop_distance: float,
        days_held: int,
        unrealized_pnl: float
    ) -> float:
        """Calculate risk score for individual position"""
        # Size risk
        size_score = min(100, percent_of_portfolio / 0.20 * 100)
        
        # Stop loss risk
        stop_score = min(100, (1 - stop_distance) * 100) if stop_distance > 0 else 100
        
        # Time risk (positions get riskier over time for options)
        time_score = min(100, days_held / 30 * 100)
        
        # P&L risk (losing positions are riskier)
        pnl_score = 50 if unrealized_pnl >= 0 else min(100, 50 + abs(unrealized_pnl) / 1000 * 50)
        
        # Weighted average
        weights = [0.4, 0.3, 0.1, 0.2]
        scores = [size_score, stop_score, time_score, pnl_score]
        
        return sum(w * s for w, s in zip(weights, scores))
    
    # ==========================================================================
    # REPORT GENERATION - PDF
    # ==========================================================================
    def _generate_pdf_report(self, data: RiskReportData) -> Path:
        """Generate PDF risk report"""
        filename = f"risk_report_{data.report_timestamp.strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = REPORT_OUTPUT_DIR / filename
        
        # Create PDF document
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build content
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#d32f2f') if data.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] else colors.HexColor('#1976d2')
        )
        
        # Title
        story.append(Paragraph(
            f"Risk Analysis Report - {data.risk_level.name}",
            title_style
        ))
        story.append(Spacer(1, 0.3 * inch))
        
        # Risk summary
        story.extend(self._create_pdf_risk_summary(data, styles))
        story.append(PageBreak())
        
        # Portfolio risk
        story.extend(self._create_pdf_portfolio_risk(data, styles))
        story.append(PageBreak())
        
        # Position risks
        story.extend(self._create_pdf_position_risks(data, styles))
        story.append(PageBreak())
        
        # Stress tests
        story.extend(self._create_pdf_stress_tests(data, styles))
        
        # Build PDF
        doc.build(story)
        
        return filepath
    
    def _create_pdf_risk_summary(self, data: RiskReportData, styles) -> List[Any]:
        """Create PDF risk summary section"""
        elements = []
        
        # Header
        elements.append(Paragraph("Executive Risk Summary", styles['Heading1']))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Risk score visualization
        risk_chart = self._create_risk_score_chart(data.risk_score, data.risk_level)
        elements.append(Image(risk_chart, width=4 * inch, height=2 * inch))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Key metrics
        metrics_data = [
            ['Risk Metric', 'Value', 'Status'],
            ['Overall Risk Score', f"{data.risk_score:.0f}/100", self._get_status_indicator(data.risk_level)],
            ['Portfolio Delta', f"{data.portfolio_risk.portfolio_delta:.0f}", self._get_delta_status(data.portfolio_risk.portfolio_delta)],
            ['Margin Utilization', f"{data.portfolio_risk.margin_used / (data.portfolio_risk.margin_used + data.portfolio_risk.margin_available):.1%}", self._get_margin_status(data.portfolio_risk)],
            ['Value at Risk (95%)', f"${data.portfolio_risk.var_95:,.0f}", ''],
            ['Max Position Size', f"{max(p.percent_of_portfolio for p in data.position_risks):.1%}" if data.position_risks else "0%", '']
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2.5 * inch, 1.5 * inch, 1 * inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(metrics_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Top alerts
        if data.risk_alerts:
            elements.append(Paragraph("Critical Risk Alerts", styles['Heading2']))
            for alert in data.risk_alerts[:3]:
                alert_text = f"• <font color='red'>⚠️</font> {alert.message}"
                elements.append(Paragraph(alert_text, styles['Normal']))
            elements.append(Spacer(1, 0.2 * inch))
        
        # Recommendations
        if data.recommendations:
            elements.append(Paragraph("Immediate Actions Required", styles['Heading2']))
            for rec in data.recommendations[:5]:
                elements.append(Paragraph(rec, styles['Normal']))
        
        return elements
    
    def _create_pdf_portfolio_risk(self, data: RiskReportData, styles) -> List[Any]:
        """Create PDF portfolio risk section"""
        elements = []
        
        elements.append(Paragraph("Portfolio Risk Analysis", styles['Heading1']))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Greeks table
        greeks_data = [
            ['Greek', 'Value', 'Interpretation'],
            ['Delta', f"{data.portfolio_risk.portfolio_delta:.1f}", self._interpret_delta(data.portfolio_risk.portfolio_delta)],
            ['Gamma', f"{data.portfolio_risk.portfolio_gamma:.2f}", self._interpret_gamma(data.portfolio_risk.portfolio_gamma)],
            ['Theta', f"${data.portfolio_risk.portfolio_theta:.0f}", self._interpret_theta(data.portfolio_risk.portfolio_theta)],
            ['Vega', f"${data.portfolio_risk.portfolio_vega:.0f}", self._interpret_vega(data.portfolio_risk.portfolio_vega)]
        ]
        
        greeks_table = Table(greeks_data, colWidths=[1.5 * inch, 1.5 * inch, 3 * inch])
        greeks_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(greeks_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Risk metrics
        risk_data = [
            ['Risk Measure', 'Value'],
            ['Gross Position Value', f"${data.portfolio_risk.gross_position_value:,.0f}"],
            ['Net Position Value', f"${data.portfolio_risk.net_position_value:,.0f}"],
            ['Concentration Risk', f"{data.portfolio_risk.concentration_risk:.1%}"],
            ['Correlation Risk', f"{data.portfolio_risk.correlation_risk:.1%}"],
            ['Maximum Drawdown', f"{data.portfolio_risk.max_drawdown:.1%}"]
        ]
        
        risk_table = Table(risk_data, colWidths=[3 * inch, 2 * inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(risk_table)
        
        # Add historical risk chart
        hist_chart = self._create_historical_risk_chart(data.historical_metrics)
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Image(hist_chart, width=6 * inch, height=3 * inch))
        
        return elements
    
    def _create_pdf_position_risks(self, data: RiskReportData, styles) -> List[Any]:
        """Create PDF position risks section"""
        elements = []
        
        elements.append(Paragraph("Position Risk Analysis", styles['Heading1']))
        elements.append(Spacer(1, 0.2 * inch))
        
        if not data.position_risks:
            elements.append(Paragraph("No open positions", styles['Normal']))
            return elements
        
        # Position risk table
        pos_data = [['Symbol', 'Value', '% of Port', 'Delta', 'Risk Score']]
        
        for pos in data.position_risks[:10]:  # Top 10 positions
            row_color = colors.red if pos.risk_score > 70 else colors.black
            pos_data.append([
                pos.symbol,
                f"${pos.market_value:,.0f}",
                f"{pos.percent_of_portfolio:.1%}",
                f"{pos.delta:.1f}",
                f"{pos.risk_score:.0f}"
            ])
        
        pos_table = Table(pos_data, colWidths=[1.5 * inch, 1.5 * inch, 1 * inch, 1 * inch, 1 * inch])
        
        # Apply conditional formatting
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]
        
        # Color high-risk positions
        for i, pos in enumerate(data.position_risks[:10], 1):
            if pos.risk_score > 70:
                table_style.append(('TEXTCOLOR', (0, i), (-1, i), colors.red))
        
        pos_table.setStyle(TableStyle(table_style))
        elements.append(pos_table)
        
        # Position concentration chart
        if len(data.position_risks) > 1:
            elements.append(Spacer(1, 0.3 * inch))
            conc_chart = self._create_position_concentration_chart(data.position_risks)
            elements.append(Image(conc_chart, width=5 * inch, height=3 * inch))
        
        return elements
    
    def _create_pdf_stress_tests(self, data: RiskReportData, styles) -> List[Any]:
        """Create PDF stress test section"""
        elements = []
        
        elements.append(Paragraph("Stress Test Results", styles['Heading1']))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Stress test summary
        stress_data = [['Scenario', 'SPY Move', 'VIX Change', 'Portfolio Impact', 'Margin Call Risk']]
        
        for test in data.stress_test_results:
            impact_pct = test.portfolio_impact / data.portfolio_risk.total_market_value
            margin_risk = "YES" if test.would_trigger_margin_call else "NO"
            
            # Color based on severity
            if abs(impact_pct) > 0.15:
                row_color = colors.red
            elif abs(impact_pct) > 0.10:
                row_color = colors.orange
            else:
                row_color = colors.black
            
            stress_data.append([
                test.scenario_name.replace('_', ' ').title(),
                f"{test.spy_move:.1%}",
                f"{test.vix_change:.1f}x",
                f"${test.portfolio_impact:,.0f} ({impact_pct:.1%})",
                margin_risk
            ])
        
        stress_table = Table(stress_data, colWidths=[1.5 * inch, 1 * inch, 1 * inch, 2 * inch, 1 * inch])
        stress_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(stress_table)
        
        # Stress test chart
        elements.append(Spacer(1, 0.3 * inch))
        stress_chart = self._create_stress_test_chart(data.stress_test_results, data.portfolio_risk)
        elements.append(Image(stress_chart, width=6 * inch, height=3 * inch))
        
        # Worst case analysis
        worst_case = min(data.stress_test_results, key=lambda x: x.worst_case_loss)
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph(
            f"Worst Case Scenario: {worst_case.scenario_name.replace('_', ' ').title()} - "
            f"Potential loss of ${abs(worst_case.worst_case_loss):,.0f} "
            f"({abs(worst_case.worst_case_loss) / data.portfolio_risk.total_market_value:.1%})",
            styles['Normal']
        ))
        
        return elements
    
    # ==========================================================================
    # REPORT GENERATION - HTML
    # ==========================================================================
    def _generate_html_report(self, data: RiskReportData) -> Path:
        """Generate HTML risk report"""
        filename = f"risk_report_{data.report_timestamp.strftime('%Y%m%d_%H%M%S')}.html"
        filepath = REPORT_OUTPUT_DIR / filename
        
        # Create HTML content
        html_content = self._create_html_content(data)
        
        # Save file
        filepath.write_text(html_content)
        
        return filepath
    
    def _create_html_content(self, data: RiskReportData) -> str:
        """Create HTML report content"""
        # Risk level colors
        level_colors = {
            RiskLevel.LOW: '#4caf50',
            RiskLevel.MODERATE: '#2196f3',
            RiskLevel.ELEVATED: '#ff9800',
            RiskLevel.HIGH: '#f44336',
            RiskLevel.CRITICAL: '#d32f2f'
        }
        
        risk_color = level_colors.get(data.risk_level, '#757575')
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Risk Report - {data.report_timestamp.strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: {risk_color};
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px;
        }}
        .risk-score {{
            font-size: 48px;
            font-weight: bold;
        }}
        .section {{
            background-color: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .alert {{
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .alert-critical {{
            background-color: #ffebee;
            border-left: 4px solid #f44336;
        }}
        .alert-high {{
            background-color: #fff3e0;
            border-left: 4px solid #ff9800;
        }}
        .metric-card {{
            display: inline-block;
            padding: 15px;
            margin: 10px;
            background-color: #f5f5f5;
            border-radius: 4px;
            min-width: 150px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #1976d2;
        }}
        .metric-label {{
            font-size: 14px;
            color: #666;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .positive {{
            color: #4caf50;
        }}
        .negative {{
            color: #f44336;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Risk Analysis Report</h1>
        <div class="risk-score">{data.risk_score:.0f}/100</div>
        <h2>{data.risk_level.name} RISK</h2>
    </div>
    
    <div class="section">
        <h2>Portfolio Overview</h2>
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-label">Portfolio Value</div>
                <div class="metric-value">${data.portfolio_risk.total_market_value:,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Portfolio Delta</div>
                <div class="metric-value">{data.portfolio_risk.portfolio_delta:.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Value at Risk</div>
                <div class="metric-value">${data.portfolio_risk.var_95:,.0f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Margin Used</div>
                <div class="metric-value">{data.portfolio_risk.margin_used / (data.portfolio_risk.margin_used + data.portfolio_risk.margin_available):.1%}</div>
            </div>
        </div>
    </div>
"""
        
        # Add alerts section
        if data.risk_alerts:
            html += """
    <div class="section">
        <h2>Risk Alerts</h2>
"""
            for alert in data.risk_alerts[:5]:
                alert_class = 'alert-critical' if alert.severity == RiskLevel.CRITICAL else 'alert-high'
                html += f"""
        <div class="alert {alert_class}">
            <strong>{alert.alert_type.replace('_', ' ').title()}:</strong> {alert.message}<br>
            <small>Action: {alert.recommended_action}</small>
        </div>
"""
            html += "    </div>\n"
        
        # Add recommendations
        if data.recommendations:
            html += """
    <div class="section">
        <h2>Recommendations</h2>
        <ul>
"""
            for rec in data.recommendations:
                html += f"            <li>{rec}</li>\n"
            html += """
        </ul>
    </div>
"""
        
        # Position table
        if data.position_risks:
            html += """
    <div class="section">
        <h2>Position Risks</h2>
        <table>
            <tr>
                <th>Symbol</th>
                <th>Market Value</th>
                <th>% of Portfolio</th>
                <th>Delta</th>
                <th>Risk Score</th>
            </tr>
"""
            for pos in data.position_risks[:10]:
                risk_class = 'negative' if pos.risk_score > 70 else ''
                html += f"""
            <tr>
                <td>{pos.symbol}</td>
                <td>${pos.market_value:,.0f}</td>
                <td>{pos.percent_of_portfolio:.1%}</td>
                <td>{pos.delta:.1f}</td>
                <td class="{risk_class}">{pos.risk_score:.0f}</td>
            </tr>
"""
            html += """
        </table>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        return html
    
    # ==========================================================================
    # REPORT GENERATION - JSON
    # ==========================================================================
    def _generate_json_report(self, data: RiskReportData) -> Path:
        """Generate JSON risk report"""
        filename = f"risk_report_{data.report_timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = REPORT_OUTPUT_DIR / filename
        
        # Convert to JSON-serializable format
        report_dict = {
            'timestamp': data.report_timestamp.isoformat(),
            'report_type': data.report_type.name,
            'risk_score': data.risk_score,
            'risk_level': data.risk_level.name,
            'portfolio_risk': {
                'total_value': data.portfolio_risk.total_market_value,
                'portfolio_delta': data.portfolio_risk.portfolio_delta,
                'portfolio_gamma': data.portfolio_risk.portfolio_gamma,
                'portfolio_theta': data.portfolio_risk.portfolio_theta,
                'portfolio_vega': data.portfolio_risk.portfolio_vega,
                'var_95': data.portfolio_risk.var_95,
                'margin_utilization': data.portfolio_risk.margin_used / (data.portfolio_risk.margin_used + data.portfolio_risk.margin_available)
            },
            'position_risks': [
                {
                    'symbol': pos.symbol,
                    'market_value': pos.market_value,
                    'percent_of_portfolio': pos.percent_of_portfolio,
                    'risk_score': pos.risk_score
                }
                for pos in data.position_risks
            ],
            'stress_tests': [
                {
                    'scenario': test.scenario_name,
                    'portfolio_impact': test.portfolio_impact,
                    'would_trigger_margin_call': test.would_trigger_margin_call
                }
                for test in data.stress_test_results
            ],
            'alerts': [
                {
                    'type': alert.alert_type,
                    'severity': alert.severity.name,
                    'message': alert.message,
                    'action': alert.recommended_action
                }
                for alert in data.risk_alerts
            ],
            'recommendations': data.recommendations
        }
        
        # Save JSON
        with open(filepath, 'w') as f:
            json.dump(report_dict, f, indent=2)
        
        return filepath
    
    # ==========================================================================
    # CHARTING METHODS
    # ==========================================================================
    def _create_risk_score_chart(self, risk_score: float, risk_level: RiskLevel) -> io.BytesIO:
        """Create risk score gauge chart"""
        fig, ax = plt.subplots(figsize=(6, 3))
        
        # Create gauge
        colors_list = ['#4caf50', '#8bc34a', '#ffeb3b', '#ff9800', '#f44336']
        bounds = [0, 20, 40, 60, 80, 100]
        
        # Create colored segments
        for i in range(len(colors_list)):
            ax.barh(0, bounds[i+1] - bounds[i], left=bounds[i], height=0.5, color=colors_list[i])
        
        # Add pointer
        ax.arrow(risk_score, -0.1, 0, 0.2, head_width=3, head_length=0.1, fc='black', ec='black')
        
        # Format
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.5, 1)
        ax.set_xticks([0, 20, 40, 60, 80, 100])
        ax.set_yticks([])
        ax.set_xlabel('Risk Score')
        ax.set_title(f'Current Risk: {risk_score:.0f}/100 ({risk_level.name})', fontsize=14, fontweight='bold')
        
        # Save to bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=CHART_DPI)
        plt.close()
        buf.seek(0)
        
        return buf
    
    def _create_historical_risk_chart(self, historical_data: pd.DataFrame) -> io.BytesIO:
        """Create historical risk metrics chart"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=CHART_SIZE, sharex=True)
        
        # Risk score over time
        ax1.plot(historical_data['date'], historical_data['risk_score'], linewidth=2, color='#1976d2')
        ax1.axhline(y=60, color='orange', linestyle='--', alpha=0.5, label='High Risk')
        ax1.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='Critical Risk')
        ax1.set_ylabel('Risk Score')
        ax1.set_title('Risk Metrics Over Time', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Margin utilization over time
        ax2.plot(historical_data['date'], historical_data['margin_utilization'] * 100, linewidth=2, color='#f44336')
        ax2.axhline(y=70, color='red', linestyle='--', alpha=0.5, label='Warning Level')
        ax2.set_ylabel('Margin Utilization (%)')
        ax2.set_xlabel('Date')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Format dates
        fig.autofmt_xdate()
        
        # Save to bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=CHART_DPI)
        plt.close()
        buf.seek(0)
        
        return buf
    
    def _create_position_concentration_chart(self, position_risks: List[PositionRisk]) -> io.BytesIO:
        """Create position concentration pie chart"""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Get top positions
        top_positions = position_risks[:8]
        other_value = sum(p.market_value for p in position_risks[8:])
        
        # Prepare data
        labels = [p.symbol for p in top_positions]
        sizes = [abs(p.market_value) for p in top_positions]
        
        if other_value > 0:
            labels.append('Other')
            sizes.append(other_value)
        
        # Create pie chart
        colors_palette = plt.cm.Set3(range(len(labels)))
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            autopct='%1.1f%%',
            colors=colors_palette,
            startangle=90
        )
        
        # Highlight concentrated positions
        for i, pos in enumerate(top_positions):
            if pos.percent_of_portfolio > MAX_POSITION_SIZE_PCT:
                wedges[i].set_edgecolor('red')
                wedges[i].set_linewidth(3)
        
        ax.set_title('Position Concentration', fontsize=14, fontweight='bold')
        
        # Save to bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=CHART_DPI)
        plt.close()
        buf.seek(0)
        
        return buf
    
    def _create_stress_test_chart(
        self,
        stress_results: List[StressTestResult],
        portfolio_risk: PortfolioRisk
    ) -> io.BytesIO:
        """Create stress test results chart"""
        fig, ax = plt.subplots(figsize=CHART_SIZE)
        
        # Prepare data
        scenarios = [r.scenario_name.replace('_', ' ').title() for r in stress_results]
        impacts = [r.portfolio_impact for r in stress_results]
        impact_pcts = [i / portfolio_risk.total_market_value * 100 for i in impacts]
        
        # Create bar chart
        colors = ['red' if i < -10 else 'orange' if i < -5 else 'green' for i in impact_pcts]
        bars = ax.bar(scenarios, impact_pcts, color=colors)
        
        # Add value labels
        for bar, pct in zip(bars, impact_pcts):
            height = bar.get_height()
            ax.annotate(f'{pct:.1f}%',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3 if height > 0 else -15),
                       textcoords="offset points",
                       ha='center', va='bottom' if height > 0 else 'top')
        
        # Format
        ax.set_ylabel('Portfolio Impact (%)')
        ax.set_title('Stress Test Results', fontsize=14, fontweight='bold')
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Rotate labels
        plt.xticks(rotation=45, ha='right')
        
        # Save to bytes
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=CHART_DPI)
        plt.close()
        buf.seek(0)
        
        return buf
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _get_status_indicator(self, risk_level: RiskLevel) -> str:
        """Get status indicator for risk level"""
        indicators = {
            RiskLevel.LOW: '✅',
            RiskLevel.MODERATE: '🔵',
            RiskLevel.ELEVATED: '🟡',
            RiskLevel.HIGH: '🟠',
            RiskLevel.CRITICAL: '🔴'
        }
        return indicators.get(risk_level, '')
    
    def _get_delta_status(self, delta: float) -> str:
        """Get status for portfolio delta"""
        if abs(delta) < 50:
            return '✅'
        elif abs(delta) < 100:
            return '🟡'
        else:
            return '🔴'
    
    def _get_margin_status(self, portfolio_risk: PortfolioRisk) -> str:
        """Get status for margin utilization"""
        util = portfolio_risk.margin_used / (portfolio_risk.margin_used + portfolio_risk.margin_available)
        if util < 0.5:
            return '✅'
        elif util < 0.7:
            return '🟡'
        else:
            return '🔴'
    
    def _interpret_delta(self, delta: float) -> str:
        """Interpret portfolio delta"""
        if abs(delta) < 10:
            return "Nearly delta neutral"
        elif delta > 50:
            return "Significantly bullish bias"
        elif delta < -50:
            return "Significantly bearish bias"
        elif delta > 0:
            return "Moderately bullish"
        else:
            return "Moderately bearish"
    
    def _interpret_gamma(self, gamma: float) -> str:
        """Interpret portfolio gamma"""
        if abs(gamma) < 1:
            return "Low gamma risk"
        elif abs(gamma) < 5:
            return "Moderate gamma exposure"
        else:
            return "High gamma risk - large delta changes possible"
    
    def _interpret_theta(self, theta: float) -> str:
        """Interpret portfolio theta"""
        if theta > 0:
            return f"Earning ${-theta:.0f} per day from time decay"
        elif theta < -100:
            return f"Losing ${-theta:.0f} per day - significant time decay"
        else:
            return f"Moderate time decay of ${-theta:.0f} per day"
    
    def _interpret_vega(self, vega: float) -> str:
        """Interpret portfolio vega"""
        if abs(vega) < 100:
            return "Low volatility exposure"
        elif abs(vega) < 500:
            return "Moderate volatility exposure"
        else:
            return f"High volatility exposure - ${vega:.0f} per 1% IV change"
    
    def _check_and_send_alerts(self, report_data: RiskReportData) -> None:
        """Check for critical alerts and send notifications"""
        critical_alerts = [a for a in report_data.risk_alerts if a.severity in [RiskLevel.CRITICAL, RiskLevel.HIGH]]
        
        if critical_alerts:
            self.logger.warning(f"Found {len(critical_alerts)} critical risk alerts")
            
            # This would integrate with notification system
            # For now, just log
            for alert in critical_alerts:
                self.logger.warning(f"RISK ALERT: {alert.message}")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def get_current_risk_score(self) -> float:
        """Get current portfolio risk score"""
        try:
            # Quick risk assessment
            positions = self.db.get_positions(datetime.now())
            positions_df = pd.DataFrame(positions)
            account_data = self.db.get_account_snapshot(datetime.now())
            
            portfolio_risk = self._calculate_portfolio_risk(positions_df, account_data)
            position_risks = self._calculate_position_risks(positions_df, portfolio_risk)
            
            risk_score = self._calculate_risk_score(portfolio_risk, position_risks, [])
            
            return risk_score
            
        except Exception as e:
            self.logger.error(f"Error calculating risk score: {e}")
            return 0.0
    
    def monitor_risk_limits(self) -> List[Dict[str, Any]]:
        """Monitor risk limits and return violations"""
        violations = []
        
        try:
            # Get current data
            positions = self.db.get_positions(datetime.now())
            positions_df = pd.DataFrame(positions)
            account_data = self.db.get_account_snapshot(datetime.now())
            
            portfolio_risk = self._calculate_portfolio_risk(positions_df, account_data)
            
            # Check portfolio delta
            if abs(portfolio_risk.portfolio_delta) > MAX_PORTFOLIO_DELTA:
                violations.append({
                    'type': 'portfolio_delta',
                    'current': portfolio_risk.portfolio_delta,
                    'limit': MAX_PORTFOLIO_DELTA,
                    'severity': 'high'
                })
            
            # Check margin utilization
            margin_util = portfolio_risk.margin_used / (
                portfolio_risk.margin_used + portfolio_risk.margin_available
            ) if portfolio_risk.margin_available > 0 else 1.0
            
            if margin_util > MAX_MARGIN_USAGE:
                violations.append({
                    'type': 'margin_utilization',
                    'current': margin_util,
                    'limit': MAX_MARGIN_USAGE,
                    'severity': 'critical' if margin_util > 0.85 else 'high'
                })
            
            # Check position concentration
            if not positions_df.empty:
                positions_df['market_value'] = positions_df['quantity'] * positions_df['current_price']
                max_position_pct = positions_df['market_value'].abs().max() / portfolio_risk.total_market_value
                
                if max_position_pct > MAX_POSITION_SIZE_PCT:
                    violations.append({
                        'type': 'position_concentration',
                        'current': max_position_pct,
                        'limit': MAX_POSITION_SIZE_PCT,
                        'severity': 'elevated'
                    })
            
            return violations
            
        except Exception as e:
            self.logger.error(f"Error monitoring risk limits: {e}")
            return []
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get quick risk summary"""
        try:
            risk_score = self.get_current_risk_score()
            risk_level = self._determine_risk_level(risk_score)
            violations = self.monitor_risk_limits()
            
            return {
                'risk_score': risk_score,
                'risk_level': risk_level.name,
                'violations': len(violations),
                'critical_violations': len([v for v in violations if v['severity'] == 'critical']),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting risk summary: {e}")
            return {
                'risk_score': 0,
                'risk_level': 'UNKNOWN',
                'violations': 0,
                'critical_violations': 0,
                'timestamp': datetime.now().isoformat()
            }

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test risk report generator
    from SpyderH_Storage.SpyderH01_DatabaseManager import DatabaseManager
from enum import Enum, auto
    
    # Initialize
    db = DatabaseManager(":memory:")
    generator = RiskReportGenerator(db)
    
    # Create sample positions for testing
    sample_positions = [
        {
            'symbol': 'SPY 450C',
            'quantity': 10,
            'current_price': 5.50,
            'entry_price': 5.00,
            'delta': 45,
            'gamma': 2.5,
            'theta': -25,
            'vega': 150,
            'unrealized_pnl': 500
        },
        {
            'symbol': 'SPY 440P',
            'quantity': -5,
            'current_price': 3.20,
            'entry_price': 3.50,
            'delta': -30,
            'gamma': 1.8,
            'theta': -15,
            'vega': 100,
            'unrealized_pnl': 150
        }
    ]
    
    # Add sample data to database
    for pos in sample_positions:
        db.save_position(pos)
    
    # Generate risk report
    print("Generating risk report...")
    report_files = generator.generate_report(
        report_type=ReportType.DAILY,
        output_formats=['pdf', 'html', 'json']
    )
    
    print("\nGenerated reports:")
    for format, filepath in report_files.items():
        print(f"  {format}: {filepath}")
    
    # Get risk summary
    summary = generator.get_risk_summary()
    print(f"\nRisk Summary:")
    print(f"  Risk Score: {summary['risk_score']:.0f}/100")
    print(f"  Risk Level: {summary['risk_level']}")
    print(f"  Violations: {summary['violations']}")
    
    # Check risk limits
    violations = generator.monitor_risk_limits()
    if violations:
        print("\nRisk Limit Violations:")
        for v in violations:
            print(f"  {v['type']}: {v['current']:.2f} (limit: {v['limit']:.2f}) - {v['severity']}")
