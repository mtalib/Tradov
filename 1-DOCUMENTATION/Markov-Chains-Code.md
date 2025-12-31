import pandas as pd
import numpy as np

class MarkovOptionTrader:
    def __init__(self, states=3, bins=None):
        """
        Initialize the Markov Chain Trader.
        
        :param states: Number of states (e.g., 3 for Bear, Neutral, Bull).
        :param bins: Custom bin edges for discretizing returns. 
                     If None, uses quantile-based binning.
        """
        self.states = states
        self.bins = bins
        self.transition_matrix = None
        self.state_map = {}  # Maps integer state IDs to readable labels
        
    def _calculate_returns(self, df):
        """Calculate daily log returns."""
        # Assuming 'Close' column exists
        df = df.copy()
        df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))
        return df.dropna()

    def _discretize(self, df):
        """
        Convert continuous returns into discrete States (0, 1, 2...).
        """
        if self.bins is None:
            # Dynamic binning based on data distribution (quantiles)
            df['State'] = pd.qcut(df['Log_Return'], q=self.states, labels=False, duplicates='drop')
        else:
            # Static binning (e.g., defined by percentage moves)
            df['State'] = pd.cut(df['Log_Return'], bins=self.bins, labels=False, include_lowest=True)
            
        return df

    def fit(self, historical_data):
        """
        Train the model on historical SPY data to build the Transition Matrix.
        
        :param historical_data: Pandas DataFrame with a 'Close' column.
        """
        df = self._calculate_returns(historical_data)
        df = self._discretize(df)
        
        # Initialize Transition Matrix (States x States)
        matrix = np.zeros((self.states, self.states))
        
        # Iterate through history to count transitions
        # From state i (today) to state j (tomorrow)
        for i in range(len(df) - 1):
            current_state = int(df.iloc[i]['State'])
            next_state = int(df.iloc[i+1]['State'])
            
            # Safety check for binning edge cases
            if 0 <= current_state < self.states and 0 <= next_state < self.states:
                matrix[current_state, next_state] += 1
        
        # Normalize rows to get probabilities (sum of row = 1)
        row_sums = matrix.sum(axis=1)
        
        # Avoid division by zero
        self.transition_matrix = np.divide(matrix, row_sums[:, None], 
                                          out=np.zeros_like(matrix), 
                                          where=row_sums[:, None]!=0)
        
        # Create human-readable labels based on actual data distribution
        state_means = df.groupby('State')['Log_Return'].mean()
        sorted_indices = state_means.sort_values().index
        
        labels = []
        for idx in sorted_indices:
            val = state_means[idx]
            if val < -0.005: labels.append("Bearish")
            elif val > 0.005: labels.append("Bullish")
            else: labels.append("Neutral")
            
        # Map state ID to label
        for i, label in enumerate(labels):
            self.state_map[i] = label
            
        print("Model Trained. Transition Matrix:")
        print(self.transition_matrix)
        return self

    def get_current_state(self, last_close, prev_close):
        """Determine the state based on the most recent price action."""
        ret = np.log(last_close / prev_close)
        
        if self.bins is None:
            raise ValueError("Cannot determine current state without fitted quantiles. Use predict_on_df.")
        else:
            # Determine which bin the return falls into
            state = np.digitize(ret, self.bins) - 1
            # Clamp to boundaries
            state = max(0, min(state, self.states - 1))
            return state

    def predict(self, current_price, prev_price):
        """
        Predict the next market regime and generate a trading signal.
        """
        if self.transition_matrix is None:
            raise Exception("Model not trained yet. Call .fit() first.")

        current_state = self.get_current_state(current_price, prev_price)
        
        # Get the probability row for the current state
        probabilities = self.transition_matrix[current_state]
        
        # Find the state with the highest probability
        predicted_next_state = np.argmax(probabilities)
        confidence = np.max(probabilities)
        
        # Generate Signal
        regime_name = self.state_map.get(predicted_next_state, "Unknown")
        current_regime = self.state_map.get(current_state, "Unknown")
        
        signal = {
            'current_regime': current_regime,
            'predicted_regime': regime_name,
            'probabilities': probabilities,
            'confidence': round(confidence, 4),
            'action': self._get_action(regime_name, confidence)
        }
        
        return signal

    def _get_action(self, regime, confidence):
        """Simple heuristic for Options Trading."""
        if confidence < 0.40:
            return "HOLD / NO EDGE"
        
        if regime == "Bullish":
            return "BUY CALL" # or SELL PUT
        elif regime == "Bearish":
            return "BUY PUT" # or SELL CALL
        else:
            return "STRADDLE / IRON CONDOR (Neutral)"

# ==========================================
# EXAMPLE USAGE
# ==========================================
if __name__ == "__main__":
    # 1. Generate Dummy SPY Data (Replace this with your API Data)
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=500)
    # Random walk with drift
    prices = 450 * np.cumprod(1 + np.random.normal(0.0005, 0.012, 500))
    spy_data = pd.DataFrame({'Close': prices}, index=dates)

    # 2. Initialize Model
    # We define bins manually for consistent mapping:
    # Bin 0: < -0.5% (Bear), Bin 1: -0.5% to 0.5% (Neutral), Bin 2: > 0.5% (Bull)
    custom_bins = [-np.inf, -0.005, 0.005, np.inf]
    
    trader = MarkovOptionTrader(states=3, bins=custom_bins)

    # 3. Train on historical data
    trader.fit(spy_data)

    # 4. Simulate a live trading decision based on last two days of data
    last_close = spy_data.iloc[-1]['Close']
    prev_close = spy_data.iloc[-2]['Close']
    
    prediction = trader.predict(last_close, prev_close)
    
    print("\n--- LIVE SIGNAL ---")
    print(f"Current Regime: {prediction['current_regime']}")
    print(f"Predicted Next Regime: {prediction['predicted_regime']}")
    print(f"Confidence: {prediction['confidence']}")
    print(f"Recommended Action: {prediction['action']}")
