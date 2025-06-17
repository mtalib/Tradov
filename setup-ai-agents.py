#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup script for Spyder AI Agents
Installs dependencies and configures the AI agent system
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.8 or higher"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True


def install_dependencies():
    """Install required packages"""
    print("\n📦 Installing AI Agent dependencies...")
    
    requirements_file = "requirements-ai-agents.txt"
    
    if not os.path.exists(requirements_file):
        print(f"❌ {requirements_file} not found")
        return False
        
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", requirements_file
        ])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def check_ollama():
    """Check if Ollama is installed and running"""
    print("\n🤖 Checking Ollama installation...")
    
    try:
        # Check if ollama is installed
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Ollama is installed: {result.stdout.strip()}")
        else:
            print("❌ Ollama is not installed")
            print("   Please install from: https://ollama.ai")
            return False
            
        # Check if model is available
        model = "llama3.2:3b-instruct-q4_K_M"
        print(f"\n🔍 Checking for model: {model}")
        
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if model in result.stdout:
            print(f"✅ Model {model} is available")
        else:
            print(f"⚠️  Model {model} not found")
            print(f"   Installing model (this may take a while)...")
            
            try:
                subprocess.run(["ollama", "pull", model], check=True)
                print(f"✅ Model {model} installed successfully")
            except subprocess.CalledProcessError:
                print(f"❌ Failed to install model {model}")
                return False
                
        return True
        
    except FileNotFoundError:
        print("❌ Ollama is not installed")
        print("   Please install from: https://ollama.ai")
        return False


def check_redis():
    """Check if Redis is available (optional)"""
    print("\n🔄 Checking Redis (optional for caching)...")
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis is available and running")
        return True
    except:
        print("⚠️  Redis is not available - will use memory cache")
        print("   For better performance, consider installing Redis")
        return False


