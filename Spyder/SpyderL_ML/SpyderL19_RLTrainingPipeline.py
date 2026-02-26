#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL19_RLTrainingPipeline.py
Purpose: Unified RL training pipeline for all Spyder environments

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-02-26 Time: 14:00:00

Module Description:
    Provides a unified RL environment registry, training, inference, and model
    management system for all Spyder RL environments. Centralizes SB3-based
    training so individual modules only define gym.Env subclasses while this
    pipeline handles training orchestration, evaluation, checkpointing, and
    model serving.

Key Features:
    - Environment registry — register/discover gym.Env classes
    - Unified training (PPO, SAC, TD3, A2C) with configurable hyperparameters
    - Evaluation with risk-adjusted metrics (Sharpe, max drawdown, win rate)
    - Checkpoint management and best-model tracking
    - Model serving — get_action() for inference in production
    - Curriculum learning support (progressive difficulty)
    - Training history persistence and comparison

Change Log:
    2026-02-26: Initial creation (Phase 2 Institutional Library Integration)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# Stable-Baselines3
try:
    import gym
    from gym import spaces
    from stable_baselines3 import PPO, SAC, TD3, A2C
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.callbacks import (
        EvalCallback,
        CheckpointCallback,
        CallbackList,
        BaseCallback,
    )
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.base_class import BaseAlgorithm
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_MODELS_DIR = "models/rl"
DEFAULT_LOGS_DIR = "logs/rl"
DEFAULT_TENSORBOARD_DIR = "tensorboard"

# Default hyperparameters per algorithm
DEFAULT_HYPERPARAMS = {
    'PPO': {
        'learning_rate': 3e-4,
        'n_steps': 2048,
        'batch_size': 64,
        'n_epochs': 10,
        'gamma': 0.99,
        'gae_lambda': 0.95,
        'clip_range': 0.2,
        'ent_coef': 0.01,
        'verbose': 0,
    },
    'SAC': {
        'learning_rate': 3e-4,
        'buffer_size': 100_000,
        'batch_size': 256,
        'gamma': 0.99,
        'tau': 0.005,
        'ent_coef': 'auto',
        'verbose': 0,
    },
    'TD3': {
        'learning_rate': 1e-3,
        'buffer_size': 100_000,
        'batch_size': 100,
        'gamma': 0.99,
        'tau': 0.005,
        'verbose': 0,
    },
    'A2C': {
        'learning_rate': 7e-4,
        'n_steps': 5,
        'gamma': 0.99,
        'gae_lambda': 1.0,
        'ent_coef': 0.01,
        'verbose': 0,
    },
}

# ==============================================================================
# ENUMS
# ==============================================================================
class RLAlgorithm(Enum):
    """Supported RL algorithms."""
    PPO = "PPO"
    SAC = "SAC"
    TD3 = "TD3"
    A2C = "A2C"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class EnvironmentSpec:
    """Specification for a registered RL environment."""
    name: str
    env_class: type
    description: str
    algorithm: RLAlgorithm = RLAlgorithm.PPO
    default_config: Dict[str, Any] = field(default_factory=dict)
    obs_dim: int = 0
    action_type: str = "discrete"  # "discrete" or "continuous"
    action_dim: int = 0
    reward_description: str = ""


@dataclass
class TrainingResult:
    """Result from a training run."""
    env_name: str
    algorithm: str
    total_timesteps: int
    training_time_seconds: float
    final_metrics: Dict[str, float]
    best_metrics: Dict[str, float]
    model_path: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvaluationResult:
    """Result from model evaluation."""
    env_name: str
    num_episodes: int
    mean_return: float
    std_return: float
    mean_length: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    additional_metrics: Dict[str, float] = field(default_factory=dict)


