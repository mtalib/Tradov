#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from enum import Enum, auto
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderK01_ReportGenerator.py
Group: K (Reporting)
Purpose: Automated report generation

Description:
This module handles automated generation of trading reports including daily
summaries, performance analytics, risk reports, and compliance documentation.
It supports multiple output formats (PDF, HTML, Excel) with customizable
templates, automated scheduling, and email distribution. The module integrates
with all system components to gather comprehensive trading metrics and generates
professional reports for analysis and record-keeping.

Author: Mohamed Talib
Created: 2025-01-27
Version: v1.0
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
TEMPLATE_DIR = Path(__file__).parent / "templates" / "reports"

# Report types
DAILY_REPORT = "daily"
WEEKLY_REPORT = "weekly"
MONTHLY_REPORT = "monthly"
QUARTERLY_REPORT = "quarterly"
ANNUAL_REPORT = "annual"
CUSTOM_REPORT = "custom"

# Output formats
OUTPUT_FORMATS = ["pdf", "html", "excel", "csv", "json"]

# Chart settings
CHART_DPI = 300
CHART_STYLE = 'seaborn-v0_8-darkgrid'
COLOR_PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

# =============================================================================
# Enumerations
# =============================================================================
class ReportType(Enum):
    """Types of reports."""
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADES = "trades"
    POSITIONS = "positions"
    PNL = "pnl"
    COMPLIANCE = "compliance"
    TAX = "tax"
    SUMMARY = "summary"