def create_directory_structure():
    """Create necessary directories for AI agents"""
    print("\n📁 Creating directory structure...")
    
    directories = [
        "SpyderX_Agents",
        "logs/ai_agents",
        "cache/ai_agents",
        "models/ai_agents",
        "config"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created {directory}")
        
    return True


def create_ai_config():
    """Create AI agent configuration file"""
    print("\n⚙️  Creating AI agent configuration...")
    
    config = {
        "ai_agents": {
            "enabled": True,
            "llm_model": "llama3.2:3b-instruct-q4_K_M",
            "agents": {
                "greeks_agent": {
                    "enabled": True,
                    "risk_free_rate": 0.05,
                    "greek_limits": {
                        "delta": 100,
                        "gamma": 50,
                        "vega": 200,
                        "theta": -300
                    }
                },
                "flow_agent": {
                    "enabled": False,  # Will be enabled when implemented
                    "config": {}
                },
                "strategy_agent": {
                    "enabled": False,  # Will be enabled when implemented
                    "config": {}
                },
                "risk_agent": {
                    "enabled": False,  # Will be enabled when implemented
                    "config": {}
                }
            },
            "performance": {
                "max_concurrent_agents": 4,
                "cache_enabled": True,
                "cache_ttl_seconds": 900
            }
        }
    }
    
    config_path = Path("config/ai_agents_config.json")
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
        
    print(f"✅ Configuration saved to {config_path}")
    return True


def update_main_config():
    """Update main Spyder configuration to enable AI agents"""
    print("\n🔧 Updating main configuration...")
    
    main_config_path = Path("config/spyder_config.json")
    
    if not main_config_path.exists():
        print("⚠️  Main config not found - creating template")
        config = {}
    else:
        with open(main_config_path, 'r') as f:
            config = json.load(f)
    
    # Add AI agent settings
    config["ai_agents_enabled"] = True
    config["ai_config_path"] = "config/ai_agents_config.json"
    
    with open(main_config_path, 'w') as f:
        json.dump(config, f, indent=4)
        
    print("✅ Main configuration updated")
    return True


def test_greeks_agent():
    """Test the Greeks agent to ensure it's working"""
    print("\n🧪 Testing Greeks Agent...")
    
    try:
        from SpyderX_Agents.SpyderX01_GreeksAgent import SpyderX01_GreeksAgent, OptionContract
        from datetime import datetime, timedelta
        
        # Create test agent
        config = {
            'risk_free_rate': 0.05,
            'llm_model': 'llama3.2:3b-instruct-q4_K_M'
        }
        
        agent = SpyderX01_GreeksAgent(config)
        
        if not agent.initialize():
            print("❌ Failed to initialize Greeks Agent")
            return False
        
        # Create test contract
        test_contract = OptionContract(
            symbol="SPY_TEST",
            strike=550.0,
            expiry=datetime.now() + timedelta(days=10),
            option_type='call',
            underlying_price=548.50,
            market_price=5.25
        )
        
        print("✅ Greeks Agent created and initialized successfully")
        print("   Agent is ready for integration")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test Greeks Agent: {e}")
        return False


def print_integration_example():
    """Print example code for integrating AI agents"""
    print("\n📝 Integration Example:")
    print("-" * 60)
    print("""
# In your SpyderA01_Main.py or main application file:

from SpyderU_Utilities.SpyderU12_AgentIntegration import AIAgentManager, integrate_greeks_agent

class SpyderMain:
    def __init__(self):
        # ... existing initialization ...
        
        # Initialize AI Agent Manager
        self.ai_manager = AIAgentManager(self.event_manager, self.config)
        self.ai_manager.initialize()
        self.ai_manager.start()
        
        # Create integration helpers
        self.greeks_ai = integrate_greeks_agent(self.ai_manager)
        
    def calculate_greeks_with_ai(self, contracts):
        # Use AI-enhanced Greeks calculation
        return self.greeks_ai.calculate_greeks_legacy(contracts)
        
    def handle_greeks_event(self, event):
        # Emit event for AI processing
        self.event_manager.emit(Event(
            type='ai_calculate_greeks',
            data={
                'contracts': event.data['contracts'],
                'market_context': self.get_market_context()
            }
        ))
""")
    print("-" * 60)


def print_next_steps():
    """Print next steps for the user"""
    print("\n" + "="*60)
    print("🎉 AI AGENT SETUP COMPLETE!")
    print("="*60)
    
    print("\n📋 Next Steps:")
    print("\n1. Move the generated AI agent modules to your Spyder directory:")
    print("   - SpyderX01_GreeksAgent.py → SpyderX_Agents/")
    print("   - SpyderU12_AgentIntegration.py → SpyderU_Utilities/")
    
    print("\n2. Update your imports in existing modules:")
    print("   - Import AIAgentManager in your main module")
    print("   - Replace direct Greeks calculations with AI agent calls")
    
    print("\n3. Monitor AI agent performance:")
    print("   - Check logs in logs/ai_agents/")
    print("   - View agent status: ai_manager.get_agent_status()")
    
    print("\n4. Implement additional agents:")
    print("   - SpyderX02_FlowAgent for order flow analysis")
    print("   - SpyderX03_StrategyAgent for strategy recommendations")
    print("   - SpyderX04_RiskAgent for risk narratives")
    
    print("\n💡 Tips:")
    print("   - Start with paper trading to test AI recommendations")
    print("   - Monitor LLM response times and adjust timeouts if needed")
    print("   - Use Redis for better caching performance in production")
    print("   - Gradually increase AI agent responsibilities as confidence grows")
    
    print("\n📚 Documentation:")
    print("   - Agent status: ai_manager.get_agent_status()")
    print("   - Performance metrics: agent.get_performance_metrics()")
    print("   - Process request: await ai_manager.process_request(...)")
    print("\n" + "="*60)


def main():
    """Main setup function"""
    print("="*60)
    print("🚀 SPYDER AI AGENT SETUP")
    print("="*60)
    
    steps = [
        ("Python version check", check_python_version),
        ("Install dependencies", install_dependencies),
        ("Check Ollama", check_ollama),
        ("Check Redis", check_redis),
        ("Create directories", create_directory_structure),
        ("Create AI config", create_ai_config),
        ("Update main config", update_main_config),
        ("Test Greeks agent", test_greeks_agent)
    ]
    
    failed = False
    
    for step_name, step_func in steps:
        print(f"\n▶️  {step_name}...")
        if not step_func():
            if step_name != "Check Redis":  # Redis is optional
                failed = True
                print(f"\n❌ Setup failed at: {step_name}")
                break
    
    if not failed:
        print_integration_example()
        print_next_steps()
    else:
        print("\n⚠️  Please fix the issues above and run setup again")
        
    return not failed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
