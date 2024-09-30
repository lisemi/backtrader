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

start_time = '20170101'
end_time = '20200101'

def get_data(code='600519.SH',starttime='20170101',endtime='20200101'):
    ts.set_token('91c9159e9e4e8694ee81475ff5e0b3af938a0640f84f5fc964e6d5bb')
    pro = ts.pro_api()
    # tushare pro获取K线数据默认是倒序，即最新数据在最前面。所以这里需要倒回来。
    df = pro.daily(ts_code=code, start_date=starttime, end_date=endtime).sort_values(by='trade_date', ascending=True)
    df.index = pd.to_datetime(df.trade_date)
    df['openinterest'] = 0
    df = df[['open','high','low','close','vol','openinterest']]

    # # 缺失值处理：日期对齐时会使得有些交易日的数据为空，所以需要对缺失数据进行填充
    df.loc[:, ['vol', 'openinterest']] = df.loc[:, ['vol', 'openinterest']].fillna(0)
    df.loc[:, ['open', 'high', 'low', 'close']] = df.loc[:, ['open', 'high', 'low', 'close']].fillna(method='pad')  # 使用前一个有效值来填充 NaN
    df.loc[:, ['open', 'high', 'low', 'close']] = df.loc[:, ['open', 'high', 'low', 'close']].fillna(0)

    print('isna: ', df.isna().sum()) 
    print('inf: ', df.isin([float('inf'), float('-inf')]).sum())

    # 由于backtrader接收的收据必须是['open','high','low','close','volume','openinterest']
    # 并且顺序也不能变，因此这里需要把vol重命名为volume。
    df.rename(columns={'vol': 'volume'}, inplace=True)

    return df


def feed_data(stock_df=None):
    fromdate = datetime(2017,1,1)
    todate = datetime(2020,1,1)
    # DataFrame 转换为 backtrader 可使用的数据格式.确保 backtrader 知道哪些列代表 open, high, low, close, volume, datetime 等
    data = bt.feeds.PandasData(dataname=stock_df,
                               fromdate=fromdate,   # 读取的起始时间
                               todate=todate)       # 读取的结束时间
    # 如果数据源列名称与backtrader要求的不同，可以如get_data()处理数据源，或者在PandasData时指定，如下：
    # data = bt.feeds.PandasData(dataname=stock_df,
    #                            datetime='trade_date',
    #                            open='open',
    #                            high='high',
    #                            low='low',
    #                            close='close',
    #                            volume='vol',
    #                            openinterest='openinterest')

    return data
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
        # 如果有订单正在执行，则返回 
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
# %%        
 
stock_df =get_data()
print(stock_df)
# %%
bt_data = feed_data(stock_df)

cerebro = bt.Cerebro()
cerebro.adddata(bt_data)
cerebro.addstrategy(MyStrategy)
startcash = 1000000
cerebro.broker.setcash(startcash)
cerebro.broker.setcommission(0.0002)
 
s = datetime.strptime(start_time, '%Y%m%d').date()
t = datetime.strptime(end_time, '%Y%m%d').date()
print(f"初始资金：{startcash}\n回测时间:{s}-{t}")
cerebro.run()
portval = cerebro.broker.getvalue()
print(f"剩余总资金：{portval}\n回测时间:{s}-{t}")

cerebro.plot(iplot=False, style='candlestick',  # 设置主图行情数据的样式为蜡烛图
             barup='red', bardown='green',      # 设置蜡烛图上涨和下跌的颜色
             volume=True, volup='red', voldown='green') # 设置成交量在行情上涨和下跌情况下的颜色
# %%
