# Add these modifications to your SpyderTestDashboard_v21.py file:

# =========================================================================
# STEP 1: Add import at the top after other imports
# =========================================================================
try:
    from SpyderG06_RiskParametersDialog import show_risk_parameters_dialog
except ImportError:
    # If running from different directory structure
    try:
        from SpyderG_GUI.SpyderG06_RiskParametersDialog import show_risk_parameters_dialog
    except ImportError:
        print("Warning: Risk Parameters Dialog not found")
        show_risk_parameters_dialog = None

# =========================================================================
# STEP 2: In the __init__ method of AutomatedTradingDashboard, add:
# =========================================================================
self.current_risk_params = None  # Store current risk parameters

# =========================================================================
# STEP 3: Replace the existing show_risk_parameters method with:
# =========================================================================
def show_risk_parameters(self):
    """Show risk parameters dialog"""
    if show_risk_parameters_dialog is None:
        QMessageBox.warning(self, "Module Not Found", 
                          "Risk Parameters Dialog module not found.\n"
                          "Please ensure SpyderG06_RiskParametersDialog.py is in the correct location.")
        return
        
    # Show the dialog
    params = show_risk_parameters_dialog(self, self.current_risk_params)
    
    if params:
        # Parameters were saved
        self.current_risk_params = params
        self.add_system_log("Risk parameters updated successfully")
        
        # Update risk monitoring displays
        self.update_risk_parameters(params)

# =========================================================================
# STEP 4: Add this new method to handle parameter updates:
# =========================================================================
def update_risk_parameters(self, params):
    """Update system with new risk parameters"""
    self.current_risk_params = params
    
    # Clear and update automation status log
    self.auto_log.clear()
    self.auto_log.append(f"Risk Profile: {params['global']['active_profile']}")
    self.auto_log.append(f"Risk/Trade: {params['global']['risk_per_trade']}%")
    self.auto_log.append(f"Max Contracts: {params['global']['max_contracts']}")
    self.auto_log.append(f"Daily Loss Limit: {params['global']['max_daily_loss']}%")
    
    # Update Greek limits status
    self.update_greek_limits(params['global'])
    
    # Log dynamic rules status
    if params['dynamic_rules']['enable_iv_scaling']:
        self.add_system_log("IV-based position scaling ENABLED")
    if params['dynamic_rules']['enable_regime_adjustment']:
        self.add_system_log("Market regime adjustments ACTIVE")
    if params['dynamic_rules']['zero_dte_enabled']:
        self.add_system_log(f"0DTE trading ENABLED (size multiplier: {params['dynamic_rules']['zero_dte_reduction']})")
    
    # Update any dependent systems
    self.update_risk_monitoring()

# =========================================================================
# STEP 5: Add method to update Greek limits based on parameters:
# =========================================================================
def update_greek_limits(self, global_params):
    """Update Greek display limits based on risk parameters"""
    # Update Greek bar displays with new limits
    max_delta = global_params['max_delta']
    max_vega = abs(global_params['max_vega'])
    max_theta = abs(global_params['max_theta'])
    
    # Update status based on current values vs limits
    delta_pct = abs(self.greek_risks.delta) / max_delta if max_delta > 0 else 0
    vega_pct = abs(self.greek_risks.vega) / max_vega if max_vega > 0 else 0
    theta_pct = abs(self.greek_risks.theta) / max_theta if max_theta > 0 else 0
    
    # Update Greek bar statuses
    delta_status = "NORMAL" if delta_pct < 0.7 else "LIMIT APPROACHING" if delta_pct < 0.9 else "AT LIMIT"
    vega_status = "NORMAL" if vega_pct < 0.7 else "LIMIT APPROACHING" if vega_pct < 0.9 else "AT LIMIT"
    theta_status = "HARVESTING TIME" if theta_pct > 0.3 else "LOW DECAY"
    
    self.greek_bars['delta'].set_value(self.greek_risks.delta, delta_status)
    self.greek_bars['vega'].set_value(self.greek_risks.vega, vega_status)
    self.greek_bars['theta'].set_value(self.greek_risks.theta, theta_status)

# =========================================================================
# STEP 6: Update the update_risk_monitoring method:
# =========================================================================
def update_risk_monitoring(self):
    """Update risk displays based on current parameters"""
    if not self.current_risk_params:
        return
        
    # This is called periodically to update displays
    # You can add more risk monitoring logic here
    pass
