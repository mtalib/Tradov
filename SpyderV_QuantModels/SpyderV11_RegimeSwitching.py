#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV11_RegimeSwitching.py
Purpose: Markov Regime-Switching model for market state identification.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 14:15:00

Module Description:
    This module implements a Markov Regime-Switching model that identifies
    distinct market states (bull, bear, sideways) and their transition
    probabilities. The model recognizes that financial markets operate in
    different regimes with distinct statistical properties, enabling the
    Spyder system to adapt its behavior based on current market conditions.
    This provides the contextual intelligence that allows other models to
    use regime-appropriate parameters and strategies.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy.stats import norm, multivariate_normal
from scipy.optimize import minimize
import matplotlib.pyplot as plt

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RegimeParameters:
    """Parameters for a single regime."""
    mean: float                # Mean return in this regime
    variance: float           # Variance in this regime
    
    def validate(self) -> bool:
        """Validate regime parameters."""
        return self.variance > 0

@dataclass
class RegimeSwitchingParameters:
    """Complete parameters for the regime-switching model."""
    regimes: List[RegimeParameters]  # Parameters for each regime
    transition_matrix: np.ndarray    # Transition probability matrix
    initial_probs: np.ndarray       # Initial regime probabilities
    
    def validate(self) -> bool:
        """Validate all model parameters."""
        n_regimes = len(self.regimes)
        
        # Check regime parameters
        for regime in self.regimes:
            if not regime.validate():
                return False
        
        # Check transition matrix
        if (self.transition_matrix.shape != (n_regimes, n_regimes) or
            not np.allclose(self.transition_matrix.sum(axis=1), 1.0) or
            np.any(self.transition_matrix < 0)):
            return False
        
        # Check initial probabilities
        if (len(self.initial_probs) != n_regimes or
            not np.isclose(self.initial_probs.sum(), 1.0) or
            np.any(self.initial_probs < 0)):
            return False
        
        return True

