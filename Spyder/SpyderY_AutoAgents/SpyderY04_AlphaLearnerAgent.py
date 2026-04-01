#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY04_AlphaLearnerAgent.py
Group: Y (AutoAgents)
Purpose: Continuous ML research, model retraining, and feature discovery

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Runs 24/7. During market hours, monitors model performance and feature
    importance. During off-hours, performs model retraining, hyperparameter
    optimization, and feature engineering research.

    Wraps SpyderX05_MLResearchAgent and SpyderL_ML modules with autonomous
    scheduling. Uses the CODE LLM for feature engineering ideas and the
    PRIMARY LLM for explaining model insights.

    Key responsibilities:
    - Monitor live model prediction accuracy
    - Retrain models during off-hours with fresh data
    - Feature discovery and engineering (LLM-assisted)
    - Hyperparameter optimization
    - Model performance drift detection
    - Publish ML-based predictions as signals

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import numpy as np  # noqa: F401
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from .SpyderY00_BaseAutoAgent import (
    BaseAutoAgent,
    AgentOutput,
    LLMRole,
    MarketSession,
)

try:
    from Spyder.SpyderX_Agents.SpyderX05_MLResearchAgent import (
        SpyderX05_MLResearchAgent,
    )
    X05_AVAILABLE = True
except ImportError:
    X05_AVAILABLE = False

try:
    from Spyder.SpyderL_ML.SpyderL01_MLPredictor import SpyderL01_MLPredictor
    ML_PREDICTOR_AVAILABLE = True
except ImportError:
    ML_PREDICTOR_AVAILABLE = False

try:
    from Spyder.SpyderL_ML.SpyderL18_FeatureStore import SpyderL18_FeatureStore
    FEATURE_STORE_AVAILABLE = True
except ImportError:
    FEATURE_STORE_AVAILABLE = False


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ModelPerformance:
    """Tracks performance of a single model."""
    model_name: str = ""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    sharpe: float = 0.0
    predictions_today: int = 0
    correct_today: int = 0
    last_retrained: str = ""
    drift_detected: bool = False
    feature_importance: dict[str, float] = field(default_factory=dict)


@dataclass
class ResearchTask:
    """An ML research task to be executed during off-hours."""
    task_type: str = ""       # retrain | optimize | feature_eng | backtest
    model_name: str = ""
    description: str = ""
    priority: int = 5         # 1=highest, 10=lowest
    status: str = "pending"   # pending | running | completed | failed
    result: str = ""
    created: datetime = field(default_factory=datetime.now)
    completed: datetime | None = None


