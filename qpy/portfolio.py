'''
This module is the heart of QuantPy. It provides
 - a class "Stock" that holds and calculates quantities of a single stock,
 - a class "Portfolio" that holds and calculates quantities of a financial
     portfolio, which is a collection of Stock instances.
 - a function "buildPortfolio()" that automatically constructs and returns
     an instance of "Portfolio" and instances of "Stock". The relevant stock
     data is either retrieved through `quandl` or provided by the user as a
     pandas.DataFrame (after loading it manually from disk/reading from file).
     For an example on how to use it, please read the corresponding docstring,
     or have a look at the examples in the sub-directory `example`.

The classes "Stock" and "Portfolio" are designed to easily manage your
financial portfolio, and make the most common quantitative calculations:
 - cumulative returns of the portfolio's stocks
     ( (price_{t} - price_{t=0} + dividend) / price_{t=0} ),
 - daily returns of the portfolio's stocks (daily percentage change),
 - daily log returns of the portfolio's stocks,
 - expected (annualised) return,
 - volatility,
 - Sharpe ratio,
 - skewness of the portfolio's stocks,
 - Kurtosis of the portfolio's stocks,
 - the portfolio's covariance matrix.

"Portfolio" also provides methods to easily compute and visualise
 - simple moving averages of any given time window,
 - exponential moving averages of any given time window,
 - Bollinger Bands of any given time window,

Furthermore, the constructed portfolio can be optimised for
 - minimum volatility,
 - maximum Sharpe ratio
by either performing a numerical computation to based on the Efficient
Frontier, or by simply performing a Monte Carlo simulation of n trials.
The former method should be preferred for reasons of computational effort
and accuracy. The latter is only included for the sake of completeness.
'''


import numpy as np
import pandas as pd
from qpy.quants import weightedMean, weightedStd, sharpeRatio
from qpy.optimisation import optimiseMC
from qpy.returns import historicalMeanReturn
from qpy.returns import dailyReturns, cumulativeReturns, dailyLogReturns


class Stock(object):
    '''
    Object that contains information about a stock/fund.
    To initialise the object, it requires a name, information about
    the stock/fund given as one of the following data structures:
     - pandas.Series
     - pandas.DataFrame
    The investment information can contain as little information as its name,
    and the amount invested in it, the column labels must be "Name" and "FMV"
    respectively, but it can also contain more information, such as
     - Year
     - Strategy
     - CCY
     - etc
    It also requires either data, e.g. daily closing prices as a
    pandas.DataFrame or pandas.Series.
    "data" must be given as a DataFrame, and at least one data column
    is required to containing the closing price, hence it is required to
    contain one column label "<stock_name> - Adj. Close" which is used to
    compute the return of investment. However, "data" can contain more
    data in additional columns.
    '''
    def __init__(self, investmentinfo, data):
        self.name = investmentinfo.Name
        self.investmentinfo = investmentinfo
        self.data = data
        # compute expected return and volatility of stock
        self.expectedReturn = self.compExpectedReturn()
        self.volatility = self.compVolatility()
        self.skew = self.__compSkew()
        self.kurtosis = self.__compKurtosis()

    def getInvestmentInfo(self):
        '''
        Returns pandas.DataFrame of FMV and other information provided
        '''
        return self.investmentinfo

    # functions to compute quantities
    def compDailyReturns(self):
        '''
        Computes the daily returns (percentage change)
        '''
        return dailyReturns(self.data)

    def compExpectedReturn(self, freq=252):
        '''
        Computes the expected return of the stock.

        Input:
         * freq: Integer (default: 252), number of trading days, default
             value corresponds to trading days in a year
        '''
        return historicalMeanReturn(self.data, freq=freq)

    def compVolatility(self, freq=252):
        '''
        Computes the volatility of the stock.

        Input:
         * freq: Integer (default: 252), number of trading days, default
             value corresponds to trading days in a year
        '''
        return self.compDailyReturns().std() * np.sqrt(freq)

    def __compSkew(self):
        '''
        Computes and returns the skewness of the stock.
        '''
        return self.data.skew().values[0]

    def __compKurtosis(self):
        '''
        Computes and returns the Kurtosis of the stock.
        '''
        return self.data.kurt().values[0]

    def properties(self):
        '''
        Nicely prints out the properties of the stock: expected return,
        volatility, skewness, Kurtosis as well as the FMV (and other
        information provided in investmentinfo.)
        '''
        # nicely printing out information and quantities of the stock
        string = "-"*50
        string += "\nStock: {}".format(self.name)
        string += "\nExpected return:{:0.3f}".format(
            self.expectedReturn.values[0])
        string += "\nVolatility: {:0.3f}".format(
            self.volatility.values[0])
        string += "\nSkewness: {:0.5f}".format(self.skew)
        string += "\nKurtosis: {:0.5f}".format(self.kurtosis)
        string += "\nInformation:"
        string += "\n"+str(self.investmentinfo.to_frame().transpose())
        string += "\n"
        string += "-"*50
        print(string)

    def __str__(self):
        # print short description
        string = "Contains information about "+str(self.name)+"."
        return string