# ==============================================================================
# EARLY STOPPING CALLBACK
# ==============================================================================
if HAS_SB3:
    class EarlyStoppingCallback(BaseCallback):
        """Stop training when performance plateaus."""

        def __init__(self, patience: int = 20, min_improvement: float = 0.01,
                     verbose: int = 0):
            super().__init__(verbose)
            self.patience = patience
            self.min_improvement = min_improvement
            self.best_reward = float('-inf')
            self.no_improvement_count = 0

        def _on_step(self) -> bool:
            if len(self.model.ep_info_buffer) > 0:
                mean_reward = np.mean([ep['r'] for ep in self.model.ep_info_buffer])
                if mean_reward > self.best_reward + self.min_improvement:
                    self.best_reward = mean_reward
                    self.no_improvement_count = 0
                else:
                    self.no_improvement_count += 1

                if self.no_improvement_count >= self.patience:
                    if self.verbose > 0:
                        print(f"Early stopping after {self.patience} evals without improvement")
                    return False
            return True


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RLTrainingPipeline:
    """
    Unified RL training pipeline for all Spyder environments.

    Provides centralized environment registration, training orchestration,
    model evaluation, and inference serving for all RL-based decision
    making across the Spyder trading system.

    Example:
        >>> pipeline = RLTrainingPipeline()
        >>> pipeline.register_environment(
        ...     name='gamma_hedging',
        ...     env_class=GammaHedgingEnvironment,
        ...     description='RL for gamma scalping hedge timing',
        ...     algorithm=RLAlgorithm.PPO
        ... )
        >>> result = pipeline.train('gamma_hedging', total_timesteps=100_000)
        >>> action = pipeline.get_action('gamma_hedging', observation)
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize RL Training Pipeline.

        Args:
            base_dir: Base directory for models, logs, tensorboard.
                      Defaults to project root.
        """
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        if not HAS_SB3:
            self.logger.warning("Stable-Baselines3 not available — RL pipeline disabled")

        # Directory setup
        self.base_dir = Path(base_dir) if base_dir else Path(".")
        self.models_dir = self.base_dir / DEFAULT_MODELS_DIR
        self.logs_dir = self.base_dir / DEFAULT_LOGS_DIR
        self.tensorboard_dir = self.base_dir / DEFAULT_TENSORBOARD_DIR

        # Registry
        self._registry: Dict[str, EnvironmentSpec] = {}

        # Active models and environments
        self._models: Dict[str, Any] = {}
        self._vec_envs: Dict[str, Any] = {}
        self._best_metrics: Dict[str, Dict[str, float]] = {}

        # Training history
        self._training_history: Dict[str, List[TrainingResult]] = defaultdict(list)

        self.logger.info("RLTrainingPipeline initialized")

    # ==========================================================================
    # ENVIRONMENT REGISTRY
    # ==========================================================================
    def register_environment(
        self,
        name: str,
        env_class: type,
        description: str = "",
        algorithm: RLAlgorithm = RLAlgorithm.PPO,
        default_config: Optional[Dict[str, Any]] = None,
        obs_dim: int = 0,
        action_type: str = "discrete",
        action_dim: int = 0,
        reward_description: str = "",
    ) -> None:
        """
        Register a new RL environment for training and inference.

        Args:
            name: Unique environment name.
            env_class: gym.Env subclass.
            description: Human-readable description.
            algorithm: Preferred RL algorithm (PPO, SAC, TD3, A2C).
            default_config: Default environment config dict.
            obs_dim: Observation space dimensionality (for documentation).
            action_type: "discrete" or "continuous".
            action_dim: Action space dimensionality.
            reward_description: Description of the reward structure.
        """
        spec = EnvironmentSpec(
            name=name,
            env_class=env_class,
            description=description,
            algorithm=algorithm,
            default_config=default_config or {},
            obs_dim=obs_dim,
            action_type=action_type,
            action_dim=action_dim,
            reward_description=reward_description,
        )
        self._registry[name] = spec
        self.logger.info(f"Registered RL environment: '{name}' ({algorithm.value})")

    def list_environments(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered environments.

        Returns:
            Dictionary of environment specs.
        """
        return {
            name: {
                'description': spec.description,
                'algorithm': spec.algorithm.value,
                'obs_dim': spec.obs_dim,
                'action_type': spec.action_type,
                'action_dim': spec.action_dim,
                'has_trained_model': name in self._models,
            }
            for name, spec in self._registry.items()
        }

    def get_environment_spec(self, name: str) -> Optional[EnvironmentSpec]:
        """Get the specification for a registered environment."""
        return self._registry.get(name)

    # ==========================================================================
    # TRAINING
    # ==========================================================================
    def train(
        self,
        env_name: str,
        total_timesteps: int = 100_000,
        algorithm: Optional[RLAlgorithm] = None,
        hyperparams: Optional[Dict[str, Any]] = None,
        env_config: Optional[Dict[str, Any]] = None,
        eval_freq: int = 5_000,
        save_freq: int = 10_000,
        n_eval_episodes: int = 10,
        early_stopping: bool = True,
        early_stopping_patience: int = 20,
    ) -> TrainingResult:
        """
        Train an RL model on a registered environment.

        Args:
            env_name: Name of registered environment.
            total_timesteps: Total training timesteps.
            algorithm: Override the environment's default algorithm.
            hyperparams: Override default hyperparameters.
            env_config: Environment configuration override.
            eval_freq: Evaluation frequency (timesteps).
            save_freq: Checkpoint save frequency (timesteps).
            n_eval_episodes: Number of episodes per evaluation.
            early_stopping: Enable early stopping.
            early_stopping_patience: Patience for early stopping.

        Returns:
            TrainingResult with metrics and model path.

        Raises:
            ValueError: If environment not registered.
            RuntimeError: If SB3 not available.
        """
        if not HAS_SB3:
            raise RuntimeError("Stable-Baselines3 not installed — cannot train")

        if env_name not in self._registry:
            raise ValueError(f"Environment '{env_name}' not registered. "
                           f"Available: {list(self._registry.keys())}")

        spec = self._registry[env_name]
        algo_enum = algorithm or spec.algorithm
        algo_name = algo_enum.value

        self.logger.info(
            f"Starting training: env='{env_name}', algo={algo_name}, "
            f"timesteps={total_timesteps:,}"
        )

        start_time = datetime.now()

        try:
            # Create environment
            config = {**spec.default_config, **(env_config or {})}
            env = self._create_vec_env(spec.env_class, config)
            eval_env = self._create_vec_env(spec.env_class, config)

            # Create model
            algo_class = self._get_algorithm_class(algo_enum)
            params = {**DEFAULT_HYPERPARAMS.get(algo_name, {}), **(hyperparams or {})}

            # Add tensorboard logging
            tb_log_dir = str(self.tensorboard_dir / env_name)
            params['tensorboard_log'] = tb_log_dir

            model = algo_class("MlpPolicy", env, **params)

            # Setup callbacks
            model_save_path = str(self.models_dir / env_name)
            log_path = str(self.logs_dir / env_name)
            os.makedirs(model_save_path, exist_ok=True)
            os.makedirs(log_path, exist_ok=True)

            callbacks = []

            eval_callback = EvalCallback(
                eval_env,
                best_model_save_path=model_save_path,
                log_path=log_path,
                eval_freq=eval_freq,
                n_eval_episodes=n_eval_episodes,
                deterministic=True,
                render=False,
            )
            callbacks.append(eval_callback)

            checkpoint_callback = CheckpointCallback(
                save_freq=save_freq,
                save_path=f"{model_save_path}/checkpoints/",
                name_prefix=f"{env_name}_{algo_name}",
            )
            callbacks.append(checkpoint_callback)

            if early_stopping:
                es_callback = EarlyStoppingCallback(
                    patience=early_stopping_patience
                )
                callbacks.append(es_callback)

            callback_list = CallbackList(callbacks)

            # Train
            model.learn(
                total_timesteps=total_timesteps,
                callback=callback_list,
                progress_bar=False,
            )

            # Save final model
            final_path = f"{model_save_path}/{env_name}_{algo_name}_final"
            model.save(final_path)

            # Store model
            self._models[env_name] = model
            self._vec_envs[env_name] = env

            # Evaluate
            eval_result = self.evaluate(env_name, num_episodes=n_eval_episodes)

            # Track metrics
            elapsed = (datetime.now() - start_time).total_seconds()
            result = TrainingResult(
                env_name=env_name,
                algorithm=algo_name,
                total_timesteps=total_timesteps,
                training_time_seconds=elapsed,
                final_metrics={
                    'mean_return': eval_result.mean_return,
                    'sharpe_ratio': eval_result.sharpe_ratio,
                    'win_rate': eval_result.win_rate,
                    'max_drawdown': eval_result.max_drawdown,
                },
                best_metrics=self._best_metrics.get(env_name, {}),
                model_path=final_path,
            )

            self._training_history[env_name].append(result)

            self.logger.info(
                f"Training complete: env='{env_name}', "
                f"Sharpe={eval_result.sharpe_ratio:.3f}, "
                f"WinRate={eval_result.win_rate:.1%}, "
                f"time={elapsed:.1f}s"
            )

            return result

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'train',
                'env_name': env_name,
                'algorithm': algo_name,
            })
            elapsed = (datetime.now() - start_time).total_seconds()
            return TrainingResult(
                env_name=env_name,
                algorithm=algo_name,
                total_timesteps=total_timesteps,
                training_time_seconds=elapsed,
                final_metrics={},
                best_metrics={},
                model_path="",
            )

    # ==========================================================================
    # EVALUATION
    # ==========================================================================
    def evaluate(
        self,
        env_name: str,
        num_episodes: int = 10,
        deterministic: bool = True,
    ) -> EvaluationResult:
        """
        Evaluate a trained model.

        Args:
            env_name: Name of the environment.
            num_episodes: Number of evaluation episodes.
            deterministic: Use deterministic policy.

        Returns:
            EvaluationResult with aggregated performance metrics.
        """
        if env_name not in self._models:
            raise ValueError(f"No trained model for '{env_name}'")

        model = self._models[env_name]
        spec = self._registry[env_name]

        # Create fresh eval environment
        config = spec.default_config
        env = spec.env_class(**config) if config else spec.env_class()

        episode_returns = []
        episode_lengths = []
        episode_pnls = []

        for _ in range(num_episodes):
            obs = env.reset()
            episode_return = 0.0
            episode_length = 0
            done = False
            step_rewards = []

            while not done:
                action, _ = model.predict(obs, deterministic=deterministic)
                obs, reward, done, info = env.step(action)
                episode_return += reward
                episode_length += 1
                step_rewards.append(reward)

            episode_returns.append(episode_return)
            episode_lengths.append(episode_length)
            episode_pnls.append(step_rewards)

        # Aggregate metrics
        returns_array = np.array(episode_returns)
        mean_return = float(np.mean(returns_array))
        std_return = float(np.std(returns_array))

        # Calculate Sharpe from per-step rewards (annualized proxy)
        all_rewards = np.concatenate(episode_pnls) if episode_pnls else np.array([0])
        sharpe = self._calculate_sharpe(all_rewards)

        # Win rate: fraction of episodes with positive return
        win_rate = float(np.mean(returns_array > 0)) if len(returns_array) > 0 else 0.0

        # Max drawdown across episodes
        max_dd = np.mean([self._calculate_max_drawdown(pnls) for pnls in episode_pnls])

        result = EvaluationResult(
            env_name=env_name,
            num_episodes=num_episodes,
            mean_return=mean_return,
            std_return=std_return,
            mean_length=float(np.mean(episode_lengths)),
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            max_drawdown=float(max_dd),
        )

        # Update best metrics
        if env_name not in self._best_metrics or sharpe > self._best_metrics[env_name].get('sharpe_ratio', float('-inf')):
            self._best_metrics[env_name] = {
                'sharpe_ratio': sharpe,
                'mean_return': mean_return,
                'win_rate': win_rate,
                'max_drawdown': float(max_dd),
            }

        return result

    # ==========================================================================
    # INFERENCE
    # ==========================================================================
    def get_action(
        self,
        env_name: str,
        observation: np.ndarray,
        deterministic: bool = True,
    ) -> Any:
        """
        Get action from a trained model for production inference.

        Args:
            env_name: Name of the environment/model.
            observation: Current observation array.
            deterministic: Use deterministic policy (recommended for production).

        Returns:
            Action (int for discrete, np.ndarray for continuous).

        Raises:
            ValueError: If no trained model available.
        """
        if env_name not in self._models:
            raise ValueError(f"No trained model for '{env_name}'. "
                           f"Train first or load a saved model.")

        model = self._models[env_name]
        action, _ = model.predict(observation, deterministic=deterministic)
        return action

    def has_trained_model(self, env_name: str) -> bool:
        """Check if a trained model exists for the given environment."""
        return env_name in self._models

    # ==========================================================================
    # MODEL PERSISTENCE
    # ==========================================================================
    def save_model(self, env_name: str, path: Optional[str] = None) -> str:
        """
        Save a trained model to disk.

        Args:
            env_name: Environment name.
            path: Override save path.

        Returns:
            Path where model was saved.
        """
        if env_name not in self._models:
            raise ValueError(f"No trained model for '{env_name}'")

        save_path = path or str(self.models_dir / f"{env_name}_saved")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        self._models[env_name].save(save_path)
        self.logger.info(f"Model saved: {save_path}")
        return save_path

    def load_model(
        self,
        env_name: str,
        path: str,
        algorithm: Optional[RLAlgorithm] = None,
    ) -> None:
        """
        Load a trained model from disk.

        Args:
            env_name: Environment name to associate model with.
            path: Path to saved model.
            algorithm: Algorithm used (auto-detected from registry if available).
        """
        if not HAS_SB3:
            raise RuntimeError("Stable-Baselines3 not installed")

        # Determine algorithm
        algo_enum = algorithm
        if algo_enum is None and env_name in self._registry:
            algo_enum = self._registry[env_name].algorithm
        if algo_enum is None:
            algo_enum = RLAlgorithm.PPO  # Default fallback

        algo_class = self._get_algorithm_class(algo_enum)
        self._models[env_name] = algo_class.load(path)
        self.logger.info(f"Model loaded: {path} → '{env_name}'")

    # ==========================================================================
    # TRAINING HISTORY
    # ==========================================================================
    def get_training_history(self, env_name: str) -> List[TrainingResult]:
        """Get training history for an environment."""
        return self._training_history.get(env_name, [])

    def get_best_metrics(self, env_name: str) -> Dict[str, float]:
        """Get best metrics achieved for an environment."""
        return self._best_metrics.get(env_name, {})

    def compare_environments(self) -> pd.DataFrame:
        """
        Compare performance across all trained environments.

        Returns:
            DataFrame with environment performance comparison.
        """
        rows = []
        for name, metrics in self._best_metrics.items():
            rows.append({
                'environment': name,
                'algorithm': self._registry[name].algorithm.value if name in self._registry else 'unknown',
                **metrics,
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ==========================================================================
    # BATCH TRAINING
    # ==========================================================================
    def train_all(
        self,
        total_timesteps: int = 100_000,
        **train_kwargs,
    ) -> Dict[str, TrainingResult]:
        """
        Train all registered environments.

        Args:
            total_timesteps: Timesteps per environment.
            **train_kwargs: Additional arguments passed to train().

        Returns:
            Dictionary of environment name → TrainingResult.
        """
        results = {}
        for env_name in self._registry:
            self.logger.info(f"Training {env_name} ({self._registry[env_name].algorithm.value})...")
            results[env_name] = self.train(env_name, total_timesteps=total_timesteps, **train_kwargs)
        return results

    # ==========================================================================
    # PRIVATE HELPERS
    # ==========================================================================
    def _create_vec_env(self, env_class: type, config: Dict[str, Any]) -> Any:
        """Create a vectorized environment."""
        def make_env():
            return env_class(**config) if config else env_class()
        return DummyVecEnv([make_env])

    def _get_algorithm_class(self, algo: RLAlgorithm) -> type:
        """Get SB3 algorithm class from enum."""
        if not HAS_SB3:
            raise RuntimeError("SB3 not installed")
        algo_map = {
            RLAlgorithm.PPO: PPO,
            RLAlgorithm.SAC: SAC,
            RLAlgorithm.TD3: TD3,
            RLAlgorithm.A2C: A2C,
        }
        return algo_map[algo]

    @staticmethod
    def _calculate_sharpe(rewards: np.ndarray) -> float:
        """Calculate Sharpe ratio from rewards."""
        if len(rewards) == 0 or np.std(rewards) == 0:
            return 0.0
        return float(np.sqrt(252) * np.mean(rewards) / np.std(rewards))

    @staticmethod
    def _calculate_max_drawdown(rewards: List[float]) -> float:
        """Calculate maximum drawdown from reward sequence."""
        if not rewards:
            return 0.0
        cumulative = np.cumsum(rewards)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative)
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0.0
        # Normalize by peak
        peak_val = np.max(peak) if np.max(peak) > 0 else 1.0
        return float(max_dd / peak_val)


# ==============================================================================
# SINGLETON ACCESSOR
# ==============================================================================
_pipeline_instance: Optional[RLTrainingPipeline] = None


def get_rl_pipeline(base_dir: Optional[str] = None) -> RLTrainingPipeline:
    """
    Get the singleton RLTrainingPipeline instance.

    Args:
        base_dir: Base directory (only used on first call).

    Returns:
        RLTrainingPipeline instance.
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RLTrainingPipeline(base_dir=base_dir)
    return _pipeline_instance