class ReportFrequency(Enum):
    """Report generation frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    ON_DEMAND = "on_demand"

class ReportFormat(Enum):
    """Report output formats."""
    PDF = "pdf"
    HTML = "html"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"

# =============================================================================
# Data Classes
# =============================================================================
class ReportConfig:
    """
    Report configuration.
    
    Attributes:
        report_type: Type of report
        frequency: Generation frequency
        format: Output format
        template: Template name
        recipients: Email recipients
        include_charts: Include charts
        include_details: Include detailed data
        custom_sections: Custom report sections
    """
    report_type: ReportType
    frequency: ReportFrequency
    format: ReportFormat
    template: Optional[str] = None
    recipients: List[str] = field(default_factory=list)
    include_charts: bool = True
    include_details: bool = True
    custom_sections: List[str] = field(default_factory=list)

class ReportData:
    """
    Data for report generation.
    
    Attributes:
        start_date: Report start date
        end_date: Report end date
        performance_metrics: Performance data
        trades: Trade data
        positions: Position data
        risk_metrics: Risk data
        account_summary: Account summary
        charts: Generated charts
        metadata: Additional metadata
    """
    start_date: datetime
    end_date: datetime
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    positions: pd.DataFrame = field(default_factory=pd.DataFrame)
    risk_metrics: Dict[str, Any] = field(default_factory=dict)
    account_summary: Dict[str, Any] = field(default_factory=dict)
    charts: Dict[str, BytesIO] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

# =============================================================================
# Class Definitions
# =============================================================================
class ReportGenerator:
    """
    Automated report generation system.
    
    This class handles the generation of various trading reports including
    performance summaries, risk analysis, trade logs, and compliance reports.
    It supports multiple output formats and automated distribution.
    
    Attributes:
        logger (Logger): Module logger
        config (ConfigManager): Configuration manager
        event_manager (EventManager): Event system
        trade_repository (TradeRepository): Trade data access
        risk_manager (RiskManager): Risk metrics access
        template_env (Environment): Jinja2 template environment
        report_configs (Dict): Report configurations
        scheduled_reports (List): Scheduled report tasks
    """
    
    def __init__(self):
        """Initialize report generator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = get_config_manager()
        self.event_manager = get_event_manager()
        self.trade_repository = get_trade_repository()
        self.risk_manager = get_risk_manager()
        self.alert_manager = get_alert_manager()
        
        # Create report directories
        self._create_directories()
        
        # Initialize template environment
        self.template_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=True
        )
        
        # Report configurations
        self.report_configs: Dict[str, ReportConfig] = {}
        self._load_report_configs()
        
        # Scheduled reports
        self.scheduled_reports: List[Dict[str, Any]] = []
        self._schedule_reports()
        
        # Chart styling
        plt.style.use(CHART_STYLE)
        sns.set_palette(COLOR_PALETTE)
        
        # Subscribe to events
        self._subscribe_to_events()
        
        self.logger.info("Report generator initialized")
    
    def _create_directories(self) -> None:
        """Create report directories."""
        directories = [
            REPORT_BASE_DIR,
            REPORT_BASE_DIR / "daily",
            REPORT_BASE_DIR / "weekly",
            REPORT_BASE_DIR / "monthly",
            REPORT_BASE_DIR / "quarterly",
            REPORT_BASE_DIR / "annual",
            REPORT_BASE_DIR / "temp"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_report_configs(self) -> None:
        """Load report configurations."""
        # Default configurations
        self.report_configs['daily_summary'] = ReportConfig(
            report_type=ReportType.SUMMARY,
            frequency=ReportFrequency.DAILY,
            format=ReportFormat.PDF,
            template='daily_summary.html',
            recipients=self.config.get('reports.daily_recipients', []),
            include_charts=True,
            include_details=False
        )
        
        self.report_configs['weekly_performance'] = ReportConfig(
            report_type=ReportType.PERFORMANCE,
            frequency=ReportFrequency.WEEKLY,
            format=ReportFormat.PDF,
            template='weekly_performance.html',
            recipients=self.config.get('reports.weekly_recipients', []),
            include_charts=True,
            include_details=True
        )
        
        self.report_configs['monthly_risk'] = ReportConfig(
            report_type=ReportType.RISK,
            frequency=ReportFrequency.MONTHLY,
            format=ReportFormat.PDF,
            template='monthly_risk.html',
            include_charts=True,
            include_details=True
        )
        
        # Load custom configurations
        custom_configs = self.config.get('reports.custom_configs', [])
        for custom in custom_configs:
            self.report_configs[custom['name']] = ReportConfig(**custom)
    
    def _schedule_reports(self) -> None:
        """Schedule automatic report generation."""
        # This would integrate with a scheduler like APScheduler
        # Simplified for this example
        self.scheduled_reports = [
            {
                'name': 'daily_summary',
                'time': '16:30',  # After market close
                'days': ['mon', 'tue', 'wed', 'thu', 'fri']
            },
            {
                'name': 'weekly_performance',
                'time': '17:00',
                'days': ['fri']
            },
            {
                'name': 'monthly_risk',
                'time': '17:00',
                'days': ['last_day_of_month']
            }
        ]
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to system events."""
        self.event_manager.subscribe('TRADING_DAY_END', self._on_trading_day_end)
        self.event_manager.subscribe('GENERATE_REPORT', self._on_generate_report)
    
    # =========================================================================
    # Public Methods - Report Generation
    # =========================================================================
    
    def generate_report(self, report_name: str, 
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None,
                       format: Optional[ReportFormat] = None) -> Path:
        """
        Generate a report.
        
        Args:
            report_name: Name of report configuration
            start_date: Report start date (optional)
            end_date: Report end date (optional)
            format: Output format override
            
        Returns:
            Path to generated report
        """
        try:
            # Get report configuration
            if report_name not in self.report_configs:
                raise ValueError(f"Unknown report: {report_name}")
            
            config = self.report_configs[report_name]
            
            # Use override format if provided
            if format:
                config.format = format
            
            # Determine date range
            if not end_date:
                end_date = datetime.now()
            
            if not start_date:
                start_date = self._get_start_date(config.frequency, end_date)
            
            self.logger.info(f"Generating {report_name} report: {start_date} to {end_date}")
            
            # Collect report data
            report_data = self._collect_report_data(config, start_date, end_date)
            
            # Generate charts if needed
            if config.include_charts:
                self._generate_charts(report_data)
            
            # Generate report in requested format
            if config.format == ReportFormat.PDF:
                report_path = self._generate_pdf_report(config, report_data)
            elif config.format == ReportFormat.HTML:
                report_path = self._generate_html_report(config, report_data)
            elif config.format == ReportFormat.EXCEL:
                report_path = self._generate_excel_report(config, report_data)
            elif config.format == ReportFormat.CSV:
                report_path = self._generate_csv_report(config, report_data)
            else:  # JSON
                report_path = self._generate_json_report(config, report_data)
            
            # Send to recipients if configured
            if config.recipients:
                self._distribute_report(report_path, config.recipients)
            
            self.logger.info(f"Report generated: {report_path}")
            
            return report_path
            
        except Exception as e:
            self.logger.error(f"Failed to generate report: {str(e)}")
            raise
    
    def generate_custom_report(self, title: str, sections: List[str],
                             start_date: datetime, end_date: datetime,
                             format: ReportFormat = ReportFormat.PDF) -> Path:
        """
        Generate a custom report with specified sections.
        
        Args:
            title: Report title
            sections: List of section names to include
            start_date: Report start date
            end_date: Report end date
            format: Output format
            
        Returns:
            Path to generated report
        """
        config = ReportConfig(
            report_type=ReportType.SUMMARY,
            frequency=ReportFrequency.ON_DEMAND,
            format=format,
            custom_sections=sections,
            include_charts=True,
            include_details=True
        )
        
        # Generate unique report name
        report_name = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.report_configs[report_name] = config
        
        try:
            return self.generate_report(report_name, start_date, end_date)
        finally:
            # Clean up temporary config
            del self.report_configs[report_name]
    
    # =========================================================================
    # Private Methods - Data Collection
    # =========================================================================
    
    def _collect_report_data(self, config: ReportConfig, 
                           start_date: datetime, end_date: datetime) -> ReportData:
        """
        Collect data for report generation.
        
        Args:
            config: Report configuration
            start_date: Start date
            end_date: End date
            
        Returns:
            Report data
        """
        report_data = ReportData(start_date=start_date, end_date=end_date)
        
        # Collect performance metrics
        report_data.performance_metrics = self._collect_performance_metrics(
            start_date, end_date
        )
        
        # Collect trades
        trades = self.trade_repository.get_trades(
            start_date=start_date,
            end_date=end_date
        )
        if trades:
            report_data.trades = pd.DataFrame([t.__dict__ for t in trades])
        
        # Collect current positions
        # This would get from trading engine
        report_data.positions = pd.DataFrame()  # Placeholder
        
        # Collect risk metrics
        report_data.risk_metrics = self._collect_risk_metrics()
        
        # Collect account summary
        report_data.account_summary = self._collect_account_summary()
        
        # Add metadata
        report_data.metadata = {
            'generated_at': datetime.now(),
            'report_type': config.report_type.value,
            'trading_days': len(get_trading_days(start_date, end_date))
        }
        
        return report_data
    
    def _collect_performance_metrics(self, start_date: datetime, 
                                   end_date: datetime) -> Dict[str, Any]:
        """Collect performance metrics."""
        # Get performance summary from repository
        summary = self.trade_repository.get_performance_summary(
            start_date=start_date.date(),
            end_date=end_date.date()
        )
        
        if summary.empty:
            return {}
        
        total_row = summary[summary['strategy'] == 'TOTAL'].iloc[0] if 'TOTAL' in summary['strategy'].values else None
        
        metrics = {
            'total_return': total_row['total_pnl'] if total_row is not None else 0,
            'total_trades': int(total_row['total_trades']) if total_row is not None else 0,
            'win_rate': total_row['win_rate'] if total_row is not None else 0,
            'profit_factor': total_row['profit_factor'] if total_row is not None else 0,
            'sharpe_ratio': total_row['sharpe_ratio'] if total_row is not None else 0,
            'max_drawdown': total_row['max_drawdown'] if total_row is not None else 0,
            'avg_trade': total_row['avg_trade'] if total_row is not None else 0,
            'best_trade': summary['total_gross_profit'].max() if not summary.empty else 0,
            'worst_trade': summary['total_gross_loss'].min() if not summary.empty else 0,
            'total_commission': total_row['total_commission'] if total_row is not None else 0,
            'by_strategy': summary[summary['strategy'] != 'TOTAL'].to_dict('records')
        }
        
        return metrics
    
    def _collect_risk_metrics(self) -> Dict[str, Any]:
        """Collect current risk metrics."""
        risk_limits = self.risk_manager.check_risk_limits()
        
        return {
            'portfolio_heat': risk_limits.get('portfolio_heat', 0),
            'daily_loss': risk_limits.get('daily_pnl', 0),
            'var_95': risk_limits.get('var_95', 0),
            'var_99': risk_limits.get('var_99', 0),
            'open_positions': risk_limits.get('open_positions', 0),
            'margin_used': 0,  # Would get from broker
            'circuit_breaker': risk_limits.get('circuit_breaker_active', False),
            'risk_level': risk_limits.get('risk_level', 'low')
        }
    
    def _collect_account_summary(self) -> Dict[str, Any]:
        """Collect account summary."""
        return {
            'account_value': self.risk_manager._get_account_value(),
            'cash_balance': 0,  # Would get from broker
            'buying_power': 0,  # Would get from broker
            'daily_pnl': self.risk_manager.risk_metrics.daily_pnl,
            'unrealized_pnl': 0,  # Would calculate from positions
            'realized_pnl': 0  # Would get from trades
        }
    
    # =========================================================================
    # Private Methods - Chart Generation
    # =========================================================================
    
    def _generate_charts(self, report_data: ReportData) -> None:
        """
        Generate charts for report.
        
        Args:
            report_data: Report data
        """
        # Equity curve
        equity_chart = self._create_equity_curve(report_data)
        if equity_chart:
            report_data.charts['equity_curve'] = equity_chart
        
        # Daily P&L
        pnl_chart = self._create_pnl_chart(report_data)
        if pnl_chart:
            report_data.charts['daily_pnl'] = pnl_chart
        
        # Win/Loss distribution
        winloss_chart = self._create_winloss_chart(report_data)
        if winloss_chart:
            report_data.charts['win_loss'] = winloss_chart
        
        # Strategy performance
        strategy_chart = self._create_strategy_chart(report_data)
        if strategy_chart:
            report_data.charts['strategy_performance'] = strategy_chart
        
        # Risk metrics
        risk_chart = self._create_risk_chart(report_data)
        if risk_chart:
            report_data.charts['risk_metrics'] = risk_chart
    
    def _create_equity_curve(self, report_data: ReportData) -> Optional[BytesIO]:
        """Create equity curve chart."""
        try:
            # Get equity curve data
            equity_curve = self.trade_repository.get_equity_curve(
                start_date=report_data.start_date.date()
            )
            
            if equity_curve.empty:
                return None
            
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Plot equity curve
            ax.plot(equity_curve.index, equity_curve['ending_equity'], 
                   linewidth=2, label='Equity')
            
            # Add zero line
            ax.axhline(y=equity_curve['ending_equity'].iloc[0], 
                      color='gray', linestyle='--', alpha=0.5)
            
            # Formatting
            ax.set_title('Equity Curve', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date')
            ax.set_ylabel('Equity ($)')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Format dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            
            # Save to buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', dpi=CHART_DPI)
            plt.close()
            
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            self.logger.error(f"Failed to create equity curve: {str(e)}")
            return None
    
    def _create_pnl_chart(self, report_data: ReportData) -> Optional[BytesIO]:
        """Create daily P&L chart."""
        try:
            if report_data.trades.empty:
                return None
            
            # Group by day
            daily_pnl = report_data.trades.groupby(
                report_data.trades['exit_time'].dt.date
            )['pnl'].sum()
            
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Create bar chart
            colors = ['green' if x > 0 else 'red' for x in daily_pnl.values]
            ax.bar(daily_pnl.index, daily_pnl.values, color=colors, alpha=0.7)
            
            # Add zero line
            ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            
            # Formatting
            ax.set_title('Daily P&L', fontsize=16, fontweight='bold')
            ax.set_xlabel('Date')
            ax.set_ylabel('P&L ($)')
            ax.grid(True, alpha=0.3)
            
            # Format dates
            plt.xticks(rotation=45)
            
            # Save to buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', dpi=CHART_DPI)
            plt.close()
            
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            self.logger.error(f"Failed to create P&L chart: {str(e)}")
            return None
    
    def _create_winloss_chart(self, report_data: ReportData) -> Optional[BytesIO]:
        """Create win/loss distribution chart."""
        try:
            if report_data.trades.empty:
                return None
            
            # Create figure with subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            
            # Win/Loss pie chart
            wins = len(report_data.trades[report_data.trades['pnl'] > 0])
            losses = len(report_data.trades[report_data.trades['pnl'] <= 0])
            
            ax1.pie([wins, losses], labels=['Wins', 'Losses'], 
                   colors=['green', 'red'], autopct='%1.1f%%')
            ax1.set_title('Win/Loss Ratio')
            
            # P&L distribution histogram
            ax2.hist(report_data.trades['pnl'], bins=30, alpha=0.7, 
                    color='blue', edgecolor='black')
            ax2.axvline(x=0, color='red', linestyle='--')
            ax2.set_title('P&L Distribution')
            ax2.set_xlabel('P&L ($)')
            ax2.set_ylabel('Frequency')
            
            # Save to buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', dpi=CHART_DPI)
            plt.close()
            
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            self.logger.error(f"Failed to create win/loss chart: {str(e)}")
            return None
    
    def _create_strategy_chart(self, report_data: ReportData) -> Optional[BytesIO]:
        """Create strategy performance comparison chart."""
        try:
            strategy_data = report_data.performance_metrics.get('by_strategy', [])
            
            if not strategy_data:
                return None
            
            # Create DataFrame
            df = pd.DataFrame(strategy_data)
            
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Bar chart of P&L by strategy
            strategies = df['strategy']
            pnl = df['total_pnl']
            
            colors = ['green' if x > 0 else 'red' for x in pnl]
            ax.bar(strategies, pnl, color=colors, alpha=0.7)
            
            # Add value labels
            for i, v in enumerate(pnl):
                ax.text(i, v, f'${v:,.0f}', ha='center', 
                       va='bottom' if v > 0 else 'top')
            
            # Formatting
            ax.set_title('Performance by Strategy', fontsize=16, fontweight='bold')
            ax.set_xlabel('Strategy')
            ax.set_ylabel('Total P&L ($)')
            ax.grid(True, alpha=0.3)
            
            # Save to buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', dpi=CHART_DPI)
            plt.close()
            
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            self.logger.error(f"Failed to create strategy chart: {str(e)}")
            return None
    
    def _create_risk_chart(self, report_data: ReportData) -> Optional[BytesIO]:
        """Create risk metrics visualization."""
        try:
            risk_metrics = report_data.risk_metrics
            
            # Create figure with subplots
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
            
            # Portfolio heat gauge
            heat = risk_metrics.get('portfolio_heat', 0) * 100
            self._create_gauge_chart(ax1, heat, 'Portfolio Heat (%)', 
                                   thresholds=[30, 60, 80])
            
            # VaR chart
            var_95 = risk_metrics.get('var_95', 0)
            var_99 = risk_metrics.get('var_99', 0)
            ax2.bar(['95% VaR', '99% VaR'], [var_95, var_99], 
                   color=['orange', 'red'], alpha=0.7)
            ax2.set_title('Value at Risk')
            ax2.set_ylabel('VaR ($)')
            
            # Position distribution
            # This would show actual position data
            ax3.text(0.5, 0.5, 'Position Distribution\n(No data)', 
                    ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Position Distribution')
            
            # Risk level indicator
            risk_level = risk_metrics.get('risk_level', 'low')
            risk_colors = {
                'low': 'green',
                'medium': 'yellow',
                'high': 'orange',
                'critical': 'red'
            }
            ax4.bar(['Risk Level'], [1], color=risk_colors.get(risk_level, 'gray'))
            ax4.set_ylim(0, 1)
            ax4.set_title(f'Current Risk Level: {risk_level.upper()}')
            ax4.set_yticks([])
            
            # Save to buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', dpi=CHART_DPI)
            plt.close()
            
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            self.logger.error(f"Failed to create risk chart: {str(e)}")
            return None
    
    def _create_gauge_chart(self, ax, value: float, title: str, 
                          thresholds: List[float]) -> None:
        """Create a gauge chart."""
        # Simple gauge implementation
        ax.clear()
        
        # Create colored sections
        colors = ['green', 'yellow', 'orange', 'red']
        prev_threshold = 0
        
        for i, threshold in enumerate(thresholds + [100]):
            ax.barh(0, threshold - prev_threshold, left=prev_threshold, 
                   height=0.5, color=colors[i], alpha=0.3)
            prev_threshold = threshold
        
        # Add value indicator
        ax.barh(0.5, value, height=0.3, color='black')
        ax.text(value, 0.5, f'{value:.1f}%', ha='left', va='center')
        
        # Formatting
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.5, 1)
        ax.set_title(title)
        ax.set_xlabel('Percentage')
        ax.set_yticks([])
    
    # =========================================================================
    # Private Methods - Report Generation
    # =========================================================================
    
    def _generate_pdf_report(self, config: ReportConfig, 
                           report_data: ReportData) -> Path:
        """Generate PDF report."""
        # First generate HTML
        html_path = self._generate_html_report(config, report_data)
        
        # Convert HTML to PDF
        pdf_filename = f"{config.report_type.value}_{report_data.end_date.strftime('%Y%m%d')}.pdf"
        pdf_path = self._get_report_path(config.frequency) / pdf_filename
        
        # Use WeasyPrint for conversion
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        
        # Clean up temporary HTML
        html_path.unlink()
        
        return pdf_path
    
    def _generate_html_report(self, config: ReportConfig, 
                            report_data: ReportData) -> Path:
        """Generate HTML report."""
        # Load template
        template_name = config.template or f"{config.report_type.value}.html"
        template = self.template_env.get_template(template_name)
        
        # Prepare context
        context = {
            'title': self._get_report_title(config, report_data),
            'data': report_data,
            'config': config,
            'charts': {}
        }
        
        # Encode charts as base64
        for name, buffer in report_data.charts.items():
            buffer.seek(0)
            encoded = base64.b64encode(buffer.read()).decode()
            context['charts'][name] = f"data:image/png;base64,{encoded}"
        
        # Render template
        html_content = template.render(**context)
        
        # Save HTML
        html_filename = f"{config.report_type.value}_{report_data.end_date.strftime('%Y%m%d')}.html"
        html_path = REPORT_BASE_DIR / "temp" / html_filename
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        return html_path
    
    def _generate_excel_report(self, config: ReportConfig, 
                             report_data: ReportData) -> Path:
        """Generate Excel report."""
        excel_filename = f"{config.report_type.value}_{report_data.end_date.strftime('%Y%m%d')}.xlsx"
        excel_path = self._get_report_path(config.frequency) / excel_filename
        
        # Create Excel writer
        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Summary sheet
            summary_df = pd.DataFrame([report_data.performance_metrics])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Trades sheet
            if not report_data.trades.empty:
                report_data.trades.to_excel(writer, sheet_name='Trades', index=False)
            
            # Performance by strategy
            if report_data.performance_metrics.get('by_strategy'):
                strategy_df = pd.DataFrame(report_data.performance_metrics['by_strategy'])
                strategy_df.to_excel(writer, sheet_name='By Strategy', index=False)
            
            # Risk metrics
            risk_df = pd.DataFrame([report_data.risk_metrics])
            risk_df.to_excel(writer, sheet_name='Risk Metrics', index=False)
            
            # Add charts
            for sheet_name, chart_buffer in report_data.charts.items():
                worksheet = workbook.add_worksheet(sheet_name)
                chart_buffer.seek(0)
                worksheet.insert_image('A1', '', {'image_data': chart_buffer})
        
        return excel_path
    
    def _generate_csv_report(self, config: ReportConfig, 
                           report_data: ReportData) -> Path:
        """Generate CSV report (trades only)."""
        csv_filename = f"trades_{report_data.end_date.strftime('%Y%m%d')}.csv"
        csv_path = self._get_report_path(config.frequency) / csv_filename
        
        if not report_data.trades.empty:
            report_data.trades.to_csv(csv_path, index=False)
        else:
            # Create empty file
            pd.DataFrame().to_csv(csv_path, index=False)
        
        return csv_path
    
    def _generate_json_report(self, config: ReportConfig, 
                            report_data: ReportData) -> Path:
        """Generate JSON report."""
        json_filename = f"{config.report_type.value}_{report_data.end_date.strftime('%Y%m%d')}.json"
        json_path = self._get_report_path(config.frequency) / json_filename
        
        # Prepare data for JSON serialization
        json_data = {
            'metadata': report_data.metadata,
            'performance': report_data.performance_metrics,
            'risk': report_data.risk_metrics,
            'account': report_data.account_summary,
            'trades': report_data.trades.to_dict('records') if not report_data.trades.empty else []
        }
        
        # Convert datetime objects
        def json_serial(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2, default=json_serial)
        
        return json_path
    
    # =========================================================================
    # Private Methods - Utilities
    # =========================================================================
    
    def _get_report_path(self, frequency: ReportFrequency) -> Path:
        """Get report directory path."""
        return REPORT_BASE_DIR / frequency.value
    
    def _get_start_date(self, frequency: ReportFrequency, 
                       end_date: datetime) -> datetime:
        """Calculate start date based on frequency."""
        if frequency == ReportFrequency.DAILY:
            return end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif frequency == ReportFrequency.WEEKLY:
            return end_date - timedelta(days=7)
        elif frequency == ReportFrequency.MONTHLY:
            return end_date - timedelta(days=30)
        elif frequency == ReportFrequency.QUARTERLY:
            return end_date - timedelta(days=90)
        elif frequency == ReportFrequency.ANNUAL:
            return end_date - timedelta(days=365)
        else:
            return end_date - timedelta(days=1)
    
    def _get_report_title(self, config: ReportConfig, 
                         report_data: ReportData) -> str:
        """Generate report title."""
        frequency_text = config.frequency.value.title()
        type_text = config.report_type.value.title()
        date_text = report_data.end_date.strftime('%B %d, %Y')
        
        return f"{frequency_text} {type_text} Report - {date_text}"
    
    def _distribute_report(self, report_path: Path, recipients: List[str]) -> None:
        """Distribute report to recipients."""
        try:
            # This would integrate with email service
            self.alert_manager.send_alert(
                level=AlertLevel.INFO,
                category=AlertCategory.SYSTEM,
                title="Report Generated",
                message=f"Report available: {report_path.name}",
                attachments=[str(report_path)],
                channels=[NotificationChannel.EMAIL],
                metadata={'recipients': recipients}
            )
            
            self.logger.info(f"Report distributed to {len(recipients)} recipients")
            
        except Exception as e:
            self.logger.error(f"Failed to distribute report: {str(e)}")
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def _on_trading_day_end(self, event_data: Dict[str, Any]) -> None:
        """Handle end of trading day event."""
        # Generate daily report
        try:
            self.generate_report('daily_summary')
        except Exception as e:
            self.logger.error(f"Failed to generate daily report: {str(e)}")
    
    def _on_generate_report(self, event_data: Dict[str, Any]) -> None:
        """Handle report generation request."""
        report_name = event_data.get('report_name')
        if report_name:
            try:
                self.generate_report(
                    report_name,
                    start_date=event_data.get('start_date'),
                    end_date=event_data.get('end_date')
                )
            except Exception as e:
                self.logger.error(f"Failed to generate requested report: {str(e)}")

# =============================================================================
# Module Functions
# =============================================================================
def get_report_generator() -> ReportGenerator:
    """
    Get singleton instance of report generator.
    
    Returns:
        ReportGenerator instance
    """
    global _REPORT_GENERATOR_INSTANCE
    if _REPORT_GENERATOR_INSTANCE is None:
        _REPORT_GENERATOR_INSTANCE = ReportGenerator()
    return _REPORT_GENERATOR_INSTANCE

def generate_quick_report(report_type: str = 'summary', 
                        days: int = 1) -> Path:
    """
    Generate a quick report for the specified period.
    
    Args:
        report_type: Type of report
        days: Number of days to include
        
    Returns:
        Path to generated report
    """
    generator = get_report_generator()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return generator.generate_custom_report(
        title=f"Quick {report_type.title()} Report",
        sections=[report_type],
        start_date=start_date,
        end_date=end_date
    )

# =============================================================================
# Module Initialization
# =============================================================================
_REPORT_GENERATOR_INSTANCE: Optional[ReportGenerator] = None