class Portfolio(object):
    '''
    Object that contains information about a investment portfolio.
    To initialise the object, it does not require any input.
    To fill the portfolio with investment information, the
    function addStock(stock) should be used, in which `stock` is
    a `Stock` object, a pandas.DataFrame of the portfolio investment
    information.
    '''
    def __init__(self):
        # initilisating instance variables
        self.portfolio = pd.DataFrame()
        self.stocks = {}
        self.data = pd.DataFrame()
        self.expectedReturn = None
        self.volatility = None
        self.sharpe = None
        self.skew = None
        self.kurtosis = None
        self.totalinvestment = None

    @property
    def totalinvestment(self):
        return self.__totalinvestment

    @totalinvestment.setter
    def totalinvestment(self, val):
        if (val is not None):
            # treat "None" as initialisation
            if (not isinstance(val, (float, int))):
                raise ValueError("Total investment must be a float or "
                                 + "integer.")
            elif (val <= 0):
                raise ValueError("The money to be invested in the "
                                 + "portfolio must be > 0.")
            else:
                self.__totalinvestment = val

    def addStock(self, stock):
        # adding stock to dictionary containing all stocks provided
        self.stocks.update({stock.name: stock})
        # adding information of stock to the portfolio
        self.portfolio = self.portfolio.append(
            stock.getInvestmentInfo(),
            ignore_index=True)
        # setting an appropriate name for the portfolio
        self.portfolio.name = "Portfolio information"
        # also add stock data of stock to the dataframe
        self._addStockData(stock.data)

        # compute expected return, volatility and Sharpe ratio of portfolio
        self.totalinvestment = self.portfolio.FMV.sum()
        self.expectedReturn = self.compExpectedReturn()
        self.volatility = self.compVolatility()
        self.sharpe = self.compSharpe()
        self.skew = self.__compSkew()
        self.kurtosis = self.__compKurtosis()

    def _addStockData(self, df):
        # loop over columns in given dataframe
        for datacol in df.columns:
            cols = len(self.data.columns)
            self.data.insert(loc=cols,
                             column=datacol,
                             value=df[datacol].values)
        # set index correctly
        self.data.set_index(df.index.values, inplace=True)
        # set index name:
        self.data.index.rename('Date', inplace=True)

    def getStock(self, name):
        '''
        Returns the instance of Stock with name <name>.
        '''
        return self.stocks[name]

    def compCumulativeReturns(self):
        '''
        Computes the cumulative returns of all stocks in the
        portfolio.
        (price_{t} - price_{t=0})/ price_{t=0}
        '''
        return cumulativeReturns(self.data)

    def compDailyReturns(self):
        '''
        Computes the daily returns (percentage change) of all
        stocks in the portfolio.
        '''
        return dailyReturns(self.data)

    def compDailyLogReturns(self):
        '''
        Computes the daily log returns of all stocks in the portfolio.
        '''
        return dailyLogReturns(self.data)

    def compMeanReturns(self, freq=252):
        '''
        Computes the mean return based on historical stock price data.

        Input:
         * freq: Integer (default: 252), number of trading days, default
             value corresponds to trading days in a year
        '''
        return historicalMeanReturn(self.data, freq=freq)

    def compWeights(self):
        '''
        Computes and returns a pandas.Series of the weights of the stocks
        of the portfolio
        '''
        # computes the weights of the stocks in the given portfolio
        # in respect of the total investment
        return self.portfolio['FMV']/self.totalinvestment

    def compExpectedReturn(self, freq=252):
        '''
        Computes the expected return of the portfolio.

        Input:
         * freq: Integer (default: 252), number of trading days, default
             value corresponds to trading days in a year
        '''
        pf_return_means = historicalMeanReturn(self.data,
                                               freq=freq)
        weights = self.compWeights()
        expectedReturn = weightedMean(pf_return_means.values, weights)
        self.expectedReturn = expectedReturn
        return expectedReturn

    def compVolatility(self, freq=252):
        '''
        Computes the volatility of the given portfolio.

        Input:
         * freq: Integer (default: 252), number of trading days, default
             value corresponds to trading days in a year
        '''
        # computing the volatility of a portfolio
        volatility = weightedStd(self.compCov(),
                                 self.compWeights()) * np.sqrt(freq)
        self.volatility = volatility
        return volatility

    def compCov(self):
        '''
        Compute and return a pandas.DataFrame of the covariance matrix
        of the portfolio.
        '''
        # get the covariance matrix of the mean returns of the portfolio
        returns = dailyReturns(self.data)
        return returns.cov()

    def compSharpe(self, riskFreeRate=0.005):
        '''
        Compute and return the Sharpe ratio of the portfolio

        Input:
         * riskFreeRate: Float (default=0.005), risk free rate
        '''
        # compute the Sharpe Ratio of the portfolio
        sharpe = sharpeRatio(self.expectedReturn,
                             self.volatility,
                             riskFreeRate)
        self.sharpe = sharpe
        return sharpe

    def __compSkew(self):
        '''
        Computes and returns the skewness of the stocks in the portfolio.
        '''
        return self.data.skew()

    def __compKurtosis(self):
        '''
        Computes and returns the Kurtosis of the stocks in the portfolio.
        '''
        return self.data.kurt()

    # optimising the investments based on volatility and sharpe ratio
    def optimisePortfolio(self,
                          total_investment=None,
                          num_trials=10000,
                          riskFreeRate=0.005,
                          freq=252,
                          verbose=True,
                          plot=True):
        '''
        Optimisation of the portfolio by performing a Monte Carlo simulation.

        Input:
         * total_investment: Float (default: None, which results in the sum of
             FMV of the portfolio information), money to be invested.
         * num_trials: Integer (default: 10000), number of portfolios to be
             computed, each with a random distribution of weights/investments
             in each stock
         * riskFreeRate: Float (default: 0.005), the risk free rate as required
             for the Sharpe Ratio
         * freq: Integer (default: 252), number of trading days, default
             value corresponds to trading days in a year
         * verbose: Boolean (default: True), if True, prints out optimised
             portfolio allocations
         * plot: Boolean (default: True), if True, a plot of the Monte Carlo
             simulation is shown
        '''
        # if total_investment is not set, use total FMV of given portfolio
        if (total_investment is None):
            total_investment = self.totalinvestment

        return optimiseMC(self.data,
                          num_trials=num_trials,
                          total_investment=total_investment,
                          riskFreeRate=riskFreeRate,
                          freq=freq,
                          initial_weights=self.compWeights().values,
                          verbose=verbose,
                          plot=plot)

    def properties(self):
        '''
        Nicely prints out the properties of the portfolio: expected return,
        volatility, Sharpe ratio, skewness, Kurtosis as well as the allocation
        of the stocks across the portfolio.
        '''
        # nicely printing out information and quantities of the portfolio
        string = "-"*50
        stocknames = self.portfolio.Name.values.tolist()
        string += "\nStocks: {}".format(", ".join(stocknames))
        string += "\nPortfolio expected return: {:0.3f}".format(
            self.expectedReturn)
        string += "\nPortfolio volatility: {:0.3f}".format(
            self.volatility)
        string += "\nPortfolio Sharpe ratio: {:0.3f}".format(
            self.sharpe)
        string += "\nSkewness:"
        string += "\n"+str(self.skew.to_frame().transpose())
        string += "\nKurtosis:"
        string += "\n"+str(self.kurtosis.to_frame().transpose())
        string += "\nInformation:"
        string += "\n"+str(self.portfolio)
        string += "\n"
        string += "-"*50
        print(string)

    def __str__(self):
        # print short description
        string = "Contains information about a portfolio."
        return string


