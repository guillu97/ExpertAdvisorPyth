import ib_insync as ib
import pandas as pd

# Connexion à IB Gateway (paper trading)
ibkr = ib.IB()
ibkr.connect('127.0.0.1', 4002, clientId=1)

# Contrat Forex (EUR/USD)
contract = ib.Forex('EURUSD')

# Vérification du contrat
ibkr.qualifyContracts(contract)

nb_days = 90

# Récupération des données historiques (90 jours, 5 minutes)
bars = ibkr.reqHistoricalData(
    contract,
    endDateTime='',
    durationStr=f'{nb_days} D',
    barSizeSetting='5 mins',
    whatToShow='MIDPOINT',  # Peut être BID ou ASK si tu veux un côté spécifique
    useRTH=False,
    formatDate=1
)

# Conversion en DataFrame pandas
df = ib.util.df(bars)

# Sauvegarde CSV
output_file = f'DataRecuperation/data/IB_Gateway/5min_midpoint/EURUSD_Forex_IBKR_{nb_days}days.csv'
df.to_csv(output_file, index=False)
print(f"Fichier sauvegardé : {output_file}")

# Déconnexion
ibkr.disconnect()
