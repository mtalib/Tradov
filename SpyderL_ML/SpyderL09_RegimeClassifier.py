#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderL09_RegimeClassifier.py
Group: L (Machine Learning)
Purpose: Market regime detection and classification

Description:
    This module implements advanced market regime classification using
    machine learning techniques. It identifies different market states
    (trending, ranging, volatile, calm) and transitions between regimes
    to help optimize strategy selection and parameter tuning.

Author: Mohamed Talib
Date: 2024-12-20
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import pickle
from pathlib import Path
from collections import deque, Counter

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from sklearn.cluster import KMeans, DBSCAN
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from scipy.stats import entropy
from hmmlearn import hm
