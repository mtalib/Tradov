#!/usr/bin/env python3
"""
Complete SPY HMM AI Trading System
A comprehensive demonstration of the autonomous HMM-based trading system.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
import time
import threading
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import dataclass, field

# Import our agent modules
from spy_hmm_ai_agent import (
    MessageBus, DataAgent, HMMAgent, MarketRegime, 
    MessageType, TradingSignal, SystemState
)
from strategy_risk_agents import StrategyAgent, RiskManagementAgent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExecutionAgent:
    """Simple execution agent for demonstration purposes"""
    
    def __init__(self, message_bus, initial_capital: float = 100000):
        self.agent_id = "ExecutionAgent"
        self.message_bus = message_bus
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.trade_history = []
        self.running = False
        self.message_queue = []
        
    def receive_message(self, message):
        """Receive messages from other agents"""
        self.message_queue.append(message)
        
    def execute_signal(self, signal: TradingSignal, risk_assessment: Dict[str, Any]):
        """Execute a trading signal (simulation)"""
        if not risk_assessment.get("approved", False):
            logger.info(f"Signal rejected by risk management: {signal.signal_type}")
            return
        
        # Simulate trade execution
        trade = {
            "timestamp": datetime.now(),
            "symbol": signal.symbol,
            "signal_type": signal.signal_type,
            "entry_price": signal.entry_price,
            "position_size": risk_assessment["adjusted_size"],
            "confidence": signal.confidence,
            "regime": signal.regime.name,
            "strategy": signal.strategy,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit
        }
        
        # Update positions
        position_value = self.current_capital * risk_assessment["adjusted_size"]
        
        if signal.signal_type == "BUY":
            self.positions[signal.symbol] = {
                "size": risk_assessment["adjusted_size"],
                "entry_price": signal.entry_price,
                "value": position_value,
                "regime": signal.regime,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit
            }
        elif signal.signal_type == "SELL":
            # For simplicity, assume we're closing existing positions
            if signal.symbol in self.positions:
                del self.positions[signal.symbol]
        
        self.trade_history.append(trade)
        
        logger.info(f"Executed {signal.signal_type} signal for {signal.symbol} "
                   f"at ${signal.entry_price:.2f} with size {risk_assessment['adjusted_size']:.3f}")
        
        # Send position update
        message = {
            "sender": self.agent_id,
            "receiver": "ALL",
            "message_type": MessageType.POSITION_UPDATE,
            "data": {"positions": self.positions, "capital": self.current_capital}
        }
        # Note: In full implementation, this would go through the message bus
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.trade_history:
            return {"total_trades": 0, "performance": "No trades executed"}
        
        df_trades = pd.DataFrame(self.trade_history)
        
        summary = {
            "total_trades": len(self.trade_history),
            "buy_signals": len(df_trades[df_trades["signal_type"] == "BUY"]),
            "sell_signals": len(df_trades[df_trades["signal_type"] == "SELL"]),
            "regime_distribution": df_trades["regime"].value_counts().to_dict(),
            "strategy_distribution": df_trades["strategy"].value_counts().to_dict(),
            "average_confidence": df_trades["confidence"].mean(),
            "current_positions": len(self.positions),
            "capital_utilization": sum(pos["size"] for pos in self.positions.values())
        }
        
        return summary

class TradingSystemManager:
    """Main system manager that coordinates all agents"""
    
    def __init__(self, symbols: List[str] = None, initial_capital: float = 100000):
        self.symbols = symbols or ["SPY"]
        self.initial_capital = initial_capital
        
        # Initialize message bus
        self.message_bus = MessageBus()
        
        # Initialize agents
        self.data_agent = DataAgent(self.message_bus, self.symbols)
        self.hmm_agent = HMMAgent(self.message_bus)
        self.strategy_agent = StrategyAgent(self.message_bus)
        self.risk_agent = RiskManagementAgent(self.message_bus)
        self.execution_agent = ExecutionAgent(self.message_bus, initial_capital)
        
        # System state
        self.system_state = SystemState()
        self.running = False
        
        # Performance tracking
        self.performance_history = []
        self.regime_history = []
        
    def start_system(self):
        """Start the complete trading system"""
        logger.info("Starting SPY HMM AI Trading System...")
        
        # Start message bus
        self.message_bus.start()
        
        # Register agents
        self.message_bus.register_agent(self.data_agent)
        self.message_bus.register_agent(self.hmm_agent)
        self.message_bus.register_agent(self.strategy_agent)
        self.message_bus.register_agent(self.risk_agent)
        
        # Start agents
        self.data_agent.start()
        self.hmm_agent.start()
        self.strategy_agent.start()
        self.risk_agent.start()
        
        self.running = True
        self.system_state.system_status = "RUNNING"
        
        logger.info("All agents started successfully")
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_system)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_system(self):
        """Stop the trading system"""
        logger.info("Stopping SPY HMM AI Trading System...")
        
        self.running = False
        self.system_state.system_status = "STOPPING"
        
        # Stop agents
        self.data_agent.stop()
        self.hmm_agent.stop()
        self.strategy_agent.stop()
        self.risk_agent.stop()
        
        # Stop message bus
        self.message_bus.stop()
        
        self.system_state.system_status = "STOPPED"
        logger.info("System stopped successfully")
    
    def _monitor_system(self):
        """Monitor system performance and state"""
        while self.running:
            try:
                # Update system state
                self.system_state.last_update = datetime.now()
                
                # Track regime history
                if self.hmm_agent.current_regime is not None:
                    self.regime_history.append({
                        "timestamp": datetime.now(),
                        "regime": self.hmm_agent.current_regime.name,
                        "confidence": self.hmm_agent.regime_confidence
                    })
                
                # Track performance
                performance = self.execution_agent.get_performance_summary()
                self.performance_history.append({
                    "timestamp": datetime.now(),
                    **performance
                })
                
                # Log system status periodically
                if len(self.performance_history) % 10 == 0:
                    self._log_system_status()
                
                time.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                time.sleep(10)
    
    def _log_system_status(self):
        """Log current system status"""
        current_regime = self.hmm_agent.current_regime
        regime_confidence = self.hmm_agent.regime_confidence
        
        logger.info(f"System Status - Regime: {current_regime.name if current_regime else 'Unknown'}, "
                   f"Confidence: {regime_confidence:.3f}, "
                   f"Trades: {len(self.execution_agent.trade_history)}, "
                   f"Positions: {len(self.execution_agent.positions)}")
    
    def get_system_report(self) -> Dict[str, Any]:
        """Generate comprehensive system report"""
        report = {
            "system_status": self.system_state.system_status,
            "runtime": datetime.now() - (self.performance_history[0]["timestamp"] 
                                       if self.performance_history else datetime.now()),
            "current_regime": self.hmm_agent.current_regime.name if self.hmm_agent.current_regime else "Unknown",
            "regime_confidence": self.hmm_agent.regime_confidence,
            "execution_summary": self.execution_agent.get_performance_summary(),
            "regime_distribution": self._analyze_regime_distribution(),
            "agent_status": {
                "data_agent": "Running" if self.data_agent.running else "Stopped",
                "hmm_agent": "Running" if self.hmm_agent.running else "Stopped",
                "strategy_agent": "Running" if self.strategy_agent.running else "Stopped",
                "risk_agent": "Running" if self.risk_agent.running else "Stopped"
            }
        }
        
        return report
    
    def _analyze_regime_distribution(self) -> Dict[str, Any]:
        """Analyze regime distribution over time"""
        if not self.regime_history:
            return {"message": "No regime data available"}
        
        df_regimes = pd.DataFrame(self.regime_history)
        
        return {
            "total_regime_changes": len(df_regimes),
            "regime_counts": df_regimes["regime"].value_counts().to_dict(),
            "average_confidence": df_regimes["confidence"].mean(),
            "latest_regime": df_regimes["regime"].iloc[-1] if len(df_regimes) > 0 else "Unknown"
        }
    
    def create_performance_visualization(self, save_path: str = None):
        """Create performance visualization"""
        if not self.regime_history:
            logger.warning("No data available for visualization")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle("SPY HMM AI Trading System Performance", fontsize=16)
        
        # Regime distribution
        df_regimes = pd.DataFrame(self.regime_history)
        regime_counts = df_regimes["regime"].value_counts()
        axes[0, 0].pie(regime_counts.values, labels=regime_counts.index, autopct='%1.1f%%')
        axes[0, 0].set_title("Regime Distribution")
        
        # Regime confidence over time
        df_regimes["timestamp"] = pd.to_datetime(df_regimes["timestamp"])
        axes[0, 1].plot(df_regimes["timestamp"], df_regimes["confidence"])
        axes[0, 1].set_title("Regime Confidence Over Time")
        axes[0, 1].set_ylabel("Confidence")
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # Trade distribution by regime
        if self.execution_agent.trade_history:
            df_trades = pd.DataFrame(self.execution_agent.trade_history)
            trade_regime_counts = df_trades["regime"].value_counts()
            axes[1, 0].bar(trade_regime_counts.index, trade_regime_counts.values)
            axes[1, 0].set_title("Trades by Regime")
            axes[1, 0].set_ylabel("Number of Trades")
            axes[1, 0].tick_params(axis='x', rotation=45)
        else:
            axes[1, 0].text(0.5, 0.5, "No trades executed", ha='center', va='center')
            axes[1, 0].set_title("Trades by Regime")
        
        # System performance metrics
        if self.performance_history:
            df_perf = pd.DataFrame(self.performance_history)
            df_perf["timestamp"] = pd.to_datetime(df_perf["timestamp"])
            axes[1, 1].plot(df_perf["timestamp"], df_perf["total_trades"], label="Total Trades")
            axes[1, 1].plot(df_perf["timestamp"], df_perf["current_positions"], label="Current Positions")
            axes[1, 1].set_title("System Activity Over Time")
            axes[1, 1].set_ylabel("Count")
            axes[1, 1].legend()
            axes[1, 1].tick_params(axis='x', rotation=45)
        else:
            axes[1, 1].text(0.5, 0.5, "No performance data", ha='center', va='center')
            axes[1, 1].set_title("System Activity Over Time")
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Performance visualization saved to {save_path}")
        
        return fig

def run_demo_system(duration_minutes: int = 10):
    """Run a demonstration of the trading system"""
    print("=" * 60)
    print("SPY HMM AI Trading System - Live Demonstration")
    print("=" * 60)
    
    # Create and start system
    system = TradingSystemManager(["SPY"], initial_capital=100000)
    
    try:
        system.start_system()
        
        print(f"System running for {duration_minutes} minutes...")
        print("Monitoring regime detection and signal generation...")
        print("Press Ctrl+C to stop early")
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < duration_minutes * 60:
            time.sleep(30)  # Update every 30 seconds
            
            # Print current status
            current_regime = system.hmm_agent.current_regime
            confidence = system.hmm_agent.regime_confidence
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Regime: {current_regime.name if current_regime else 'Detecting...'} "
                  f"(Confidence: {confidence:.3f})")
            
            # Print recent trades
            recent_trades = system.execution_agent.trade_history[-3:]
            if recent_trades:
                print("Recent signals:")
                for trade in recent_trades:
                    print(f"  {trade['signal_type']} {trade['symbol']} "
                          f"@ ${trade['entry_price']:.2f} "
                          f"({trade['regime']}, {trade['confidence']:.3f})")
        
        print(f"\nDemo completed after {duration_minutes} minutes")
        
        # Generate final report
        report = system.get_system_report()
        print("\n" + "=" * 40)
        print("FINAL SYSTEM REPORT")
        print("=" * 40)
        
        print(f"System Status: {report['system_status']}")
        print(f"Current Regime: {report['current_regime']}")
        print(f"Regime Confidence: {report['regime_confidence']:.3f}")
        
        exec_summary = report['execution_summary']
        print(f"\nTrading Summary:")
        print(f"  Total Trades: {exec_summary['total_trades']}")
        print(f"  Buy Signals: {exec_summary.get('buy_signals', 0)}")
        print(f"  Sell Signals: {exec_summary.get('sell_signals', 0)}")
        print(f"  Average Confidence: {exec_summary.get('average_confidence', 0):.3f}")
        print(f"  Current Positions: {exec_summary['current_positions']}")
        
        if 'regime_distribution' in exec_summary:
            print(f"\nRegime Distribution in Trades:")
            for regime, count in exec_summary['regime_distribution'].items():
                print(f"  {regime}: {count}")
        
        # Create visualization
        try:
            fig = system.create_performance_visualization("/home/ubuntu/hmm_system_performance.png")
            print(f"\nPerformance visualization saved to: /home/ubuntu/hmm_system_performance.png")
        except Exception as e:
            print(f"Could not create visualization: {e}")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
    finally:
        system.stop_system()
        print("System stopped.")
    
    return system

if __name__ == "__main__":
    # Run the demonstration
    demo_system = run_demo_system(duration_minutes=5)  # 5-minute demo

