#!/usr/bin/env python3
import logging
from typing import Optional, Dict, Any

class Contract:
    def __init__(self):
        self.symbol = ""
        self.secType = ""
        self.exchange = ""
        self.currency = ""

class Stock(Contract):
    def __init__(self, symbol="", exchange="SMART", currency="USD"):
        super().__init__()
        self.symbol = symbol
        self.secType = "STK"
        self.exchange = exchange
        self.currency = currency

class ContractBuilder:
    def __init__(self, cache_size: int = 1000):
        self.logger = logging.getLogger("ContractBuilder")
        self._contract_cache = {}
        
    def build_stock(self, symbol: str, exchange: str = "SMART", currency: str = "USD"):
        return Stock(symbol.upper(), exchange, currency)
        
    def build_spy(self):
        return self.build_stock("SPY", "SMART", "USD")

_contract_builder = None

def get_contract_builder():
    global _contract_builder
    if _contract_builder is None:
        _contract_builder = ContractBuilder()
    return _contract_builder

def create_contract_builder(cache_size: int = 1000):
    return get_contract_builder()

__all__ = ["ContractBuilder", "get_contract_builder", "create_contract_builder"]
