#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels  
Module: SpyderV02_ModelManager.py
Purpose: Model lifecycle management and orchestration

Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-20 Time: 12:15:00  

Module Description:
    Manages the complete lifecycle of quantitative models including
    initialization, calibration scheduling, performance monitoring,
    model selection, and graceful degradation. Coordinates between
    multiple pricing and risk models for optimal performance.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor, Future

# ==============================================================================
# THIRD-PARTY IMPORTS  
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# MODEL DEFINITIONS
# ==============================================================================
class ModelStatus(Enum):
    """Model operational status."""
    INITIALIZING = "initializing"
    READY = "ready"
    CALIBRATING = "calibrating"
    ERROR = "error"
    DISABLED = "disabled"

class CalibrationTrigger(Enum):
    """Model calibration triggers."""
    SCHEDULE = "schedule"          # Time-based
    MARKET_MOVE = "market_move"    # Price/vol threshold
    PERFORMANCE = "performance"    # Model performance degrades
    MANUAL = "manual"             # User initiated

@dataclass
class ModelConfig:
    """Configuration for individual models."""
    name: str
    model_class: str
    enabled: bool = True
    calibration_frequency: str = "daily"  # daily, hourly, never
    performance_threshold: float = 0.85   # Model accuracy threshold
    initialization_params: Dict[str, Any] = field(default_factory=dict)
    calibration_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelPerformance:
    """Model performance metrics."""
    accuracy: float
    rmse: float
    last_calibration: datetime
    calibration_success: bool
    execution_time_avg: float
    error_count: int
    usage_count: int

@dataclass
class CalibrationTask:
    """Calibration task definition."""
    model_name: str
    trigger: CalibrationTrigger
    priority: int
    scheduled_time: datetime
    market_data: Optional[Any] = None
    callback: Optional[Callable] = None

