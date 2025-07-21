import backtrader as bt


class MBBStrategy(bt.Strategy):
    params = dict(
        period=20,  # Période standard
        multiplier=2.0,  # Multiplicateur standard
        atr_period=14,  # ATR standard
        trend_period=40,  # Filtre de tendance plus long
        min_atr=3.0,  # Filtre de volatilité moins strict
        max_trades_per_day=3  # Plus de trades autorisés
    )

    def __init__(self):
        # Indicateurs de base
        sma = bt.ind.SMA(self.data.close, period=self.p.period)
        std = bt.ind.StdDev(self.data.close, period=self.p.period)
        
        # Bandes de Bollinger
        self.middle = sma
        self.upper = sma + self.p.multiplier * std
        self.lower = sma - self.p.multiplier * std
        
        # ATR pour take-profit dynamique
        self.atr = bt.ind.ATR(self.data, period=self.p.atr_period)
        
        # Filtre de tendance
        self.trend_sma = bt.ind.SMA(self.data.close, period=self.p.trend_period)
        
        # RSI pour éviter les zones de surachat/survente
        self.rsi = bt.ind.RSI(self.data.close, period=14)
        
        # Variables pour le suivi des positions
        self.order = None
        self.buyprice = None
        self.sellprice = None
        self.trades_today = 0
        self.last_trade_date = None

    def next(self):
        # Vérifier si on a une commande en cours
        if self.order:
            return
        
        # Réinitialiser le compteur de trades quotidien
        current_date = self.data.datetime.date(0)
        if self.last_trade_date != current_date:
            self.trades_today = 0
            self.last_trade_date = current_date
        
        # Vérifier la volatilité minimale
        if self.atr[0] < self.p.min_atr:
            return
        
        # Limiter le nombre de trades par jour
        if self.trades_today >= self.p.max_trades_per_day:
            return
        
        # Conditions d'entrée simplifiées mais efficaces
        if not self.position:
            # Entrée long : croisement vers le haut de la bande inférieure + tendance haussière + RSI < 60
            if (self.data.close[-1] < self.lower[-1] and 
                self.data.close[0] >= self.lower[0] and
                self.data.close[0] > self.trend_sma[0] and
                self.rsi[0] < 60):
                
                self.order = self.buy()
                self.buyprice = self.data.close[0]
                self.trades_today += 1
            
            # Entrée short : croisement vers le bas de la bande supérieure + tendance baissière + RSI > 40
            elif (self.data.close[-1] > self.upper[-1] and 
                  self.data.close[0] <= self.upper[0] and
                  self.data.close[0] < self.trend_sma[0] and
                  self.rsi[0] > 40):
                
                self.order = self.sell()
                self.sellprice = self.data.close[0]
                self.trades_today += 1
        
        # Gestion des positions ouvertes
        else:
            # Position longue
            if self.position.size > 0:
                # Take-profit dynamique (1.5x ATR)
                take_profit = self.buyprice + 1.5 * self.atr[0]
                # Stop-loss : cassure de la bande inférieure
                stop_loss = self.lower[0]
                
                if self.data.close[0] >= take_profit or self.data.close[0] <= stop_loss:
                    self.order = self.close()
            
            # Position courte
            elif self.position.size < 0:
                # Take-profit dynamique (1.5x ATR)
                take_profit = self.sellprice - 1.5 * self.atr[0]
                # Stop-loss : cassure de la bande supérieure
                stop_loss = self.upper[0]
                
                if self.data.close[0] <= take_profit or self.data.close[0] >= stop_loss:
                    self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'ACHAT EXÉCUTÉ, Prix: {order.executed.price:.2f}, Coût: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'VENTE EXÉCUTÉE, Prix: {order.executed.price:.2f}, Coût: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}')
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Ordre annulé/marge insuffisante/rejeté')
        
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        
        self.log(f'OPÉRATION TERMINÉE, Profit: {trade.pnl:.2f}, Profit Net: {trade.pnlcomm:.2f}')

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

# Chargement des données CSV
data_5min = bt.feeds.GenericCSVData(
    dataname='DataRecuperation/data/IB_Gateway/5min_midpoint/SP500_CFD_IBKR_90_D.csv',
    dtformat='%Y-%m-%d %H:%M:%S%z',
    datetime=0,
    open=1,
    high=2,
    low=3,
    close=4,
    volume=5,
    openinterest=-1,
    timeframe=bt.TimeFrame.Minutes,
    compression=5,
    nullvalue=-1.0
)

# Paramètres initiaux
capital_initial = 20000
levier = 5 # Levier réduit pour moins de risque

# Création de l'engine
cerebro = bt.Cerebro()
cerebro.addstrategy(MBBStrategy)
cerebro.adddata(data_5min)

# Résample les données en 30 minutes (au lieu de 45)
cerebro.resampledata(data_5min, timeframe=bt.TimeFrame.Minutes, compression=30)

# Configuration du broker
cerebro.broker.setcash(capital_initial)
cerebro.broker.setcommission(commission=0.5, commtype=bt.CommInfoBase.COMM_FIXED)  # Commission réduite
cerebro.broker.set_slippage_fixed(0.25)  # Slippage réduit

# Sizing optimisé
cerebro.addsizer(bt.sizers.PercentSizer, percents=100 * levier)

# Lancer le backtest
print(f"Capital initial : {capital_initial:.2f} EUR")
print("Démarrage du backtest...")
results = cerebro.run()
print(f"Capital final : {cerebro.broker.getvalue():.2f} EUR")
print(f"Profit/Perte : {cerebro.broker.getvalue() - capital_initial:.2f} EUR")
print(f"Rendement : {((cerebro.broker.getvalue() / capital_initial) - 1) * 100:.2f}%")

# Affichage des statistiques
if len(results) > 0:
    strat = results[0]
    print(f"\nStatistiques de la stratégie:")
    
    # Utiliser les statistiques de backtrader
    # try:
    print(strat.stats[0])
    total_trades = strat.stats.trades.total.total
    winning_trades = strat.stats.trades.won.total
    losing_trades = strat.stats.trades.lost.total
    
    print(f"Nombre total d'opérations: {total_trades}")
    print(f"Opérations gagnantes: {winning_trades}")
    print(f"Opérations perdantes: {losing_trades}")
    
    if total_trades > 0:
        win_rate = (winning_trades / total_trades) * 100
        print(f"Taux de réussite: {win_rate:.2f}%")
        
        # Calculer le profit moyen par trade
        total_pnl = cerebro.broker.getvalue() - capital_initial
        avg_pnl = total_pnl / total_trades
        print(f"Profit moyen par trade: {avg_pnl:.2f} EUR")
        
        # Calculer le ratio gain/perte
        if losing_trades > 0 and winning_trades > 0:
            avg_win = strat.stats.trades.won.pnl.average
            avg_loss = strat.stats.trades.lost.pnl.average
            if avg_loss != 0:
                profit_factor = abs(avg_win / avg_loss)
                print(f"Ratio gain/perte: {profit_factor:.2f}")
    # except:
    #     print("Statistiques détaillées non disponibles")

# Affichage du graphique
cerebro.plot(style='candlestick', barup='green', bardown='red')
