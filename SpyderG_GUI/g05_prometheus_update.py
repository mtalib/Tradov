#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEMPORARY FILE - Shows how to integrate Prometheus Metrics into SpyderG05_TradingDashboard

This code replaces the create_right_panel method's System Health section
with the integrated Prometheus Metrics display
"""

# ==============================================================================
# MODIFICATION FOR SpyderG05_TradingDashboard.py
# ==============================================================================

def create_right_panel_with_prometheus(self) -> QWidget:
    """
    Modified create_right_panel method with integrated Prometheus Metrics
    Replace the existing create_right_panel method with this version
    """
    panel = QWidget()
    layout = QVBoxLayout()
    layout.setSpacing(3)
    layout.setContentsMargins(5, 5, 5, 5)
    
    # ... [Control buttons section remains the same] ...
    
    # ... [Account info section remains the same] ...
    
    # ... [P&L Performance section remains the same] ...
    
    # ... [Risk Monitor section remains the same] ...
    
    # ... [Autonomous AI Activity section remains the same] ...
    
    # ===========================================================================
    # REPLACE SYSTEM HEALTH WITH PROMETHEUS METRICS
    # ===========================================================================
    
    # Prometheus Metrics Panel (replacing System Health)
    metrics_group = QGroupBox("PROMETHEUS METRICS")
    metrics_layout = QVBoxLayout()
    metrics_layout.setSpacing(2)
    metrics_layout.setContentsMargins(5, 10, 5, 5)
    
    # Create two-column layout for client status
    clients_widget = QWidget()
    clients_layout = QGridLayout()
    clients_layout.setSpacing(1)
    clients_layout.setContentsMargins(0, 0, 0, 0)
    
    # Client indicators (matching your mockup)
    self.client_indicators = {}
    client_configs = [
        ("CLIENT 0: Admin", 0, 0),
        ("CLIENT 1: Orders", 0, 1),
        ("CLIENT 2: Core", 1, 0),
        ("CLIENT 3: Options", 1, 1),
        ("CLIENT 4: Volatility", 2, 0),
        ("CLIENT 5: Internals", 2, 1),
        ("CLIENT 6: Major ETFs", 3, 0),
        ("CLIENT 7: Extended Assets", 3, 1),
        ("CLIENT 8: Sector ETFs", 4, 0),
    ]
    
    for label_text, row, col in client_configs:
        # Create label with dot indicator
        label = QLabel(f"● {label_text}")
        label.setStyleSheet(f"color: {COLORS['positive']}; font-size: 11px;")
        label.setFixedHeight(18)
        self.client_indicators[label_text.split(':')[0]] = label
        clients_layout.addWidget(label, row, col)
    
    clients_widget.setLayout(clients_layout)
    metrics_layout.addWidget(clients_widget)
    
    # Separator line
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setStyleSheet(f"color: {COLORS['border']};")
    metrics_layout.addWidget(separator)
    
    # System metrics section
    metrics_stats_widget = QWidget()
    metrics_stats_layout = QVBoxLayout()
    metrics_stats_layout.setSpacing(2)
    metrics_stats_layout.setContentsMargins(0, 5, 0, 0)
    
    # Create metric displays
    self.metrics_displays = {}
    
    # Active Clients with bar
    active_clients_layout = QHBoxLayout()
    active_clients_label = QLabel("Active Clients:")
    active_clients_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
    active_clients_label.setFixedWidth(80)
    
    self.active_clients_bar = QProgressBar()
    self.active_clients_bar.setRange(0, 9)
    self.active_clients_bar.setValue(8)  # Example: 8 clients active
    self.active_clients_bar.setFixedHeight(16)
    self.active_clients_bar.setStyleSheet(f"""
        QProgressBar {{
            border: 1px solid {COLORS['border']};
            border-radius: 2px;
            text-align: center;
            font-size: 10px;
            color: white;
        }}
        QProgressBar::chunk {{
            background-color: {COLORS['positive']};
        }}
    """)
    self.active_clients_bar.setFormat("8/9")
    
    active_clients_layout.addWidget(active_clients_label)
    active_clients_layout.addWidget(self.active_clients_bar)
    metrics_stats_layout.addLayout(active_clients_layout)
    
    # Memory usage
    memory_layout = QHBoxLayout()
    memory_label = QLabel("Memory:")
    memory_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
    memory_label.setFixedWidth(80)
    
    self.memory_value = QLabel("45%")
    self.memory_value.setStyleSheet(f"color: {COLORS['positive']}; font-size: 11px;")
    self.memory_value.setAlignment(Qt.AlignmentFlag.AlignRight)
    
    memory_layout.addWidget(memory_label)
    memory_layout.addWidget(self.memory_value)
    memory_layout.addStretch()
    metrics_stats_layout.addLayout(memory_layout)
    
    # CPU usage
    cpu_layout = QHBoxLayout()
    cpu_label = QLabel("CPU:")
    cpu_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
    cpu_label.setFixedWidth(80)
    
    self.cpu_value = QLabel("22%")
    self.cpu_value.setStyleSheet(f"color: {COLORS['positive']}; font-size: 11px;")
    self.cpu_value.setAlignment(Qt.AlignmentFlag.AlignRight)
    
    cpu_layout.addWidget(cpu_label)
    cpu_layout.addWidget(self.cpu_value)
    cpu_layout.addStretch()
    metrics_stats_layout.addLayout(cpu_layout)
    
    # API Calls/sec
    api_layout = QHBoxLayout()
    api_label = QLabel("API Calls/Sec:")
    api_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
    api_label.setFixedWidth(80)
    
    self.api_value = QLabel("127")
    self.api_value.setStyleSheet(f"color: {COLORS['neutral']}; font-size: 11px;")
    self.api_value.setAlignment(Qt.AlignmentFlag.AlignRight)
    
    api_layout.addWidget(api_label)
    api_layout.addWidget(self.api_value)
    api_layout.addStretch()
    metrics_stats_layout.addLayout(api_layout)
    
    # System Health Status (compact)
    health_layout = QHBoxLayout()
    health_label = QLabel("System Health:")
    health_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
    health_label.setFixedWidth(80)
    
    self.health_status = QLabel("92/100")
    self.health_status.setStyleSheet(f"color: {COLORS['positive']}; font-size: 11px; font-weight: bold;")
    self.health_status.setAlignment(Qt.AlignmentFlag.AlignRight)
    
    health_layout.addWidget(health_label)
    health_layout.addWidget(self.health_status)
    health_layout.addStretch()
    metrics_stats_layout.addLayout(health_layout)
    
    metrics_stats_widget.setLayout(metrics_stats_layout)
    metrics_layout.addWidget(metrics_stats_widget)
    
    metrics_group.setLayout(metrics_layout)
    layout.addWidget(metrics_group)
    
    panel.setLayout(layout)
    return panel

# ==============================================================================
# ADDITIONAL METHODS TO ADD TO SpyderG05_TradingDashboard CLASS
# ==============================================================================

def update_prometheus_metrics(self):
    """Update Prometheus metrics display (call from timer)"""
    # This would get real data from SpyderB15_PrometheusMetrics
    # For now, simulate updates
    
    import random
    
    # Update client statuses
    for client_id, indicator in self.client_indicators.items():
        # Simulate random status
        if random.random() > 0.9:  # 10% chance of being down
            indicator.setStyleSheet(f"color: {COLORS['negative']}; font-size: 11px;")
        else:
            indicator.setStyleSheet(f"color: {COLORS['positive']}; font-size: 11px;")
    
    # Update metrics
    active_count = sum(1 for _ in self.client_indicators.values() 
                      if random.random() > 0.1)
    self.active_clients_bar.setValue(active_count)
    self.active_clients_bar.setFormat(f"{active_count}/9")
    
    # Update system metrics
    memory = random.randint(40, 60)
    self.memory_value.setText(f"{memory}%")
    self.memory_value.setStyleSheet(
        f"color: {COLORS['positive'] if memory < 70 else COLORS['warning']}; font-size: 11px;"
    )
    
    cpu = random.randint(15, 35)
    self.cpu_value.setText(f"{cpu}%")
    self.cpu_value.setStyleSheet(
        f"color: {COLORS['positive'] if cpu < 50 else COLORS['warning']}; font-size: 11px;"
    )
    
    api_calls = random.randint(100, 150)
    self.api_value.setText(str(api_calls))
    self.api_value.setStyleSheet(
        f"color: {COLORS['neutral'] if api_calls < 180 else COLORS['warning']}; font-size: 11px;"
    )
    
    # Calculate health score
    health_score = 100
    health_score -= (memory - 45) if memory > 45 else 0
    health_score -= (cpu - 20) if cpu > 20 else 0
    health_score -= (api_calls - 100) / 10 if api_calls > 100 else 0
    health_score = max(0, min(100, int(health_score)))
    
    self.health_status.setText(f"{health_score}/100")
    if health_score > 80:
        color = COLORS['positive']
    elif health_score > 60:
        color = COLORS['neutral']
    else:
        color = COLORS['negative']
    self.health_status.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")

def setup_prometheus_timer(self):
    """Add this to setup_timers() method"""
    # Prometheus metrics update timer
    self.prometheus_timer = QTimer()
    self.prometheus_timer.timeout.connect(self.update_prometheus_metrics)
    self.prometheus_timer.start(2000)  # Update every 2 seconds

# ==============================================================================
# INTEGRATION WITH REAL PROMETHEUS DATA
# ==============================================================================

def connect_to_prometheus_collector(self):
    """
    Connect to the actual Prometheus metrics collector (SpyderB15)
    This would be called in __init__ or setup
    """
    try:
        # Import the passive collector functions
        from SpyderG07_PrometheusMetricsDisplay import get_client_status, get_system_metrics
        
        # Store references
        self.get_client_status = get_client_status
        self.get_system_metrics = get_system_metrics
        
        # Initial update
        self.update_prometheus_metrics_real()
        
    except ImportError:
        self.logger.warning("Prometheus collector not available, using simulation")
        
def update_prometheus_metrics_real(self):
    """Update with real data from Prometheus collector"""
    if hasattr(self, 'get_client_status'):
        # Get real client status
        for i in range(9):
            status = self.get_client_status(i)
            client_key = f"CLIENT {i}"
            if client_key in self.client_indicators:
                if status['connected']:
                    self.client_indicators[client_key].setStyleSheet(
                        f"color: {COLORS['positive']}; font-size: 11px;"
                    )
                else:
                    self.client_indicators[client_key].setStyleSheet(
                        f"color: {COLORS['negative']}; font-size: 11px;"
                    )
        
        # Get real system metrics
        metrics = self.get_system_metrics()
        
        # Update displays
        self.memory_value.setText(f"{metrics['memory_percent']:.0f}%")
        self.cpu_value.setText(f"{metrics['cpu_percent']:.0f}%")
        self.api_value.setText(str(metrics['api_calls_per_sec']))
        
        # Update health score based on real metrics
        health = 100
        if metrics['memory_percent'] > 70:
            health -= 20
        if metrics['cpu_percent'] > 50:
            health -= 15
        if metrics['api_calls_per_sec'] > 180:
            health -= 10
            
        self.health_status.setText(f"{health}/100")