class SpyderRegimeSwitchingModel:
    """
    Markov Regime-Switching model for market state identification.
    
    Features:
    - Multi-regime market state detection
    - EM algorithm for parameter estimation
    - Real-time regime probability updates
    - Regime transition analysis
    - Integration with other Spyder models
    """
    
    def __init__(self, n_regimes: int = 3, regime_names: Optional[List[str]] = None):
        self.n_regimes = n_regimes
        self.regime_names = regime_names or [f"Regime_{i+1}" for i in range(n_regimes)]
        self.parameters: Optional[RegimeSwitchingParameters] = None
        self.fitted_data: Optional[pd.Series] = None
        self.filtered_probs: Optional[np.ndarray] = None
        self.smoothed_probs: Optional[np.ndarray] = None
        self.log_likelihood: Optional[float] = None
        self.estimation_results: Dict[str, Any] = {}
        
    def fit(self, returns: pd.Series, max_iterations: int = 100, tolerance: float = 1e-6) -> Dict[str, Any]:
        """
        Fit regime-switching model using EM algorithm.
        
        Args:
            returns: Time series of returns
            max_iterations: Maximum EM iterations
            tolerance: Convergence tolerance
            
        Returns:
            Dictionary with estimation results
        """
        if len(returns) < 50:
            raise ValueError("Need at least 50 observations to fit regime-switching model")
        
        logger.info(f"Fitting {self.n_regimes}-regime switching model to {len(returns)} observations...")
        
        start_time = datetime.now()
        self.fitted_data = returns.copy()
        
        # Initialize parameters
        self._initialize_parameters(returns)
        
        # EM algorithm
        log_likelihoods = []
        
        for iteration in range(max_iterations):
            # E-step: Calculate regime probabilities
            self._expectation_step(returns)
            
            # M-step: Update parameters
            old_params = self._get_parameter_vector()
            self._maximization_step(returns)
            new_params = self._get_parameter_vector()
            
            # Calculate log-likelihood
            current_ll = self._calculate_log_likelihood(returns)
            log_likelihoods.append(current_ll)
            
            # Check convergence
            param_change = np.max(np.abs(new_params - old_params))
            if iteration > 0:
                ll_change = current_ll - log_likelihoods[-2]
                if param_change < tolerance and ll_change < tolerance:
                    logger.info(f"EM algorithm converged after {iteration + 1} iterations")
                    break
        
        end_time = datetime.now()
        
        # Final E-step for final probabilities
        self._expectation_step(returns)
        self.log_likelihood = log_likelihoods[-1]
        
        # Store results
        self.estimation_results = {
            'log_likelihood': self.log_likelihood,
            'aic': -2 * self.log_likelihood + 2 * self._count_parameters(),
            'bic': -2 * self.log_likelihood + np.log(len(returns)) * self._count_parameters(),
            'iterations': len(log_likelihoods),
            'converged': iteration < max_iterations - 1,
            'estimation_time': (end_time - start_time).total_seconds(),
            'log_likelihood_path': log_likelihoods
        }
        
        # Model validation
        self._validate_model()
        
        logger.info(f"Regime-switching estimation completed. Log-likelihood: {self.log_likelihood:.2f}")
        
        return self.estimation_results
    
    def _initialize_parameters(self, returns: pd.Series):
        """Initialize model parameters using k-means-like approach."""
        # Sort returns and divide into regimes
        sorted_returns = np.sort(returns.values)
        n_obs = len(sorted_returns)
        
        regimes = []
        for i in range(self.n_regimes):
            start_idx = i * n_obs // self.n_regimes
            end_idx = (i + 1) * n_obs // self.n_regimes
            regime_data = sorted_returns[start_idx:end_idx]
            
            regimes.append(RegimeParameters(
                mean=np.mean(regime_data),
                variance=np.var(regime_data)
            ))
        
        # Initialize transition matrix (slightly persistent)
        transition_matrix = np.full((self.n_regimes, self.n_regimes), 0.1 / (self.n_regimes - 1))
        np.fill_diagonal(transition_matrix, 0.9)
        
        # Equal initial probabilities
        initial_probs = np.full(self.n_regimes, 1.0 / self.n_regimes)
        
        self.parameters = RegimeSwitchingParameters(
            regimes=regimes,
            transition_matrix=transition_matrix,
            initial_probs=initial_probs
        )
    
    def _expectation_step(self, returns: pd.Series):
        """E-step: Calculate filtered and smoothed probabilities."""
        T = len(returns)
        
        # Forward pass (filtering)
        self.filtered_probs = np.zeros((T, self.n_regimes))
        
        # Initial probabilities
        for j in range(self.n_regimes):
            likelihood = norm.pdf(returns.iloc[0], 
                                self.parameters.regimes[j].mean,
                                np.sqrt(self.parameters.regimes[j].variance))
            self.filtered_probs[0, j] = self.parameters.initial_probs[j] * likelihood
        
        # Normalize
        self.filtered_probs[0] /= self.filtered_probs[0].sum()
        
        # Forward recursion
        for t in range(1, T):
            for j in range(self.n_regimes):
                # Prediction step
                predicted_prob = np.sum(self.filtered_probs[t-1] * self.parameters.transition_matrix[:, j])
                
                # Update step
                likelihood = norm.pdf(returns.iloc[t],
                                    self.parameters.regimes[j].mean,
                                    np.sqrt(self.parameters.regimes[j].variance))
                
                self.filtered_probs[t, j] = predicted_prob * likelihood
            
            # Normalize
            self.filtered_probs[t] /= self.filtered_probs[t].sum()
        
        # Backward pass (smoothing)
        self.smoothed_probs = np.zeros((T, self.n_regimes))
        self.smoothed_probs[-1] = self.filtered_probs[-1]
        
        for t in range(T-2, -1, -1):
            for i in range(self.n_regimes):
                smoothing_factor = 0.0
                for j in range(self.n_regimes):
                    if self.filtered_probs[t+1, j] > 0:
                        smoothing_factor += (self.parameters.transition_matrix[i, j] * 
                                           self.smoothed_probs[t+1, j] / 
                                           self.filtered_probs[t+1, j])
                
                self.smoothed_probs[t, i] = self.filtered_probs[t, i] * smoothing_factor
    
    def _maximization_step(self, returns: pd.Series):
        """M-step: Update model parameters."""
        T = len(returns)
        
        # Update regime parameters
        for j in range(self.n_regimes):
            # Weighted mean
            weights = self.smoothed_probs[:, j]
            weight_sum = weights.sum()
            
            if weight_sum > 1e-8:
                new_mean = np.sum(weights * returns.values) / weight_sum
                new_variance = np.sum(weights * (returns.values - new_mean)**2) / weight_sum
                
                # Ensure minimum variance
                new_variance = max(new_variance, 1e-8)
                
                self.parameters.regimes[j].mean = new_mean
                self.parameters.regimes[j].variance = new_variance
        
        # Update transition matrix
        for i in range(self.n_regimes):
            for j in range(self.n_regimes):
                numerator = 0.0
                denominator = 0.0
                
                for t in range(T-1):
                    # Joint probability of being in regime i at t and regime j at t+1
                    if self.filtered_probs[t+1, j] > 0:
                        joint_prob = (self.filtered_probs[t, i] * 
                                    self.parameters.transition_matrix[i, j] * 
                                    norm.pdf(returns.iloc[t+1],
                                           self.parameters.regimes[j].mean,
                                           np.sqrt(self.parameters.regimes[j].variance)) *
                                    self.smoothed_probs[t+1, j] / self.filtered_probs[t+1, j])
                        
                        numerator += joint_prob
                    
                    denominator += self.smoothed_probs[t, i]
                
                if denominator > 1e-8:
                    self.parameters.transition_matrix[i, j] = numerator / denominator
                else:
                    self.parameters.transition_matrix[i, j] = 1.0 / self.n_regimes
        
        # Normalize transition matrix rows
        for i in range(self.n_regimes):
            row_sum = self.parameters.transition_matrix[i].sum()
            if row_sum > 0:
                self.parameters.transition_matrix[i] /= row_sum
        
        # Update initial probabilities
        self.parameters.initial_probs = self.smoothed_probs[0]
    
    def _calculate_log_likelihood(self, returns: pd.Series) -> float:
        """Calculate log-likelihood of the data."""
        T = len(returns)
        log_likelihood = 0.0
        
        for t in range(T):
            likelihood_sum = 0.0
            for j in range(self.n_regimes):
                likelihood = norm.pdf(returns.iloc[t],
                                    self.parameters.regimes[j].mean,
                                    np.sqrt(self.parameters.regimes[j].variance))
                likelihood_sum += self.filtered_probs[t, j] * likelihood
            
            if likelihood_sum > 0:
                log_likelihood += np.log(likelihood_sum)
        
        return log_likelihood
    
    def _get_parameter_vector(self) -> np.ndarray:
        """Get all parameters as a single vector for convergence checking."""
        params = []
        
        # Regime parameters
        for regime in self.parameters.regimes:
            params.extend([regime.mean, regime.variance])
        
        # Transition matrix (flatten)
        params.extend(self.parameters.transition_matrix.flatten())
        
        # Initial probabilities
        params.extend(self.parameters.initial_probs)
        
        return np.array(params)
    
    def _count_parameters(self) -> int:
        """Count the number of free parameters in the model."""
        # Regime parameters: 2 per regime (mean, variance)
        regime_params = 2 * self.n_regimes
        
        # Transition matrix: n*(n-1) free parameters (rows sum to 1)
        transition_params = self.n_regimes * (self.n_regimes - 1)
        
        # Initial probabilities: n-1 free parameters (sum to 1)
        initial_params = self.n_regimes - 1
        
        return regime_params + transition_params + initial_params
    
    def _validate_model(self):
        """Perform model validation."""
        if not self.parameters.validate():
            logger.warning("Model parameters failed validation")
        
        # Check regime persistence
        persistence = np.diag(self.parameters.transition_matrix)
        self.estimation_results['regime_persistence'] = persistence
        
        # Check regime identification
        regime_probs = self.smoothed_probs.mean(axis=0)
        self.estimation_results['regime_frequencies'] = regime_probs
    
    def predict_regime(self, horizon: int = 1) -> np.ndarray:
        """
        Predict regime probabilities for future periods.
        
        Args:
            horizon: Number of periods ahead to predict
            
        Returns:
            Array of regime probabilities for each future period
        """
        if self.filtered_probs is None:
            raise ValueError("Model must be fitted before prediction")
        
        # Start with current regime probabilities
        current_probs = self.filtered_probs[-1]
        
        predictions = np.zeros((horizon, self.n_regimes))
        
        for h in range(horizon):
            # Multiply by transition matrix
            next_probs = current_probs @ self.parameters.transition_matrix
            predictions[h] = next_probs
            current_probs = next_probs
        
        return predictions
    
    def get_current_regime(self) -> Tuple[int, float]:
        """
        Get the most likely current regime.
        
        Returns:
            Tuple of (regime_index, probability)
        """
        if self.filtered_probs is None:
            raise ValueError("Model must be fitted first")
        
        current_probs = self.filtered_probs[-1]
        regime_idx = np.argmax(current_probs)
        probability = current_probs[regime_idx]
        
        return regime_idx, probability
    
    def get_regime_statistics(self) -> pd.DataFrame:
        """Get comprehensive regime statistics."""
        if self.parameters is None or self.smoothed_probs is None:
            raise ValueError("Model must be fitted first")
        
        stats = []
        
        for i, regime in enumerate(self.parameters.regimes):
            # Calculate regime-specific statistics
            regime_mask = self.smoothed_probs[:, i] > 0.5  # Periods where regime i is most likely
            
            if np.any(regime_mask):
                regime_returns = self.fitted_data[regime_mask]
                duration = np.mean(np.diff(np.where(np.diff(regime_mask.astype(int)))[0]))
            else:
                regime_returns = pd.Series([])
                duration = 0
            
            stats.append({
                'regime': self.regime_names[i],
                'mean_return': regime.mean,
                'volatility': np.sqrt(regime.variance),
                'frequency': self.smoothed_probs[:, i].mean(),
                'persistence': self.parameters.transition_matrix[i, i],
                'avg_duration': duration if duration > 0 else np.nan,
                'sharpe_ratio': regime.mean / np.sqrt(regime.variance) if regime.variance > 0 else np.nan
            })
        
        return pd.DataFrame(stats)
    
    def update_regime_probabilities(self, new_return: float) -> np.ndarray:
        """
        Update regime probabilities with new return observation.
        
        Args:
            new_return: New return observation
            
        Returns:
            Updated regime probabilities
        """
        if self.filtered_probs is None:
            raise ValueError("Model must be fitted first")
        
        # Get previous probabilities
        prev_probs = self.filtered_probs[-1]
        
        # Prediction step
        predicted_probs = prev_probs @ self.parameters.transition_matrix
        
        # Update step
        likelihoods = np.array([
            norm.pdf(new_return, regime.mean, np.sqrt(regime.variance))
            for regime in self.parameters.regimes
        ])
        
        updated_probs = predicted_probs * likelihoods
        updated_probs /= updated_probs.sum()
        
        # Update stored probabilities
        self.filtered_probs = np.vstack([self.filtered_probs, updated_probs])
        self.fitted_data = pd.concat([self.fitted_data, pd.Series([new_return])])
        
        return updated_probs

