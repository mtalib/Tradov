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

import json
import pickle
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from hmmlearn import hm
from scipy.stats import entropy
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import calinski_harabasz_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