def _correctQuandlRequestStockName(names):
    '''
    This function makes sure that all strings in the given list of
    stock names are leading with "WIKI/" as required by quandl to
    request data.

    Example: If an element of names is "GOOG" (which stands for
    Google), this function modifies the element of names to "WIKI/GOOG".
    '''
    # make sure names is a list of names:
    if (isinstance(names, str)):
        names = [names]
    reqnames = []
    # correct stock names if necessary:
    for name in names:
        if (not name.startswith('WIKI/')):
            name = 'WIKI/'+name
        reqnames.append(name)
    return reqnames


def _quandlRequest(names, start_date=None, end_date=None):
    '''
    This function performs a simple request from quandl and returns
    a DataFrame containing stock data.

    Input:
     * names: List of strings of stock names to be requested
     * start_date (optional): String/datetime of the start date of
         relevant stock data
     * end_date (optional): String/datetime of the end date of
         relevant stock data
    '''
    try:
        import quandl
    except ImportError:
        print("The following package is required:\n - quandl\n"
              + "Please make sure that it is installed.")
    # get correct stock names that quandl.get can request,
    # e.g. "WIKI/GOOG" for Google
    reqnames = _correctQuandlRequestStockName(names)
    return quandl.get(reqnames, start_date=start_date, end_date=end_date)


