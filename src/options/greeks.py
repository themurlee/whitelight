import math
from datetime import datetime

def calculate_black_scholes_greeks(
    stock_price: float,
    strike_price: float,
    time_to_maturity_years: float,
    risk_free_rate: float = 0.045,
    volatility: float = 0.25,
    option_type: str = "CALL"
) -> dict:
    """
    Calculates Black-Scholes Option Greeks: Delta, Gamma, Theta, Vega.
    """
    if time_to_maturity_years <= 0 or volatility <= 0 or stock_price <= 0 or strike_price <= 0:
        return {"delta": 0.5, "gamma": 0.01, "theta": -0.02, "vega": 0.15, "iv_rank": 35.0}

    S = float(stock_price)
    K = float(strike_price)
    T = float(time_to_maturity_years)
    r = float(risk_free_rate)
    v = float(volatility)

    d1 = (math.log(S / K) + (r + 0.5 * v ** 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)

    # Cumulative distribution function
    def cdf(x):
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    # Probability density function
    def pdf(x):
        return math.exp(-0.5 * x ** 2) / math.sqrt(2.0 * math.pi)

    if option_type.upper() == "CALL":
        delta = cdf(d1)
        theta = (- (S * pdf(d1) * v) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * cdf(d2)) / 365.0
    else:
        delta = cdf(d1) - 1.0
        theta = (- (S * pdf(d1) * v) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * cdf(-d2)) / 365.0

    gamma = pdf(d1) / (S * v * math.sqrt(T))
    vega = (S * pdf(d1) * math.sqrt(T)) / 100.0

    # Estimate IV Rank based on volatility relative to 52-week norm
    iv_rank = min(100.0, max(5.0, (v - 0.15) / (0.45 - 0.15) * 100.0))

    return {
        "delta": round(delta, 3),
        "gamma": round(gamma, 4),
        "theta": round(theta, 3),
        "vega": round(vega, 3),
        "iv_rank": round(iv_rank, 1)
    }

def calculate_greeks(
    symbol: str,
    strike: float,
    expiry: str,
    option_type: str,
    current_price: float,
    iv_rank: float = 35.0
) -> dict:
    """
    Wrapper for calculate_black_scholes_greeks that parses expiry to years.
    """
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d")
        now = datetime.now()
        dte_days = max(1, (exp_date - now).days)
        time_to_maturity = dte_days / 365.0
    except Exception:
        # Fallback to 30 DTE
        time_to_maturity = 30.0 / 365.0
        
    # Estimate volatility from iv_rank or default to 0.25
    vol = 0.15 + (iv_rank / 100.0) * 0.30
    
    return calculate_black_scholes_greeks(
        stock_price=current_price,
        strike_price=strike,
        time_to_maturity_years=time_to_maturity,
        volatility=vol,
        option_type=option_type
    )