def main():
    """Example usage of the SpyderRegimeSwitchingModel."""
    print("="*60)
    print(" SPYDER - Regime-Switching Model Demonstration")
    print("="*60)
    
    # Generate synthetic data with regime switches
    np.random.seed(42)
    T = 500
    
    # Define true regimes
    true_regimes = [
        {'mean': 0.001, 'std': 0.01, 'name': 'Bull Market'},      # Low vol, positive returns
        {'mean': -0.002, 'std': 0.03, 'name': 'Bear Market'},     # High vol, negative returns
        {'mean': 0.0005, 'std': 0.015, 'name': 'Sideways Market'} # Medium vol, neutral returns
    ]
    
    # True transition matrix (persistent regimes)
    true_transition = np.array([
        [0.95, 0.03, 0.02],  # Bull -> Bull, Bear, Sideways
        [0.05, 0.90, 0.05],  # Bear -> Bull, Bear, Sideways  
        [0.10, 0.10, 0.80]   # Sideways -> Bull, Bear, Sideways
    ])
    
    # Simulate regime switches and returns
    regimes = np.zeros(T, dtype=int)
    returns = np.zeros(T)
    
    regimes[0] = 0  # Start in bull market
    
    for t in range(T):
        if t > 0:
            # Sample next regime
            regimes[t] = np.random.choice(3, p=true_transition[regimes[t-1]])
        
        # Sample return from current regime
        current_regime = true_regimes[regimes[t]]
        returns[t] = np.random.normal(current_regime['mean'], current_regime['std'])
    
    # Create pandas series
    dates = pd.date_range(start='2020-01-01', periods=T, freq='D')
    returns_series = pd.Series(returns, index=dates)
    
    print(f"\n--- Generated {T} returns with regime switches ---")
    print("True regime characteristics:")
    for i, regime in enumerate(true_regimes):
        freq = np.mean(regimes == i)
        print(f"  {regime['name']}: μ={regime['mean']:.3f}, σ={regime['std']:.3f}, freq={freq:.1%}")
    
    # Fit regime-switching model
    regime_names = ['Bull', 'Bear', 'Sideways']
    model = SpyderRegimeSwitchingModel(n_regimes=3, regime_names=regime_names)
    
    print("\n--- Fitting Regime-Switching Model ---")
    estimation_results = model.fit(returns_series, max_iterations=50)
    
    print("Estimation Results:")
    print(f"  Log-likelihood: {estimation_results['log_likelihood']:.2f}")
    print(f"  AIC: {estimation_results['aic']:.2f}")
    print(f"  BIC: {estimation_results['bic']:.2f}")
    print(f"  Iterations: {estimation_results['iterations']}")
    print(f"  Converged: {estimation_results['converged']}")
    print(f"  Estimation time: {estimation_results['estimation_time']:.2f} seconds")
    
    # Display estimated parameters
    print("\n--- Estimated Regime Parameters ---")
    regime_stats = model.get_regime_statistics()
    print(regime_stats.round(4))
    
    # Transition matrix
    print("\n--- Estimated Transition Matrix ---")
    print("From\\To    Bull     Bear     Sideways")
    print("-" * 35)
    for i, from_regime in enumerate(regime_names):
        row = model.parameters.transition_matrix[i]
        print(f"{from_regime:<8} {row[0]:.3f}    {row[1]:.3f}    {row[2]:.3f}")
    
    # Current regime identification
    print("\n--- Current Market State ---")
    current_regime_idx, current_prob = model.get_current_regime()
    current_regime_name = regime_names[current_regime_idx]
    print(f"  Most likely current regime: {current_regime_name}")
    print(f"  Probability: {current_prob:.3f}")
    
    # Recent regime probabilities
    recent_probs = model.filtered_probs[-5:]
    print("\n  Recent regime probabilities (last 5 days):")
    print("  " + "-" * 40)
    print(f"  {'Day':<5} {'Bull':<8} {'Bear':<8} {'Sideways':<8}")
    print("  " + "-" * 40)
    for i, probs in enumerate(recent_probs):
        day = f"T-{4-i}"
        print(f"  {day:<5} {probs[0]:<8.3f} {probs[1]:<8.3f} {probs[2]:<8.3f}")
    
    # Regime predictions
    print("\n--- Regime Forecasting ---")
    predictions = model.predict_regime(horizon=5)
    print("  Regime probability forecasts:")
    print("  " + "-" * 40)
    print(f"  {'Day':<5} {'Bull':<8} {'Bear':<8} {'Sideways':<8}")
    print("  " + "-" * 40)
    for i, probs in enumerate(predictions):
        day = f"T+{i+1}"
        print(f"  {day:<5} {probs[0]:<8.3f} {probs[1]:<8.3f} {probs[2]:<8.3f}")
    
    # Model validation
    print("\n--- Model Validation ---")
    
    # Regime classification accuracy
    estimated_regimes = np.argmax(model.smoothed_probs, axis=1)
    accuracy = np.mean(estimated_regimes == regimes)
    print(f"  Regime classification accuracy: {accuracy:.1%}")
    
    # Regime persistence
    persistence = model.estimation_results['regime_persistence']
    print("  Estimated regime persistence:")
    for i, p in enumerate(persistence):
        print(f"    {regime_names[i]}: {p:.3f}")
    
    # Parameter recovery analysis
    print("\n--- Parameter Recovery Analysis ---")
    print("  " + "-" * 50)
    print(f"  {'Regime':<10} {'True μ':<8} {'Est μ':<8} {'True σ':<8} {'Est σ':<8}")
    print("  " + "-" * 50)
    
    for i, (true_regime, est_regime) in enumerate(zip(true_regimes, model.parameters.regimes)):
        true_mean = true_regime['mean']
        true_std = true_regime['std']
        est_mean = est_regime.mean
        est_std = np.sqrt(est_regime.variance)
        
        print(f"  {regime_names[i]:<10} {true_mean:<8.4f} {est_mean:<8.4f} {true_std:<8.4f} {est_std:<8.4f}")
    
    # Real-time update simulation
    print("\n--- Real-time Update Simulation ---")
    print("  Simulating new return observations...")
    
    # Generate 3 new returns
    new_returns = np.random.normal(0, 0.02, 3)
    
    for i, new_return in enumerate(new_returns):
        updated_probs = model.update_regime_probabilities(new_return)
        most_likely = np.argmax(updated_probs)
        print(f"    Day {i+1}: Return = {new_return:.4f}")
        print(f"            Regime probs: Bull={updated_probs[0]:.3f}, Bear={updated_probs[1]:.3f}, Sideways={updated_probs[2]:.3f}")
        print(f"            Most likely: {regime_names[most_likely]}")
    
    # Performance summary
    print("\n--- Performance Summary ---")
    print(f"  Model complexity: {model._count_parameters()} parameters")
    print(f"  Data efficiency: {T / model._count_parameters():.1f} observations per parameter")
    print(f"  Regime identification: {accuracy:.1%} accuracy")
    print(f"  Real-time updates: Supported")
    print(f"  Integration ready: Yes (provides market context to other models)")
    
    print("="*60)

if __name__ == "__main__":
    main()

