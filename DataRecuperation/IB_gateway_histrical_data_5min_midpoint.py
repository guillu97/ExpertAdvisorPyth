import ib_insync as ib
import pandas as pd

# Connexion à IB Gateway (paper trading) port 4002
ibkr = ib.IB()
ibkr.connect('127.0.0.1', 4002, clientId=1)

# Définition du contrat CFD SP500
contract = ib.CFD(symbol='IBUS500', exchange='SMART', currency='USD')

# Vérification du contrat
ibkr.qualifyContracts(contract)

nb_days = 90

# Récupération des données historiques (ici dernières 10 journées en 5 minutes)
bars = ibkr.reqHistoricalData(
    contract,
    endDateTime='',
    durationStr=f'{nb_days} D',
    barSizeSetting='5 mins',
    whatToShow='MIDPOINT',
    useRTH=False,
    formatDate=1
)

# Conversion en DataFrame pandas
df = ib.util.df(bars)

# Sauvegarde CSV (facultatif)
df.to_csv(f'DataRecuperation/data/IB_Gateway/5min_midpoint/SP500_CFD_IBKR_{nb_days}days.csv', index=False)

# Fermeture de connexion
ibkr.disconnect()
