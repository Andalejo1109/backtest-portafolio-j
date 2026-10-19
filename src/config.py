"""Parámetros del laboratorio. Autor: Andrés Alejandro Rodríguez Lozano. Uso educativo, no es recomendación."""
# Pesos por valor de la captura de eToro del 18-oct-2026 (suman 100,01% -> se normalizan)
PORT_J_RAW = {"VT": 20.81, "SPYG": 20.82, "SCHD": 15.01, "BLK": 12.81, "ITA": 12.00,
               "SMH": 9.55, "MCHI": 3.04, "REMX": 3.44, "COHR": 2.53}
# Core de Alejandro (pesos eToro 5-oct-2026). En Yahoo BRK.B = BRK-B
CORE_RAW = {"SPYG": 30.51, "SMH": 21.76, "BRK-B": 20.40, "IEMG": 20.15, "VTI": 7.18}
SPY_RAW = {"SPY": 100.0}

def normalize(d):
    s = sum(d.values())
    return {k: v / s for k, v in d.items()}

PORTFOLIOS = {
    "Portafolio J (laboratorio)": normalize(PORT_J_RAW),
    "Core Alejandro": normalize(CORE_RAW),
    "SPY": normalize(SPY_RAW),
}
PROXY = "SPY"            # método sensibilidad: antes del lanzamiento se usa el retorno total de SPY
INITIAL = 1000.0
MONTHLY = 200.0
HORIZONS = {"10 años": "2016-10-01", "15 años": "2011-10-01"}
END = "2026-10-19"       # último cierre disponible: 16-oct-2026
COST_BPS = 5.0
COST_SENS = [0.0, 5.0, 15.0]
ALL_TICKERS = sorted({t for p in PORTFOLIOS.values() for t in p})
