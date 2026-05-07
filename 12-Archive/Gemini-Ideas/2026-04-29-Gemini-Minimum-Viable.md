2026-04-29-Minium-Viable-Signal-Set

To build the lean, autonomous regime-aware engine we discussed, you need to be ruthless about cutting correlated and noisy data. Every additional symbol that answers the same question just adds fragility and false confidence.

If this panel is meant to represent what the autonomous backend is processing to make decisions, here is exactly what you should remove and what you should keep, based on the principle of the "minimum viable signal set".

🚨 What to REMOVE (The Noise & Redundancy)
1. Correlated Indices (Remove: SPX, QQQ, IWM)

Why: For an SPY options bot, tracking the SPX, Nasdaq (QQQ), and Russell 2000 (IWM) alongside SPY is redundant. They are highly correlated and tell the bot the same basic directional story. The bot only needs the SPY quote and option chain.

2. Noisy Market Internals (Remove: $TICK, $TRIN, $ADD, NYMO, CPC, $VOLD, XLK, XLF, RVOL)

Why: This is classic overengineering for a regime classifier. You need one participation/momentum indicator at most (like RSI or a simple volume check). Feeding tick-by-tick breadth ($TICK, $ADD) into an options sizing algorithm will cause erratic behavior. Sector ETFs (XLK, XLF) are unnecessary since SPY already aggregates them.

3. Redundant Macro & Commodities (Remove: GLD, USO, TLT, LQD)

Why: Gold (GLD) and Oil (USO) are not core drivers of the SPY options volatility regime. For bonds, you already have TNX (10-year yield) to track the risk-free rate and macro shifts. TLT and LQD are redundant.

4. Derivative Volatility (Remove: VVIX, SKEW)

Why: VVIX is the volatility of VIX. For your regime classifier, the VIX level and the term structure (VIX vs VIX9D/VXV) give you the complete picture of market stress and backwardation.

5. Opaque Custom Metrics (Remove: GEX, DEX, OGL, DIX, PSR, PMR)

Why: Unless one of these is your dedicated, tested "Kill Switch" signal, dark pool index (DIX) or gamma exposure (GEX) estimations usually add complexity without proportional signal for standard credit spread/directional algorithms.

🟢 What to KEEP (The Minimum Viable Set)
This is the lean stack that perfectly maps to the 6-regime classifier:

The Underlying: SPY (Direction and price state).

Volatility Regime & Term Structure: VIX, VIX9D, VXV. (Crucial for detecting crisis/turbulent regimes via backwardation).

Macro / Rates: TNX (Rates) and DXY (Dollar/Risk Appetite).

Options Analytics: IVR, ATM_IV, VRP. (Essential for knowing if volatility is rich or cheap, dictating strike selection).

Orthogonal Custom Signals: WRS (Consumer defensiveness) and potentially HYG or SWAN if you use them as your explicit emergency/stress kill-switch.

The Pragmatic Approach
If you like looking at all 30+ symbols as a human trader, you can keep the UI exactly as it is! Just ensure that the Python backend strategy engine is completely decoupled from the UI and is only consuming the 10-12 symbols in the "Keep" list to make its autonomous decisions.