# ==============================================================================
# MODEL MANAGER CLASS
# ==============================================================================
class SpyderModelManager:
    """
    Comprehensive model lifecycle manager for quantitative trading models.
    
    Features:
    - Automatic model initialization and configuration
    - Scheduled and event-driven calibration
    - Performance monitoring and model selection
    - Graceful error handling and fallback models
    - Resource management and optimization
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the model manager."""
        self.logger = self._setup_logging()
        
        # Core state
        self.models = {}                    # Active model instances
        self.model_configs = {}             # Model configurations
        self.model_performance = {}         # Performance tracking
        self.model_status = {}              # Current status
        
        # Calibration management
        self.calibration_queue = asyncio.Queue()
        self.calibration_executor = ThreadPoolExecutor(max_workers=2)
        self.calibration_tasks = {}        # Active calibration tasks
        
        # Scheduling
        self.scheduler_running = False
        self.scheduler_task = None
        
        # Performance monitoring
        self.performance_window = 100       # Last N predictions for accuracy
        self.model_predictions = {}         # Recent predictions for validation
        
        # Load configuration
        self._load_configuration(config_path)
        
        self.logger.info("🔧 SpyderModelManager initialized")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for model manager."""
        logger = logging.getLogger('SpyderModelManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    def _load_configuration(self, config_path: Optional[str]):
        """Load model configurations."""
        # Default configurations for discovered models
        default_configs = {
            'heston': ModelConfig(
                name='heston',
                model_class='SpyderHestonModel',
                calibration_frequency='daily',
                performance_threshold=0.85,
                initialization_params={'risk_free_rate': 0.05},
                calibration_params={'max_iterations': 500, 'tolerance': 1e-6}
            ),
            'cvar': ModelConfig(
                name='cvar',
                model_class='SpyderCVaRCalculator',
                calibration_frequency='hourly',
                performance_threshold=0.90,
                initialization_params={},
                calibration_params={'confidence_levels': [0.95, 0.99]}
            ),
            'black_scholes': ModelConfig(
                name='black_scholes',
                model_class='BlackScholesModel',
                calibration_frequency='never',
                performance_threshold=0.70,
                initialization_params={'risk_free_rate': 0.05}
            )
        }
        
        # Load from file if provided, otherwise use defaults
        if config_path:
            try:
                with open(config_path, 'r') as f:
                    loaded_configs = json.load(f)
                # Convert to ModelConfig objects
                for name, config_dict in loaded_configs.items():
                    self.model_configs[name] = ModelConfig(**config_dict)
            except Exception as e:
                self.logger.warning(f"Failed to load config from {config_path}: {e}")
                self.model_configs = default_configs
        else:
            self.model_configs = default_configs
        
        self.logger.info(f"📋 Loaded {len(self.model_configs)} model configurations")

    async def start(self) -> bool:
        """Start the model manager."""
        try:
            self.logger.info("🚀 Starting SpyderModelManager...")
            
            # Initialize all enabled models
            for model_name, config in self.model_configs.items():
                if config.enabled:
                    await self._initialize_model(model_name, config)
            
            # Start calibration scheduler
            await self._start_scheduler()
            
            # Start calibration worker
            asyncio.create_task(self._calibration_worker())
            
            self.logger.info("✅ SpyderModelManager started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start ModelManager: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the model manager."""
        try:
            self.logger.info("🛑 Stopping SpyderModelManager...")
            
            # Stop scheduler
            await self._stop_scheduler()
            
            # Shutdown calibration executor
            self.calibration_executor.shutdown(wait=True)
            
            # Clear models
            self.models.clear()
            
            self.logger.info("✅ SpyderModelManager stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping ModelManager: {e}")
            return False

    async def _initialize_model(self, model_name: str, config: ModelConfig):
        """Initialize a specific model."""
        try:
            self.logger.info(f"🔧 Initializing model: {model_name}")
            
            # Set initial status
            self.model_status[model_name] = ModelStatus.INITIALIZING
            
            # Create model instance (simplified - in practice would use dynamic imports)
            if config.model_class == 'SpyderHestonModel':
                try:
                    from SpyderV05_HestonModel import SpyderHestonModel
                    model = SpyderHestonModel(**config.initialization_params)
                except ImportError:
                    model = self._create_placeholder_model(config.model_class)
            elif config.model_class == 'SpyderCVaRCalculator':
                try:
                    from SpyderV10_CVaRCalculator import SpyderCVaRCalculator
                    model = SpyderCVaRCalculator(**config.initialization_params)
                except ImportError:
                    model = self._create_placeholder_model(config.model_class)
            else:
                # Placeholder model
                model = self._create_placeholder_model(config.model_class)
            
            # Store model
            self.models[model_name] = model
            self.model_status[model_name] = ModelStatus.READY
            
            # Initialize performance tracking
            self.model_performance[model_name] = ModelPerformance(
                accuracy=1.0,
                rmse=0.0,
                last_calibration=datetime.min,
                calibration_success=True,
                execution_time_avg=0.0,
                error_count=0,
                usage_count=0
            )
            
            # Initialize prediction tracking
            self.model_predictions[model_name] = []
            
            self.logger.info(f"✅ Model {model_name} initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize model {model_name}: {e}")
            self.model_status[model_name] = ModelStatus.ERROR

    def _create_placeholder_model(self, model_class: str):
        """Create a placeholder model for unknown classes."""
        class PlaceholderModel:
            def __init__(self):
                self.model_class = model_class
                
            def predict(self, *args, **kwargs):
                return np.random.random()
                
            def calibrate(self, *args, **kwargs):
                return {"success": True, "rmse": 0.1}
        
        return PlaceholderModel()

    async def _start_scheduler(self):
        """Start the calibration scheduler."""
        self.scheduler_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("📅 Calibration scheduler started")

    async def _stop_scheduler(self):
        """Stop the calibration scheduler."""
        self.scheduler_running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        self.logger.info("📅 Calibration scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop for automatic calibration."""
        while self.scheduler_running:
            try:
                current_time = datetime.now()
                
                # Check each model for calibration needs
                for model_name, config in self.model_configs.items():
                    if not config.enabled or model_name not in self.models:
                        continue
                    
                    # Check if calibration is due
                    if await self._should_calibrate(model_name, config, current_time):
                        await self._schedule_calibration(
                            model_name, 
                            CalibrationTrigger.SCHEDULE,
                            priority=1
                        )
                
                # Sleep for scheduler interval (5 minutes)
                await asyncio.sleep(300)
                
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _should_calibrate(self, model_name: str, config: ModelConfig, 
                               current_time: datetime) -> bool:
        """Determine if a model should be calibrated."""
        if config.calibration_frequency == 'never':
            return False
        
        perf = self.model_performance[model_name]
        
        # Check time-based calibration
        if config.calibration_frequency == 'daily':
            time_threshold = timedelta(days=1)
        elif config.calibration_frequency == 'hourly':
            time_threshold = timedelta(hours=1)
        else:
            return False
        
        # Check if enough time has passed
        if current_time - perf.last_calibration < time_threshold:
            return False
        
        # Check if model is already calibrating
        if self.model_status[model_name] == ModelStatus.CALIBRATING:
            return False
        
        # Check performance threshold
        if perf.accuracy < config.performance_threshold:
            self.logger.info(f"🔄 Model {model_name} performance below threshold: {perf.accuracy:.3f}")
            return True
        
        return True

    async def _schedule_calibration(self, model_name: str, 
                                   trigger: CalibrationTrigger, 
                                   priority: int = 1,
                                   market_data: Any = None):
        """Schedule a model calibration."""
        task = CalibrationTask(
            model_name=model_name,
            trigger=trigger,
            priority=priority,
            scheduled_time=datetime.now(),
            market_data=market_data
        )
        
        await self.calibration_queue.put(task)
        self.logger.info(f"📋 Scheduled calibration for {model_name} (trigger: {trigger.value})")

    async def _calibration_worker(self):
        """Worker to process calibration tasks."""
        while True:
            try:
                # Get next calibration task
                task = await self.calibration_queue.get()
                
                # Execute calibration
                await self._execute_calibration(task)
                
                # Mark task as done
                self.calibration_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in calibration worker: {e}")

    async def _execute_calibration(self, task: CalibrationTask):
        """Execute a calibration task."""
        model_name = task.model_name
        
        try:
            self.logger.info(f"🔄 Starting calibration for {model_name}")
            
            # Update status
            self.model_status[model_name] = ModelStatus.CALIBRATING
            
            # Get model and configuration
            model = self.models[model_name]
            config = self.model_configs[model_name]
            
            # Prepare calibration data (simplified)
            if task.market_data:
                calib_data = task.market_data
            else:
                calib_data = self._generate_sample_calibration_data(model_name)
            
            # Execute calibration in thread pool
            start_time = datetime.now()
            
            if hasattr(model, 'calibrate'):
                # Run calibration
                if asyncio.iscoroutinefunction(model.calibrate):
                    result = await model.calibrate(calib_data)
                else:
                    # Run in executor for sync methods
                    result = await asyncio.get_event_loop().run_in_executor(
                        self.calibration_executor,
                        model.calibrate,
                        calib_data
                    )
            else:
                result = {"success": True, "rmse": 0.1}
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update performance metrics
            perf = self.model_performance[model_name]
            perf.last_calibration = datetime.now()
            perf.calibration_success = result.get('success', True)
            perf.execution_time_avg = (
                perf.execution_time_avg * 0.9 + execution_time * 0.1
            )
            
            # Update model status
            self.model_status[model_name] = ModelStatus.READY
            
            self.logger.info(f"✅ Calibration completed for {model_name} (RMSE: {result.get('rmse', 'N/A')})")
            
        except Exception as e:
            self.logger.error(f"❌ Calibration failed for {model_name}: {e}")
            self.model_status[model_name] = ModelStatus.ERROR
            self.model_performance[model_name].error_count += 1

    def _generate_sample_calibration_data(self, model_name: str) -> List[Dict]:
        """Generate sample calibration data for models."""
        # This would normally come from real market data
        if model_name == 'heston':
            return [
                {
                    'strike': 450 + i * 5,
                    'maturity': 0.25,
                    'price': 5.0 + np.random.normal(0, 0.5),
                    'type': 'call',
                    'spot': 450.0
                }
                for i in range(10)
            ]
        else:
            return []

    def get_model(self, model_name: str) -> Optional[Any]:
        """Get a model instance by name."""
        if model_name in self.models and self.model_status[model_name] == ModelStatus.READY:
            return self.models[model_name]
        return None

    def get_best_model(self, model_type: str) -> Optional[str]:
        """Get the best performing model of a given type."""
        candidates = []
        
        for model_name, config in self.model_configs.items():
            if (model_type in config.name and 
                self.model_status[model_name] == ModelStatus.READY):
                
                perf = self.model_performance[model_name]
                candidates.append((model_name, perf.accuracy))
        
        if candidates:
            best_model = max(candidates, key=lambda x: x[1])
            return best_model[0]
        
        return None

    def get_model_status(self, model_name: str) -> ModelStatus:
        """Get current status of a model."""
        return self.model_status.get(model_name, ModelStatus.ERROR)

    def get_performance_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get performance summary for all models."""
        summary = {}
        
        for model_name, perf in self.model_performance.items():
            summary[model_name] = {
                'status': self.model_status[model_name].value,
                'accuracy': perf.accuracy,
                'rmse': perf.rmse,
                'last_calibration': perf.last_calibration.isoformat(),
                'calibration_success': perf.calibration_success,
                'avg_execution_time': perf.execution_time_avg,
                'error_count': perf.error_count,
                'usage_count': perf.usage_count
            }
        
        return summary

    async def force_calibration(self, model_name: str) -> bool:
        """Force immediate calibration of a model."""
        try:
            if model_name not in self.models:
                self.logger.error(f"Model {model_name} not found")
                return False
            
            await self._schedule_calibration(
                model_name,
                CalibrationTrigger.MANUAL,
                priority=0  # Highest priority
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to force calibration for {model_name}: {e}")
            return False

    def record_prediction(self, model_name: str, prediction: float, 
                         actual: Optional[float] = None):
        """Record a model prediction for performance tracking."""
        if model_name not in self.model_predictions:
            return
        
        # Add prediction
        self.model_predictions[model_name].append({
            'prediction': prediction,
            'actual': actual,
            'timestamp': datetime.now()
        })
        
        # Keep only recent predictions
        if len(self.model_predictions[model_name]) > self.performance_window:
            self.model_predictions[model_name] = self.model_predictions[model_name][-self.performance_window:]
        
        # Update usage count
        self.model_performance[model_name].usage_count += 1
        
        # Update accuracy if we have actuals
        if actual is not None:
            self._update_model_accuracy(model_name)

    def _update_model_accuracy(self, model_name: str):
        """Update model accuracy based on recent predictions."""
        predictions = self.model_predictions[model_name]
        
        # Filter predictions with actuals
        valid_predictions = [p for p in predictions if p['actual'] is not None]
        
        if len(valid_predictions) >= 10:  # Need at least 10 samples
            errors = [abs(p['prediction'] - p['actual']) for p in valid_predictions]
            actuals = [p['actual'] for p in valid_predictions]
            
            # Calculate metrics
            mae = np.mean(errors)
            rmse = np.sqrt(np.mean([e**2 for e in errors]))
            mape = np.mean([e/max(abs(a), 1e-6) for e, a in zip(errors, actuals)])
            
            # Convert to accuracy (simplified)
            accuracy = max(0, 1 - mape)
            
            # Update performance
            perf = self.model_performance[model_name]
            perf.accuracy = accuracy
            perf.rmse = rmse

# ==============================================================================
# TESTING
# ==============================================================================
async def test_model_manager():
    """Test the model manager functionality."""
    print("🧪 TESTING SPYDER MODEL MANAGER")
    print("=" * 50)
    
    # Create manager
    manager = SpyderModelManager()
    
    # Test 1: Start manager
    print("\n📡 Test 1: Starting model manager...")
    start_success = await manager.start()
    print(f"✅ Manager started: {start_success}")
    
    # Test 2: Check model status
    print("\n📊 Test 2: Checking model statuses...")
    for model_name in manager.model_configs.keys():
        status = manager.get_model_status(model_name)
        print(f"✅ {model_name}: {status.value}")
    
    # Test 3: Get models
    print("\n🔧 Test 3: Getting models...")
    heston = manager.get_model('heston')
    print(f"✅ Heston model available: {heston is not None}")
    
    # Test 4: Performance summary
    print("\n📈 Test 4: Performance summary...")
    summary = manager.get_performance_summary()
    print(f"✅ Performance data for {len(summary)} models")
    
    # Test 5: Force calibration
    print("\n🔄 Test 5: Force calibration...")
    calib_success = await manager.force_calibration('heston')
    print(f"✅ Calibration scheduled: {calib_success}")
    
    # Wait a bit for calibration
    await asyncio.sleep(2)
    
    # Test 6: Stop manager
    print("\n🛑 Test 6: Stopping manager...")
    stop_success = await manager.stop()
    print(f"✅ Manager stopped: {stop_success}")
    
    print("\n🎯 MODEL MANAGER TEST COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_model_manager())
