import backtrader as bt

class SP500MultiPatternV38(bt.Strategy):
    params = dict(
        atr_length=14,
        atr_mult_sl=2.0,  # Stop-loss standard
        atr_mult_tp=3.0,  # Take-profit standard
        trail_atr=1.0,
        adx_threshold=20,  # ADX standard
        supertrend_factor=3.0,
        supertrend_atr=10,
        volatility_threshold=1.5,  # Volatilité moins strict
        max_trades_per_day=3,  # Plus de trades autorisés
        rsi_period=14,
        rsi_oversold=40,  # RSI permissif
        rsi_overbought=60,  # RSI permissif
        min_profit_threshold=5,  # Profit minimum faible
        consecutive_losses_limit=5  # Limite de pertes consécutives
    )

    def __init__(self):
        # ATR
        self.atr = bt.ind.ATR(period=self.p.atr_length)

        # Supertrend (simplified as SMA - factor * ATR)
        self.supertrend_base = bt.ind.SMA(self.data.close, period=self.p.supertrend_atr)
        self.supertrend = self.supertrend_base - self.p.supertrend_factor * self.atr

        # ADX - Utilisation de l'indicateur intégré de backtrader
        self.adx = bt.ind.ADX(period=14)
        
        # RSI pour confirmation
        self.rsi = bt.ind.RSI(period=self.p.rsi_period)
        
        # Moyennes mobiles pour tendance
        self.sma_20 = bt.ind.SMA(self.data.close, period=20)
        
        # Variable pour le suivi des positions
        self.order = None
        self.trades_today = 0
        self.last_trade_date = None
        self.consecutive_losses = 0
        self.total_trades = 0
        self.winning_trades = 0

    def next(self):
        # Vérifier si on a une commande en cours
        if self.order:
            return
            
        # Réinitialiser le compteur de trades quotidien
        current_date = self.data.datetime.date(0)
        if self.last_trade_date != current_date:
            self.trades_today = 0
            self.last_trade_date = current_date
            
        close = self.data.close[0]
        open_ = self.data.open[0]
        close_prev = self.data.close[-1]
        open_prev = self.data.open[-1]
        high = self.data.high[0]
        low = self.data.low[0]
        high_prev = self.data.high[-1]
        low_prev = self.data.low[-1]
        atr = self.atr[0]
        supertrend = self.supertrend[0]
        adx = self.adx[0]
        rsi = self.rsi[0]
        sma_20 = self.sma_20[0]

        # Vérifier que les indicateurs sont valides
        if not (atr > 0 and adx > 0 and rsi > 0):
            return

        # Limiter le nombre de trades par jour
        if self.trades_today >= self.p.max_trades_per_day:
            return
            
        # Pause après trop de pertes consécutives
        if self.consecutive_losses >= self.p.consecutive_losses_limit:
            return

        # Conditions de tendance simples
        trend_up = close > supertrend
        trend_down = close < supertrend
        trend_ok = adx >= self.p.adx_threshold
        volatility_ok = (atr / close) * 100 < self.p.volatility_threshold

        # Patterns simples
        bull_engulfing = (close_prev < open_prev and close > open_ and 
                         close > open_prev and open_ < close_prev and
                         (close - open_) > 1.3 * (open_prev - close_prev))
        
        bear_engulfing = (close_prev > open_prev and close < open_ and 
                         close < open_prev and open_ > close_prev and
                         (open_ - close) > 1.3 * (close_prev - open_prev))

        bull_pin = ((high - low) > 2 * abs(open_ - close) and close > open_ and 
                   low < low_prev and close > low + (high - low) * 0.7)
        
        bear_pin = ((high - low) > 2 * abs(open_ - close) and close < open_ and 
                   high > high_prev and close < high - (high - low) * 0.7)

        doji = abs(close - open_) <= (high - low) * 0.1
        bull_doji = doji and close > open_prev
        bear_doji = doji and close < open_prev

        # Conditions RSI
        rsi_oversold = rsi < self.p.rsi_oversold
        rsi_overbought = rsi > self.p.rsi_overbought

        # Conditions combinées simples
        long_condition = ((bull_engulfing or bull_pin or bull_doji) and 
                         trend_up and trend_ok and volatility_ok and 
                         rsi_oversold and (close - open_) > self.p.min_profit_threshold)
        
        short_condition = ((bear_engulfing or bear_pin or bear_doji) and 
                          trend_down and trend_ok and volatility_ok and 
                          rsi_overbought and (open_ - close) > self.p.min_profit_threshold)

        # SL / TP
        sl = atr * self.p.atr_mult_sl
        tp = atr * self.p.atr_mult_tp

        # Gestion des positions
        if not self.position:
            if long_condition:
                # Vérifier la marge disponible
                if self.broker.getcash() > close * 0.1:  # Au moins 10% de marge
                    self.order = self.buy()
                    self.trades_today += 1
                    self.total_trades += 1

            elif short_condition:
                # Vérifier la marge disponible
                if self.broker.getcash() > close * 0.1:  # Au moins 10% de marge
                    self.order = self.sell()
                    self.trades_today += 1
                    self.total_trades += 1

        # Gestion des positions ouvertes avec stop-loss et take-profit
        else:
            # Position longue
            if self.position.size > 0:
                # Take-profit dynamique
                take_profit = self.position.price + tp
                # Stop-loss dynamique
                stop_loss = self.position.price - sl
                
                if close >= take_profit or close <= stop_loss:
                    self.order = self.close()
            
            # Position courte
            elif self.position.size < 0:
                # Take-profit dynamique
                take_profit = self.position.price - tp
                # Stop-loss dynamique
                stop_loss = self.position.price + sl
                
                if close <= take_profit or close >= stop_loss:
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
        
        # Réinitialiser l'ordre principal
        if order == self.order:
            self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        
        # Mettre à jour les statistiques
        if trade.pnl > 0:
            self.winning_trades += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            
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
capital_initial = 5000  # Capital augmenté pour éviter les problèmes de marge
levier = 3  # Levier réduit pour plus de sécurité

# Création de l'engine
cerebro = bt.Cerebro()
cerebro.addstrategy(SP500MultiPatternV38)
cerebro.adddata(data_5min)

# Résample les données en 30 minutes
cerebro.resampledata(data_5min, timeframe=bt.TimeFrame.Minutes, compression=30)

# Configuration du broker
cerebro.broker.setcash(capital_initial)
cerebro.broker.setcommission(commission=0.5, commtype=bt.CommInfoBase.COMM_FIXED)
cerebro.broker.set_slippage_fixed(0.25)

# Sizing optimisé avec FixedSize au lieu de PercentSizer
prix_initial = 5500  # Prix moyen du SP500
stake = int((capital_initial * levier) / prix_initial)
cerebro.addsizer(bt.sizers.FixedSize, stake=stake)

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
    try:
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
    except:
        print("Statistiques détaillées non disponibles")

# Affichage du graphique
# cerebro.plot(style='candlestick', barup='green', bardown='red')