# ==============================================================================
# ALPHA LEARNER AGENT
# ==============================================================================
class SpyderY04_AlphaLearnerAgent(BaseAutoAgent):
    """Continuous ML research and model management agent.

    Market hours:  Monitor prediction accuracy, detect drift, publish ML signals
    Off-hours:     Retrain models, optimize hyperparams, engineer features

    Subscribes to:
        market.analysis     — Market data for feature updates
        signals.*           — Signal outcomes for accuracy tracking
        execution.*         — Trade results for model evaluation
        meta.research       — Research requests from other agents

    Publishes to:
        signals.ml_prediction — ML-based trading predictions
        meta.research         — Research findings and model updates
        meta.model_health     — Model performance metrics
    """

    AGENT_ID = "Y04_alpha_learner"
    AGENT_NAME = "AlphaLearner Agent"
    AGENT_VERSION = "1.0.0"
    DESCRIPTION = "Continuous ML research, model retraining, and feature discovery"

    ACTIVE_SESSIONS = {
        MarketSession.OVERNIGHT,
        MarketSession.PRE_MARKET,
        MarketSession.MARKET_OPEN,
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
        MarketSession.POST_MARKET,
    }

    TICK_INTERVALS = {
        MarketSession.OVERNIGHT: 600,     # 10 min — research mode
        MarketSession.PRE_MARKET: 300,    # 5 min — prep models
        MarketSession.MARKET_OPEN: 60,    # 1 min — prediction mode
        MarketSession.MARKET_HOURS: 120,  # 2 min — monitoring
        MarketSession.POWER_HOUR: 60,     # 1 min — eod predictions
        MarketSession.POST_MARKET: 300,   # 5 min — evaluation
    }

    TICK_INTERVAL = 120.0

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Model tracking
        self._models: dict[str, ModelPerformance] = {}
        self._research_queue: list[ResearchTask] = []
        self._completed_research: list[ResearchTask] = []
        self._predictions: deque = deque(maxlen=500)
        self._tick_count: int = 0
        self._last_retrain_date: str | None = None

        # Delegates
        self._x05_agent: Any | None = None
        if X05_AVAILABLE:
            try:
                self._x05_agent = SpyderX05_MLResearchAgent()
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to initialize X05 MLResearchAgent: {e}")

        self._ml_predictor: Any | None = None
        if ML_PREDICTOR_AVAILABLE:
            try:
                self._ml_predictor = SpyderL01_MLPredictor()
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to initialize MLPredictor: {e}")

        self._feature_store: Any | None = None
        if FEATURE_STORE_AVAILABLE:
            try:
                self._feature_store = SpyderL18_FeatureStore()
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to initialize FeatureStore: {e}")

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def on_start(self) -> None:
        """Subscribe to relevant topics."""
        self.subscribe("market.analysis")
        self.subscribe("signals.*")
        self.subscribe("execution.*")
        self.subscribe("meta.research")

    def on_wake(self, session: MarketSession) -> None:
        """Session-specific preparation."""
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 120.0)

        if session == MarketSession.PRE_MARKET:
            self._pre_market_prep()
        elif session == MarketSession.POST_MARKET:
            self._post_market_evaluation()

        super().on_wake(session)

    # ==========================================================================
    # MAIN TICK
    # ==========================================================================
    def tick(self, session: MarketSession) -> None:
        """Session-aware ML operations."""
        self._tick_count += 1
        self.TICK_INTERVAL = self.TICK_INTERVALS.get(session, 120.0)

        if session in (
            MarketSession.MARKET_OPEN,
            MarketSession.MARKET_HOURS,
            MarketSession.POWER_HOUR,
        ):
            # Market hours: generate predictions
            self._generate_predictions(session)
            # Monitor model health
            if self._tick_count % 10 == 0:
                self._monitor_model_health()
        elif session in (MarketSession.OVERNIGHT, MarketSession.POST_MARKET):
            # Off-hours: execute research tasks
            self._execute_research_queue()

    # ==========================================================================
    # PREDICTION GENERATION
    # ==========================================================================
    def _generate_predictions(self, session: MarketSession) -> None:
        """Generate ML-based predictions during market hours."""
        if not self._ml_predictor:
            return

        try:
            prediction = None
            if hasattr(self._ml_predictor, "predict"):
                prediction = self._ml_predictor.predict(symbol="SPY")

            if prediction is not None:
                direction = "bullish" if getattr(prediction, "direction", 0) > 0 else "bearish"
                confidence = getattr(prediction, "confidence", 0.5)
                horizon = getattr(prediction, "horizon_minutes", 60)

                pred_record = {
                    "direction": direction,
                    "confidence": confidence,
                    "horizon_minutes": horizon,
                    "timestamp": datetime.now().isoformat(),
                    "session": session.value,
                }
                self._predictions.append(pred_record)

                # Only publish high-confidence predictions
                if confidence >= 0.65:
                    self.publish(AgentOutput(
                        agent_id=self.AGENT_ID,
                        output_type="signal",
                        topic="signals.ml_prediction",
                        payload=pred_record,
                        confidence=confidence,
                        reasoning=(
                            f"ML prediction: {direction} with {confidence:.0%} "
                            f"confidence (horizon: {horizon}min)"
                        ),
                        priority="NORMAL",
                    ))

        except Exception as e:
            self.logger.warning(f"Prediction generation failed: {e}", exc_info=True)

    # ==========================================================================
    # MODEL HEALTH MONITORING
    # ==========================================================================
    def _monitor_model_health(self) -> None:
        """Check model accuracy and detect drift."""
        for model_name, perf in self._models.items():
            if perf.predictions_today > 10:
                accuracy = perf.correct_today / perf.predictions_today
                perf.accuracy = accuracy

                # Drift detection: accuracy dropped below 55%
                if accuracy < 0.55:
                    perf.drift_detected = True
                    self._queue_research_task(ResearchTask(
                        task_type="retrain",
                        model_name=model_name,
                        description=f"Accuracy dropped to {accuracy:.0%} — retrain needed",
                        priority=2,
                    ))

                    self.publish(AgentOutput(
                        agent_id=self.AGENT_ID,
                        output_type="alert",
                        topic="meta.model_health",
                        payload={
                            "model": model_name,
                            "accuracy": accuracy,
                            "drift_detected": True,
                        },
                        confidence=0.9,
                        reasoning=f"Model {model_name} accuracy drop: {accuracy:.0%}",
                        priority="HIGH",
                    ))

    # ==========================================================================
    # RESEARCH QUEUE
    # ==========================================================================
    def _queue_research_task(self, task: ResearchTask) -> None:
        """Add a research task to the queue."""
        self._research_queue.append(task)
        self._research_queue.sort(key=lambda t: t.priority)

    def _execute_research_queue(self) -> None:
        """Execute the next research task in the queue (off-hours only)."""
        if not self._research_queue:
            # Auto-generate research tasks if queue is empty
            self._generate_research_ideas()
            return

        task = self._research_queue[0]
        task.status = "running"

        try:
            if task.task_type == "retrain":
                self._retrain_model(task)
            elif task.task_type == "optimize":
                self._optimize_hyperparams(task)
            elif task.task_type == "feature_eng":
                self._feature_engineering(task)
            elif task.task_type == "backtest":
                self._run_backtest(task)

            task.status = "completed"
            task.completed = datetime.now()
        except Exception as e:
            task.status = "failed"
            task.result = str(e)

        self._research_queue.pop(0)
        self._completed_research.append(task)

    def _retrain_model(self, task: ResearchTask) -> None:
        """Retrain a model with fresh data."""
        if self._ml_predictor and hasattr(self._ml_predictor, "retrain"):
            try:
                self._ml_predictor.retrain(model_name=task.model_name)
                task.result = "Retrained successfully"
                self._last_retrain_date = datetime.now().strftime("%Y-%m-%d")

                self.publish(AgentOutput(
                    agent_id=self.AGENT_ID,
                    output_type="report",
                    topic="meta.research",
                    payload={
                        "action": "retrain",
                        "model": task.model_name,
                        "status": "success",
                        "date": self._last_retrain_date,
                    },
                    confidence=0.8,
                    reasoning=f"Model {task.model_name} retrained successfully",
                    priority="NORMAL",
                ))
            except Exception as e:
                task.result = f"Retrain failed: {e}"

    def _optimize_hyperparams(self, task: ResearchTask) -> None:
        """Optimize hyperparameters for a model."""
        if self._x05_agent and hasattr(self._x05_agent, "optimize_model"):
            try:
                import asyncio
                result = asyncio.run(
                    self._x05_agent.optimize_model(model_name=task.model_name)
                )
                task.result = f"Optimization complete: {result}"
            except Exception as e:
                task.result = f"Optimization failed: {e}"

    def _feature_engineering(self, task: ResearchTask) -> None:
        """LLM-assisted feature engineering."""
        prompt = (
            f"Feature engineering for model '{task.model_name}':\n"
            f"Current features: {list(self._models.get(task.model_name, ModelPerformance()).feature_importance.keys())[:10]}\n"
            f"Task: {task.description}\n\n"
            f"Suggest 3 new features for SPY options trading prediction. "
            f"For each feature, provide:\n"
            f"1. Feature name\n"
            f"2. Calculation method\n"
            f"3. Expected predictive value\n"
            f"Focus on features derivable from OHLCV, options chain, VIX, "
            f"and macro data."
        )

        response = self.llm_query(
            prompt=prompt,
            role=LLMRole.CODE,
            system_prompt=(
                "You are a quantitative researcher specializing in feature engineering "
                "for options trading ML models. Be specific and practical."
            ),
        ) or ""

        task.result = response

        if response:
            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="research",
                topic="meta.research",
                payload={
                    "action": "feature_engineering",
                    "model": task.model_name,
                    "suggestions": response,
                },
                confidence=0.6,
                reasoning="LLM-assisted feature engineering suggestions",
                priority="LOW",
            ))

    def _run_backtest(self, task: ResearchTask) -> None:
        """Run a backtest for a model or strategy."""
        task.result = "Backtest placeholder — delegate to SpyderD strategies"

    # ==========================================================================
    # RESEARCH IDEA GENERATION
    # ==========================================================================
    def _generate_research_ideas(self) -> None:
        """Ask LLM for research ideas when the queue is empty."""
        model_summaries = {
            name: {
                "accuracy": p.accuracy,
                "drift": p.drift_detected,
                "last_retrained": p.last_retrained,
            }
            for name, p in self._models.items()
        }

        prompt = (
            f"ML research planning for SPY options trading system.\n"
            f"Active models: {model_summaries or 'None tracked yet'}\n"
            f"Last retrain: {self._last_retrain_date or 'Never'}\n"
            f"Completed research today: {len([t for t in self._completed_research if t.completed and t.completed.date() == datetime.now().date()])}\n\n"
            f"Suggest ONE high-impact ML research task. Choose from:\n"
            f"1. retrain — Retrain an existing model with latest data\n"
            f"2. feature_eng — Engineer new predictive features\n"
            f"3. optimize — Hyperparameter optimization\n"
            f"4. backtest — Validate a hypothesis with historical data\n\n"
            f"Output as JSON: {{\"task_type\": \"...\", \"model_name\": \"...\", "
            f"\"description\": \"...\", \"priority\": N}}"
        )

        response = self.llm_query_json(
            prompt=prompt,
            role=LLMRole.CODE,
            system_prompt="You are an ML research director for a quantitative trading fund.",
        ) or {}

        if response and "task_type" in response:
            self._queue_research_task(ResearchTask(
                task_type=response.get("task_type", "feature_eng"),
                model_name=response.get("model_name", "default"),
                description=response.get("description", "LLM-generated research task"),
                priority=response.get("priority", 5),
            ))

    # ==========================================================================
    # SESSION HOOKS
    # ==========================================================================
    def _pre_market_prep(self) -> None:
        """Pre-market: prepare models for the trading day."""
        # Reset daily counters
        for perf in self._models.values():
            perf.predictions_today = 0
            perf.correct_today = 0
            perf.drift_detected = False

    def _post_market_evaluation(self) -> None:
        """Post-market: evaluate model performance for the day."""
        summary = {}
        for name, perf in self._models.items():
            if perf.predictions_today > 0:
                summary[name] = {
                    "accuracy": perf.correct_today / perf.predictions_today,
                    "predictions": perf.predictions_today,
                    "drift": perf.drift_detected,
                }

        if summary:
            self.publish(AgentOutput(
                agent_id=self.AGENT_ID,
                output_type="report",
                topic="meta.model_health",
                payload=summary,
                confidence=0.85,
                reasoning="Daily model performance summary",
                priority="NORMAL",
                ttl_seconds=86400,
            ))

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "tick_count": self._tick_count,
            "last_retrain_date": self._last_retrain_date,
            "models": {
                name: {
                    "accuracy": p.accuracy,
                    "last_retrained": p.last_retrained,
                    "drift": p.drift_detected,
                }
                for name, p in self._models.items()
            },
            "research_queue_size": len(self._research_queue),
            "completed_research_count": len(self._completed_research),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._tick_count = state.get("tick_count", 0)
        self._last_retrain_date = state.get("last_retrain_date")
        for name, data in state.get("models", {}).items():
            self._models[name] = ModelPerformance(
                model_name=name,
                accuracy=data.get("accuracy", 0.0),
                last_retrained=data.get("last_retrained", ""),
                drift_detected=data.get("drift", False),
            )


# ==============================================================================
# FACTORY
# ==============================================================================
def create_alpha_learner_agent(**kwargs: Any) -> SpyderY04_AlphaLearnerAgent:
    """Factory function for creating the AlphaLearner agent."""
    return SpyderY04_AlphaLearnerAgent(**kwargs)
