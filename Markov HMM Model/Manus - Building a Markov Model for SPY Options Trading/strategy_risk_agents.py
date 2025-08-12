#!/usr/bin/env python3
"""
Strategy and Risk Management Agents for SPY HMM Trading System
Implements sophisticated strategy generation and risk management capabilities.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import threading
import time
import queue
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Import base classes from the main agent file
from spy_hmm_ai_agent import (
    BaseAgent, MessageType, TradingSignal, MarketRegime, 
    SystemState, AgentMessage
)

logger = logging.getLogger(__name__)

class StrategyAgent(BaseAgent):
    """Agent responsible for generating trading strategies and signals"""
    
    def __init__(self, message_bus, strategy_config: Dict[str, Any] = None):
        super().__init__("StrategyAgent", message_bus)
        self.strategy_config = strategy_config or self._default_strategy_config()
        self.current_regime = MarketRegime.TRANSITIONAL_NEUTRAL
        self.regime_confidence = 0.0
        self.market_data = {}
        self.strategy_models = {}
        self.signal_history = []
        self.performance_tracker = {}
        
        # Initialize regime-specific models
        self._initialize_strategy_models()
        
    def _default_strategy_config(self) -> Dict[str, Any]:
        """Default strategy configuration"""
        return {
            "min_confidence_threshold": 0.6,
            "signal_strength_threshold": 0.53,
            "max_signals_per_day": 5,
            "lookback_period": 20,
            "retraining_frequency": 50,  # retrain every 50 signals
            "regime_strategies": {
                MarketRegime.LOW_VOLATILITY_TRENDING: {
                    "strategy_type": "momentum",
                    "features": ["momentum_5", "momentum_10", "rsi", "macd"],
                    "signal_threshold": 0.55
                },
                MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: {
                    "strategy_type": "mean_reversion",
                    "features": ["rsi", "bb_width", "volatility", "returns"],
                    "signal_threshold": 0.60
                },
                MarketRegime.TRANSITIONAL_NEUTRAL: {
                    "strategy_type": "conservative",
                    "features": ["volatility", "volume_ratio", "rsi"],
                    "signal_threshold": 0.65
                }
            }
        }
    
    def _initialize_strategy_models(self):
        """Initialize machine learning models for each regime"""
        for regime in MarketRegime:
            self.strategy_models[regime] = {
                "model": RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42
                ),
                "scaler": StandardScaler(),
                "trained": False,
                "last_training": None,
                "performance": {"accuracy": 0.0, "trades": 0, "wins": 0}
            }
    
    def process_data(self, market_data: Dict[str, pd.DataFrame]) -> List[TradingSignal]:
        """Generate trading signals based on current market regime and data"""
        signals = []
        
        try:
            if not market_data or "SPY" not in market_data:
                return signals
            
            spy_data = market_data["SPY"]
            
            # Check if we have enough data
            if len(spy_data) < self.strategy_config["lookback_period"]:
                logger.warning("Insufficient data for signal generation")
                return signals
            
            # Generate regime-specific signals
            if self.regime_confidence >= self.strategy_config["min_confidence_threshold"]:
                signal = self._generate_regime_signal(spy_data, self.current_regime)
                if signal:
                    signals.append(signal)
            
            # Update signal history
            self.signal_history.extend(signals)
            
            # Retrain models if needed
            if len(self.signal_history) % self.strategy_config["retraining_frequency"] == 0:
                self._retrain_models()
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
        
        return signals
    
    def _generate_regime_signal(self, data: pd.DataFrame, regime: MarketRegime) -> Optional[TradingSignal]:
        """Generate a signal for a specific regime"""
        try:
            regime_config = self.strategy_config["regime_strategies"][regime]
            model_info = self.strategy_models[regime]
            
            # Prepare features
            features = self._prepare_signal_features(data, regime_config["features"])
            if features is None:
                return None
            
            # Train model if not trained
            if not model_info["trained"]:
                self._train_regime_model(data, regime)
                if not model_info["trained"]:
                    return None
            
            # Generate prediction
            model = model_info["model"]
            scaler = model_info["scaler"]
            
            # Get latest features for prediction
            latest_features = features[-1:].reshape(1, -1)
            latest_features_scaled = scaler.transform(latest_features)
            
            # Predict signal probability
            signal_proba = model.predict_proba(latest_features_scaled)[0]
            
            # Determine signal type and strength
            signal_strength = max(signal_proba)
            signal_threshold = regime_config["signal_threshold"]
            
            if signal_strength >= signal_threshold:
                # Determine signal direction
                signal_class = model.predict(latest_features_scaled)[0]
                signal_type = "BUY" if signal_class == 1 else "SELL"
                
                # Calculate position sizing and risk parameters
                position_size = self._calculate_position_size(signal_strength, regime)
                stop_loss, take_profit = self._calculate_risk_parameters(
                    data, signal_type, regime
                )
                
                signal = TradingSignal(
                    symbol="SPY",
                    signal_type=signal_type,
                    confidence=signal_strength,
                    regime=regime,
                    strategy=regime_config["strategy_type"],
                    entry_price=data['Close'].iloc[-1],
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_size=position_size
                )
                
                logger.info(f"Generated {signal_type} signal for {regime.name} "
                          f"with confidence {signal_strength:.3f}")
                
                return signal
                
        except Exception as e:
            logger.error(f"Error generating regime signal: {e}")
        
        return None
    
    def _prepare_signal_features(self, data: pd.DataFrame, feature_names: List[str]) -> Optional[np.ndarray]:
        """Prepare features for signal generation"""
        try:
            # Filter available features
            available_features = [f for f in feature_names if f in data.columns]
            if not available_features:
                return None
            
            # Extract features
            features_df = data[available_features].copy()
            
            # Handle missing values
            features_df = features_df.fillna(method='ffill').fillna(method='bfill')
            features_df = features_df.dropna()
            
            if len(features_df) < self.strategy_config["lookback_period"]:
                return None
            
            return features_df.values
            
        except Exception as e:
            logger.error(f"Error preparing signal features: {e}")
            return None
    
    def _train_regime_model(self, data: pd.DataFrame, regime: MarketRegime):
        """Train the machine learning model for a specific regime"""
        try:
            regime_config = self.strategy_config["regime_strategies"][regime]
            model_info = self.strategy_models[regime]
            
            # Prepare training data
            features = self._prepare_signal_features(data, regime_config["features"])
            if features is None or len(features) < 50:
                logger.warning(f"Insufficient data to train {regime.name} model")
                return
            
            # Create target variable (future returns)
            returns = data['returns'].shift(-1).dropna()
            
            # Align features and targets
            min_length = min(len(features), len(returns))
            X = features[:min_length]
            y = (returns[:min_length] > 0).astype(int)  # Binary classification
            
            if len(X) < 30:
                return
            
            # Scale features
            X_scaled = model_info["scaler"].fit_transform(X)
            
            # Train model
            model_info["model"].fit(X_scaled, y)
            model_info["trained"] = True
            model_info["last_training"] = datetime.now()
            
            logger.info(f"Trained {regime.name} model with {len(X)} samples")
            
        except Exception as e:
            logger.error(f"Error training regime model: {e}")
    
    def _calculate_position_size(self, signal_strength: float, regime: MarketRegime) -> float:
        """Calculate position size based on signal strength and regime"""
        base_size = 0.02  # 2% of portfolio
        
        # Adjust based on signal strength
        strength_multiplier = signal_strength / 0.5  # Normalize to 0.5 baseline
        
        # Adjust based on regime
        regime_multipliers = {
            MarketRegime.LOW_VOLATILITY_TRENDING: 1.2,
            MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: 0.8,
            MarketRegime.TRANSITIONAL_NEUTRAL: 0.6
        }
        
        regime_multiplier = regime_multipliers.get(regime, 1.0)
        
        position_size = base_size * strength_multiplier * regime_multiplier
        
        # Cap position size
        return min(position_size, 0.05)  # Max 5% of portfolio
    
    def _calculate_risk_parameters(self, data: pd.DataFrame, signal_type: str, 
                                 regime: MarketRegime) -> Tuple[float, float]:
        """Calculate stop loss and take profit levels"""
        current_price = data['Close'].iloc[-1]
        volatility = data['volatility'].iloc[-1] if 'volatility' in data.columns else 0.2
        
        # Adjust risk parameters based on regime
        if regime == MarketRegime.LOW_VOLATILITY_TRENDING:
            stop_loss_pct = 0.02  # 2%
            take_profit_pct = 0.04  # 4%
        elif regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING:
            stop_loss_pct = 0.03  # 3%
            take_profit_pct = 0.03  # 3%
        else:  # Transitional
            stop_loss_pct = 0.015  # 1.5%
            take_profit_pct = 0.025  # 2.5%
        
        # Adjust for volatility
        vol_adjustment = min(volatility / 0.2, 2.0)  # Cap at 2x adjustment
        stop_loss_pct *= vol_adjustment
        take_profit_pct *= vol_adjustment
        
        if signal_type == "BUY":
            stop_loss = current_price * (1 - stop_loss_pct)
            take_profit = current_price * (1 + take_profit_pct)
        else:  # SELL
            stop_loss = current_price * (1 + stop_loss_pct)
            take_profit = current_price * (1 - take_profit_pct)
        
        return stop_loss, take_profit
    
    def _retrain_models(self):
        """Retrain all regime models with recent data"""
        logger.info("Retraining strategy models...")
        if self.market_data and "SPY" in self.market_data:
            for regime in MarketRegime:
                self._train_regime_model(self.market_data["SPY"], regime)
    
    def _run(self):
        """Main strategy agent loop"""
        while self.running:
            try:
                # Process messages
                while not self.message_queue.empty():
                    message = self.message_queue.get()
                    
                    if message.message_type == MessageType.REGIME_UPDATE:
                        self.current_regime = message.data["regime"]
                        self.regime_confidence = message.data["confidence"]
                        
                    elif message.message_type == MessageType.MARKET_DATA_UPDATE:
                        self.market_data = message.data["data"]
                        
                        # Generate signals if we have both regime and data
                        if (self.current_regime is not None and 
                            self.regime_confidence > 0):
                            signals = self.process_data(self.market_data)
                            
                            for signal in signals:
                                self.send_message(
                                    "ALL",
                                    MessageType.SIGNAL_GENERATED,
                                    {"signal": signal}
                                )
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in StrategyAgent main loop: {e}")
                time.sleep(5)

class RiskManagementAgent(BaseAgent):
    """Agent responsible for risk management and position monitoring"""
    
    def __init__(self, message_bus, risk_config: Dict[str, Any] = None):
        super().__init__("RiskManagementAgent", message_bus)
        self.risk_config = risk_config or self._default_risk_config()
        self.portfolio_positions = {}
        self.risk_metrics = {}
        self.current_regime = MarketRegime.TRANSITIONAL_NEUTRAL
        self.market_data = {}
        self.alert_history = []
        
    def _default_risk_config(self) -> Dict[str, Any]:
        """Default risk management configuration"""
        return {
            "max_portfolio_risk": 0.10,  # 10% max portfolio risk
            "max_single_position": 0.05,  # 5% max single position
            "max_daily_loss": 0.03,  # 3% max daily loss
            "max_drawdown": 0.15,  # 15% max drawdown
            "position_limits": {
                MarketRegime.LOW_VOLATILITY_TRENDING: 0.80,  # 80% max exposure
                MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: 0.60,  # 60% max exposure
                MarketRegime.TRANSITIONAL_NEUTRAL: 0.40  # 40% max exposure
            },
            "volatility_scaling": True,
            "correlation_limits": 0.70,  # Max correlation between positions
            "rebalance_threshold": 0.05  # Rebalance when allocation drifts 5%
        }
    
    def process_data(self, signal: TradingSignal) -> Dict[str, Any]:
        """Process and validate trading signals for risk compliance"""
        risk_assessment = {
            "approved": False,
            "adjusted_size": 0.0,
            "risk_score": 0.0,
            "warnings": [],
            "adjustments": []
        }
        
        try:
            # Check portfolio risk limits
            current_exposure = self._calculate_current_exposure()
            regime_limit = self.risk_config["position_limits"][self.current_regime]
            
            if current_exposure >= regime_limit:
                risk_assessment["warnings"].append(
                    f"Portfolio exposure ({current_exposure:.2%}) exceeds regime limit ({regime_limit:.2%})"
                )
                return risk_assessment
            
            # Check position size limits
            max_position_size = min(
                self.risk_config["max_single_position"],
                signal.position_size or 0.02
            )
            
            # Adjust for volatility if enabled
            if self.risk_config["volatility_scaling"]:
                volatility_adjustment = self._calculate_volatility_adjustment()
                max_position_size *= volatility_adjustment
            
            # Check if position size needs adjustment
            adjusted_size = min(signal.position_size or 0.02, max_position_size)
            
            if adjusted_size != signal.position_size:
                risk_assessment["adjustments"].append(
                    f"Position size adjusted from {signal.position_size:.3f} to {adjusted_size:.3f}"
                )
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(signal, adjusted_size)
            
            # Approve signal if risk is acceptable
            if risk_score <= 1.0:  # Risk score threshold
                risk_assessment["approved"] = True
                risk_assessment["adjusted_size"] = adjusted_size
                risk_assessment["risk_score"] = risk_score
            else:
                risk_assessment["warnings"].append(
                    f"Risk score ({risk_score:.2f}) exceeds threshold (1.0)"
                )
            
        except Exception as e:
            logger.error(f"Error in risk assessment: {e}")
            risk_assessment["warnings"].append(f"Risk assessment error: {e}")
        
        return risk_assessment
    
    def _calculate_current_exposure(self) -> float:
        """Calculate current portfolio exposure"""
        total_exposure = 0.0
        for position in self.portfolio_positions.values():
            total_exposure += abs(position.get("size", 0.0))
        return total_exposure
    
    def _calculate_volatility_adjustment(self) -> float:
        """Calculate volatility-based position size adjustment"""
        if not self.market_data or "SPY" not in self.market_data:
            return 1.0
        
        try:
            spy_data = self.market_data["SPY"]
            if "volatility" not in spy_data.columns:
                return 1.0
            
            current_vol = spy_data["volatility"].iloc[-1]
            baseline_vol = 0.20  # 20% baseline volatility
            
            # Inverse relationship: higher volatility = smaller positions
            vol_adjustment = baseline_vol / max(current_vol, 0.05)
            
            # Cap adjustment between 0.5 and 2.0
            return max(0.5, min(2.0, vol_adjustment))
            
        except Exception as e:
            logger.error(f"Error calculating volatility adjustment: {e}")
            return 1.0
    
    def _calculate_risk_score(self, signal: TradingSignal, position_size: float) -> float:
        """Calculate overall risk score for a signal"""
        risk_score = 0.0
        
        try:
            # Base risk from position size
            risk_score += position_size / self.risk_config["max_single_position"]
            
            # Regime risk adjustment
            regime_risk_multipliers = {
                MarketRegime.LOW_VOLATILITY_TRENDING: 0.8,
                MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: 1.2,
                MarketRegime.TRANSITIONAL_NEUTRAL: 1.0
            }
            
            regime_multiplier = regime_risk_multipliers.get(self.current_regime, 1.0)
            risk_score *= regime_multiplier
            
            # Confidence adjustment (lower confidence = higher risk)
            confidence_adjustment = 2.0 - signal.confidence
            risk_score *= confidence_adjustment
            
            # Portfolio concentration risk
            current_exposure = self._calculate_current_exposure()
            concentration_risk = current_exposure / self.risk_config["max_portfolio_risk"]
            risk_score += concentration_risk * 0.3
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            risk_score = 2.0  # High risk score on error
        
        return risk_score
    
    def _monitor_portfolio_risk(self):
        """Monitor ongoing portfolio risk metrics"""
        try:
            # Calculate current risk metrics
            self.risk_metrics = {
                "total_exposure": self._calculate_current_exposure(),
                "largest_position": self._get_largest_position_size(),
                "portfolio_var": self._calculate_portfolio_var(),
                "correlation_risk": self._calculate_correlation_risk(),
                "regime_exposure": self._calculate_regime_exposure()
            }
            
            # Check for risk alerts
            alerts = self._check_risk_alerts()
            
            # Send alerts if any
            for alert in alerts:
                self.send_message(
                    "ALL",
                    MessageType.RISK_ALERT,
                    {"alert": alert, "risk_metrics": self.risk_metrics}
                )
                
        except Exception as e:
            logger.error(f"Error monitoring portfolio risk: {e}")
    
    def _get_largest_position_size(self) -> float:
        """Get the size of the largest position"""
        if not self.portfolio_positions:
            return 0.0
        return max(abs(pos.get("size", 0.0)) for pos in self.portfolio_positions.values())
    
    def _calculate_portfolio_var(self) -> float:
        """Calculate portfolio Value at Risk (simplified)"""
        # Simplified VaR calculation
        total_exposure = self._calculate_current_exposure()
        if not self.market_data or "SPY" not in self.market_data:
            return total_exposure * 0.02  # 2% default VaR
        
        try:
            spy_data = self.market_data["SPY"]
            if "volatility" in spy_data.columns:
                volatility = spy_data["volatility"].iloc[-1]
                # 95% VaR approximation
                var_95 = total_exposure * volatility * 1.645 / np.sqrt(252)
                return var_95
        except:
            pass
        
        return total_exposure * 0.02
    
    def _calculate_correlation_risk(self) -> float:
        """Calculate correlation risk (simplified)"""
        # For SPY-focused trading, correlation risk is limited
        # This would be more complex with multiple assets
        return 0.0
    
    def _calculate_regime_exposure(self) -> Dict[str, float]:
        """Calculate exposure by regime"""
        regime_exposure = {regime.name: 0.0 for regime in MarketRegime}
        
        for position in self.portfolio_positions.values():
            regime = position.get("regime", MarketRegime.TRANSITIONAL_NEUTRAL)
            regime_exposure[regime.name] += abs(position.get("size", 0.0))
        
        return regime_exposure
    
    def _check_risk_alerts(self) -> List[str]:
        """Check for risk limit violations"""
        alerts = []
        
        # Check total exposure
        if self.risk_metrics["total_exposure"] > self.risk_config["max_portfolio_risk"]:
            alerts.append(
                f"Portfolio exposure ({self.risk_metrics['total_exposure']:.2%}) "
                f"exceeds limit ({self.risk_config['max_portfolio_risk']:.2%})"
            )
        
        # Check largest position
        if self.risk_metrics["largest_position"] > self.risk_config["max_single_position"]:
            alerts.append(
                f"Largest position ({self.risk_metrics['largest_position']:.2%}) "
                f"exceeds limit ({self.risk_config['max_single_position']:.2%})"
            )
        
        # Check VaR
        if self.risk_metrics["portfolio_var"] > self.risk_config["max_daily_loss"]:
            alerts.append(
                f"Portfolio VaR ({self.risk_metrics['portfolio_var']:.2%}) "
                f"exceeds daily loss limit ({self.risk_config['max_daily_loss']:.2%})"
            )
        
        return alerts
    
    def _run(self):
        """Main risk management agent loop"""
        while self.running:
            try:
                # Process messages
                while not self.message_queue.empty():
                    message = self.message_queue.get()
                    
                    if message.message_type == MessageType.SIGNAL_GENERATED:
                        signal = message.data["signal"]
                        risk_assessment = self.process_data(signal)
                        
                        # Send risk assessment back
                        self.send_message(
                            "StrategyAgent",
                            MessageType.RISK_ALERT,
                            {"risk_assessment": risk_assessment, "signal": signal}
                        )
                        
                    elif message.message_type == MessageType.REGIME_UPDATE:
                        self.current_regime = message.data["regime"]
                        
                    elif message.message_type == MessageType.MARKET_DATA_UPDATE:
                        self.market_data = message.data["data"]
                        
                    elif message.message_type == MessageType.POSITION_UPDATE:
                        self.portfolio_positions = message.data["positions"]
                
                # Monitor portfolio risk periodically
                self._monitor_portfolio_risk()
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in RiskManagementAgent main loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    print("Strategy and Risk Management Agents")
    print("This module provides additional agents for the SPY HMM trading system.")
    print("Import and use with the main spy_hmm_ai_agent.py module.")

