#%%
import os
import sys
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import tushare as ts

# 由于系统中安装了backtrader包，为了方便调试源码，这里首先是引入当前工程的backtrader源码
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_package_dir = os.path.abspath(os.path.join(current_dir, '../../'))
# sys.path.insert(0, project_package_dir)
import backtrader as bt

def get_data(code='600519.SH',starttime='20170101',endtime='20200101'):
    ts.set_token('91c9159e9e4e8694ee81475ff5e0b3af938a0640f84f5fc964e6d5bb')
    pro = ts.pro_api()
    # tushare pro获取K线数据默认是倒序，即最新数据在最前面。所以这里需要倒回来。
    df = pro.daily(ts_code=code, start_date=starttime, end_date=endtime).sort_values(by='trade_date', ascending=True)
    df.index = pd.to_datetime(df.trade_date)
    df['openinterest'] = 0
    df = df[['open','high','low','close','vol','amount','openinterest']]
    return df
 
 
stock_df =get_data()
fromdate = datetime(2017,1,1)
todate = datetime(2020,1,1)
data = bt.feeds.PandasData(dataname=stock_df,fromdate=fromdate,todate=todate)
print(stock_df.head())
 #%%

 # 交易策略：当前价格大于当前移动平均值则卖出，否则买入
class MyStrategy(bt.Strategy):
    # 技术指标参数，可以在addstrategy添加策略的时候指定参数的值
    params=(
        ('maperiod',20),
    )

    def log(self, txt, dt=None): 
        # 记录策略的执行日志  
        dt = dt or self.datas[0].datetime.date(0) 
        print('%s, %s' % (dt.isoformat(), txt)) 
    
    def __init__(self):
        # 保存收盘价的引用  
        self.dataclose = self.datas[0].close 
        self.order = None
        # 买入价格和手续费  
        self.buyprice = None 
        self.buycomm = None 
        # 加入均线指标  
        self.ma = bt.indicators.SimpleMovingAverage(self.datas[0],period=self.params.maperiod)
        # 绘制图形时候用到的指标  
        bt.indicators.ExponentialMovingAverage(self.datas[0], period=25) 
        bt.indicators.WeightedMovingAverage(self.datas[0], period=25,subplot=True) 
        bt.indicators.StochasticSlow(self.datas[0]) 
        bt.indicators.MACDHisto(self.datas[0]) 
        rsi = bt.indicators.RSI(self.datas[0]) 
        bt.indicators.SmoothedMovingAverage(rsi, period=10) 
        bt.indicators.ATR(self.datas[0], plot=False) 

    def next(self):
        # 打印收盘价  
        # self.log('Close, %.2f' % self.dataclose[0]) 
        # 如果有订单正在挂起，不操作  
        if self.order: 
            return 

        if(not self.position):
            if self.dataclose[0] < self.ma[0]:
                if self.dataclose[-1] < self.ma[-1]:
                    self.log('买入单, %.2f' % self.dataclose[0]) 
                    self.order = self.buy(size=200)
        else:
            if self.dataclose[0] > self.ma[0]:
                if self.dataclose[-1] > self.ma[-1]:
                    self.log('卖出单, %.2f' % self.dataclose[0]) 
                    self.order = self.sell (size=200)

    def notify_order(self, order): 
        if order.status in [order.Submitted, order.Accepted]:
            # broker 提交/接受了，买/卖订单则什么都不做  
            return 
        # 检查一个订单是否完成  
        # 注意: 当资金不足时，broker会拒绝订单  
        if order.status in [order.Completed]: 
            if order.isbuy(): 
                self.log( 
                    '已买入, 价格: %.2f, 费用: %.2f, 佣金 %.2f' % 
                    (order.executed.price, 
                    order.executed.value, 
                    order.executed.comm)) 
                self.buyprice = order.executed.price 
                self.buycomm = order.executed.comm 
            elif order.issell(): 
                self.log('已卖出, 价格: %.2f, 费用: %.2f, 佣金 %.2f' % 
                    (order.executed.price, 
                    order.executed.value, 
                    order.executed.comm)) 
            # 记录当前交易数量  
            self.bar_executed = len(self) 

        elif order.status in [order.Canceled, order.Margin, order.Rejected]: 
            self.log('订单取消/保证金不足/拒绝')

        # 其他状态记录为：无挂起订单  
        self.order = None 

    # 交易状态通知，一买一卖算交易  
    def notify_trade(self, trade): 
        if not trade.isclosed: 
            return 
        self.log('交易利润, 毛利润 %.2f, 净利润 %.2f' % 
            (trade.pnl, trade.pnlcomm)) 
        
 
cerebro = bt.Cerebro()
cerebro.adddata(data)
cerebro.addstrategy(MyStrategy)
startcash = 1000000
cerebro.broker.setcash(startcash)
cerebro.broker.setcommission(0.0002)
 
s = fromdate.strftime("%Y-%m-%d")
t = todate.strftime("%Y-%m-%d")
print(f"初始资金：{startcash}\n回测时间:{s}-{t}")
cerebro.run()
portval = cerebro.broker.getvalue()
print(f"剩余总资金：{portval}\n回测时间:{s}-{t}")
cerebro.plot()
# cerebro.plot(iplot=False, style='candlestick', barup='red', bardown='green', volume=True, volup='red', voldown='green')
# %%
