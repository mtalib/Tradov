**Geometric Brownian Motion (GBM)** is a stochastic process widely used in quantitative finance to model the evolution of asset prices over time. It captures two key empirical features of many financial series:

1. **Continuous compounding returns** – price changes are multiplicative rather than additive.  
2. **Log‑normal distribution of prices** – the logarithm of the price follows a normal distribution, which ensures prices stay positive.

Mathematically, GBM is defined by the stochastic differential equation (SDE):

\[
dS_t = \mu S_t \,dt + \sigma S_t \,dW_t
\]

where  

* \(S_t\) – asset price at time \(t\)  
* \(\mu\) – drift coefficient (expected return per unit time)  
* \(\sigma\) – volatility coefficient (standard deviation of returns)  
* \(dW_t\) – increment of a Wiener process (standard Brownian motion)

**Solution (closed‑form)**  

Integrating the SDE yields:

\[
S_t = S_0 \exp\!\Bigl[\bigl(\mu - \tfrac{1}{2}\sigma^2\bigr)t + \sigma W_t\Bigr]
\]

Thus, the log‑price \(\ln S_t\) follows a normal distribution with mean \(\ln S_0 + (\mu - \tfrac{1}{2}\sigma^2)t\) and variance \(\sigma^2 t\).

### Why GBM is popular in trading

| Feature | How GBM addresses it |
|---------|----------------------|
| **Non‑negative prices** | Exponential form guarantees \(S_t > 0\). |
| **Proportional volatility** | Volatility scales with price level, matching observed market behavior. |
| **Mathematical tractability** | Closed‑form solutions enable analytical pricing of derivatives (e.g., Black‑Scholes). |
| **Monte‑Carlo simulation** | Easy to simulate paths for risk analysis, scenario testing, and algorithmic strategy development. |

### Typical uses

* **Option pricing** – the Black‑Scholes model assumes the underlying follows GBM.  
* **Risk management** – Monte‑Carlo simulations of GBM paths estimate Value‑at‑Risk (VaR) and Expected Shortfall.  
* **Algorithmic trading** – synthetic price series generated via GBM help test strategies under realistic stochastic dynamics.  
* **Portfolio optimization** – modeling future asset returns for scenario analysis.

### Limitations

* **No mean reversion** – GBM drifts indefinitely; many assets exhibit tendency to revert to a long‑term mean.  
* **Constant volatility & drift** – Real markets show time‑varying volatility (volatility clustering) and stochastic drift.  
* **No jumps** – Sudden price jumps (e.g., news events) are not captured; jump‑diffusion models extend GBM for this.  

---
import numpy as np
import matplotlib.pyplot as plt

def simulate_gbm(
    S0: float,
    mu: float,
    sigma: float,
    T: float,
    N: int,
    n_paths: int,
    seed: int | None = None,
) -> np.ndarray:
    """
    Simulate GBM price paths.

    Parameters
    ----------
    S0 : float
        Initial asset price.
    mu : float
        Expected return (drift) per unit time.
    sigma : float
        Volatility (standard deviation of returns) per unit time.
    T : float
        Total time horizon (e.g., years).
    N : int
        Number of time steps.
    n_paths : int
        Number of simulated paths.
    seed : int | None
        Random seed for reproducibility.

    Returns
    -------
    np.ndarray
        Array of shape (n_paths, N+1) containing simulated prices.
    """
    rng = np.random.default_rng(seed)

    dt = T / N
    # Pre‑allocate array; first column is S0 for every path
    prices = np.empty((n_paths, N + 1))
    prices[:, 0] = S0

    # Generate random normal increments for the Wiener process
    # shape: (n_paths, N)
    Z = rng.standard_normal(size=(n_paths, N))

    # Cumulative sum of Brownian increments scaled by sqrt(dt)
    W = np.cumsum(np.sqrt(dt) * Z, axis=1)

    # Apply the GBM closed‑form solution
    # S_t = S0 * exp[(mu - 0.5*sigma^2)*t + sigma*W_t]
    t = np.linspace(dt, T, N)  # time points (exclude 0)
    drift = (mu - 0.5 * sigma ** 2) * t
    diffusion = sigma * W
    prices[:, 1:] = S0 * np.exp(drift + diffusion)

    return prices

if __name__ == "__main__":
    # ---- User‑adjustable parameters ----
    S0 = 100.0      # initial price
    mu = 0.07       # annual drift (7%)
    sigma = 0.2     # annual volatility (20%)
    T = 1.0         # 1 year
    N = 252         # trading days in a year
    n_paths = 5     # how many paths to draw
    seed = 42       # reproducibility
    # -----------------------------------

    paths = simulate_gbm(S0, mu, sigma, T, N, n_paths, seed)

    # Plotting
    plt.figure(figsize=(10, 6))
    for i in range(n_paths):
        plt.plot(np.linspace(0, T, N + 1), paths[i], lw=1.5, label=f"Path {i+1}")

    plt.title("Geometric Brownian Motion – Simulated Price Paths")
    plt.xlabel("Time (years)")
    plt.ylabel("Price")
    plt.grid(True, which="both", ls="--", lw=0.5, alpha=0.7)
    plt.legend()
    plt.show()