def _getQuandlDataColumnLabel(stock_name, data_label):
    '''
    Given stock name and label of a data column, this function returns
    the string "<stock_name> - <data_label>" as it can be found in a
    DataFrame returned by quandl.
    '''
    return stock_name+' - '+data_label


def _getStocksDataColumns(data, names, cols):
    '''
    This function returns a subset of the given DataFrame data, which
    contains only the data columns as specified in the input cols.

        Input:
         * data: A DataFrame which contains quantities of the stocks
             listed in pf_information
         * names: A string or list of strings, containing the names of the
             stocks, e.g. 'GOOG' for Google.
         * cols: A list of strings of column labels of data to be
             extracted.
        Output:
         * data: A DataFrame which contains only the data columns of
             data as specified in cols.
    '''
    # get correct stock names that quandl get request
    reqnames = _correctQuandlRequestStockName(names)
    # get current column labels and replacement labels
    reqcolnames = []
    for i in range(len(names)):
        for col in cols:
            # differ between dataframe directly from quandl and
            # possibly previously processed dataframe, e.g.
            # read in from disk with slightly modified column labels
            # 1. if <stock_name> in column labels
            if (names[i] in data.columns):
                colname = names[i]
            # 2. if "WIKI/<stock_name> - <col>" in column labels
            elif (_getQuandlDataColumnLabel(reqnames[i], col) in
                  data.columns):
                colname = _getQuandlDataColumnLabel(reqnames[i], col)
            # 3. if "<stock_name> - <col>" in column labels
            elif (_getQuandlDataColumnLabel(names[i], col) in
                  data.columns):
                colname = _getQuandlDataColumnLabel(names[i], col)
            # else, error
            else:
                raise ValueError("Could not find column labels in given "
                                 + "dataframe.")
            # append correct name to list of correct names
            reqcolnames.append(colname)

    data = data.loc[:, reqcolnames]
    # now rename the columns (removing "WIKI/" from column labels):
    newcolnames = {}
    for i in reqcolnames:
        newcolnames.update({i: i.replace('WIKI/', '')})
    data.rename(columns=newcolnames, inplace=True)
    # if only one data column per stock exists, rename column labels
    # to the name of the corresponding stock
    newcolnames = {}
    if (len(cols) == 1):
        for i in range(len(names)):
            newcolnames.update({_getQuandlDataColumnLabel(
                names[i], cols[0]): names[i]})
        data.rename(columns=newcolnames, inplace=True)
    return data


def _buildPortfolioFromQuandl(pf_information,
                              names,
                              start_date=None,
                              end_date=None):
    '''
    Returns a portfolio based on input in form of a list of strings/names
    of stocks.

    Input:
     * pf_information: DataFrame with the required data column
         labels "Name" and "FMV" of the stocks.
     * names: A string or list of strings, containing the names of the
         stocks, e.g. 'GOOG' for Google.
     * start_date (optional): String/datetime start date of stock data to
         be requested through quandl (default: None)
     * end_date (optional): String/datetime end date of stock data to be
         requested through quandl (default: None)
    Output:
     * pf: Instance of Portfolio which contains all the information
         requested by the user.
    '''
    # create an empty portfolio
    pf = Portfolio()
    # request data from quandl:
    data = _quandlRequest(names, start_date, end_date)
    # build portfolio:
    pf = _buildPortfolioFromDf(pf_information, data)
    return pf


def _stocknamesInDataColumns(names, df):
    '''
    Returns True if at least one element of names was found as a column
    label in the dataframe df.
    '''
    return any((name in label for name in names for label in df.columns))


def _buildPortfolioFromDf(pf_information,
                          data,
                          datacolumns=["Adj. Close"]):
    '''
    Returns a portfolio based on input in form of pandas.DataFrame.

    Input:
     * pf_information: DataFrame with the required data column labels
         "Name" and "FMV" of the stocks.
     * data: A DataFrame which contains prices of the stocks listed in
         pf_information
     * datacolumns (optional): A list of strings of data column labels
         to be extracted and returned (default: ["Adj. Close"]).
    Output:
     * pf: Instance of Portfolio which contains all the information
         requested by the user.
    '''
    # make sure stock names are in data dataframe
    if (not _stocknamesInDataColumns(pf_information.Name.values,
                                     data)):
        raise ValueError("Error: None of the provided stock names were"
                         + "found in the provided dataframe.")
    # extract only 'Adj. Close' column from DataFrame:
    data = _getStocksDataColumns(data,
                                 pf_information.Name.values,
                                 datacolumns)
    # building portfolio:
    pf = Portfolio()
    for i in range(len(pf_information)):
        # get name of stock
        name = pf_information.loc[i].Name
        # extract data column(s) of said stock
        stock_data = data.filter(regex=name).copy(deep=True)
        # if only one data column per stock exists, give dataframe a name
        if (len(datacolumns) == 1):
            stock_data.name = datacolumns[0]
        # create Stock instance and add it to portfolio
        pf.addStock(Stock(pf_information.loc[i],
                          data=stock_data))
    return pf


def _allListEleInOther(l1, l2):
    '''
    Returns True if all elements of list l1 are found in list l2.
    '''
    return all(ele in l2 for ele in l1)


def _anyListEleInOther(l1, l2):
    '''
    Returns True if any element of list l1 is found in list l2.
    '''
    return any(ele in l2 for ele in l1)


def _listComplement(A, B):
    '''
    Returns the relative complement of A in B (also denoted as A\\B)
    '''
    return list(set(B) - set(A))


def buildPortfolio(pf_information, **kwargs):
    '''
    This function builds and returns a portfolio given a set ofinput
    arguments.

    Input:
     * pf_information: This input is always required. DataFrame with
         the required data column labels "Name" and "FMV" of the stocks.
     * names: A string or list of strings, containing the names of the
         stocks, e.g. 'GOOG' for Google.
     * start (optional): String/datetime start date of stock data to be
         requested through quandl (default: None)
     * end (optional): String/datetime end date of stock data to be
         requested through quandl (default: None)
     * data (optional): A DataFrame which contains quantities of
         the stocks listed in pf_information
    Output:
     * pf: Instance of Portfolio which contains all the information
         requested by the user.

    Only the following combinations of inputs are allowed:
     * pf_information, names, start_date (optional), end_date (optional)
     * pf_information, data

    Moreover, the two different ways this function can be used are useful
    for
     1. building a portfolio by pulling data from quandl,
     2. building a portfolio by providing stock data which was obtained
         otherwise, e.g. from data files
    '''
    docstringMsg = "Please read through the docstring, " \
                   "'buildPortfolio.__doc__'."
    inputError = "Error: None of the input arguments {} are allowed " \
                 "in combination with {}. "+docstringMsg
    if (kwargs is None):
        raise ValueError("Error: "+docstringMsg)

    # create an empty portfolio
    pf = Portfolio()

    # list of all valid optional input arguments
    allInputArgs = ['names',
                    'start_date',
                    'end_date',
                    'data']

    # 1. names, start_date, end_date
    allowedInputArgs = ['names',
                        'start_date',
                        'end_date']
    complementInputArgs = _listComplement(allowedInputArgs, allInputArgs)
    if (_allListEleInOther(['names'], kwargs.keys())):
        # check that no input argument conflict arises:
        if (_anyListEleInOther(complementInputArgs, kwargs.keys())):
            raise ValueError(inputError.format(
                complementInputArgs, allowedInputArgs))
        # get portfolio:
        pf = _buildPortfolioFromQuandl(pf_information, **kwargs)

    # 2. data
    allowedInputArgs = ['data']
    complementInputArgs = _listComplement(allowedInputArgs, allInputArgs)
    if (_allListEleInOther(['data'], kwargs.keys())):
        # check that no input argument conflict arises:
        if (_anyListEleInOther(_listComplement(
             allowedInputArgs, allInputArgs), kwargs.keys())):
            raise ValueError(inputError.format(
                complementInputArgs, allowedInputArgs))
        # get portfolio:
        pf = _buildPortfolioFromDf(pf_information, **kwargs)

    return pf
