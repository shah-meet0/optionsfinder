import get_access_token as gat
from kiteconnect import KiteConnect
import pandas as pd
import time


class OptionBoxFinder:
    def __init__(self):
        access_token_1 = gat.get_access_token()
        # Comes from another class made by me to get the access token for kite,
        # but that class contains sensitive information, and is not relevant to this class beyond instantiation of kite.
        kite_1 = KiteConnect(api_key)  # Requires kite API key
        kite_1.set_access_token(access_token_1)
        self.kite_session = kite_1 

    def get_instrument_dump(self):
        df = pd.DataFrame(self.kite_session.instruments())
        return df

    @staticmethod
    def get_expiries(trading_name, instrument_dump, is_df_already=True):
        if not is_df_already:
            instrument_dump = pd.DataFrame.to_csv(instrument_dump)
        all_ins_df = instrument_dump[instrument_dump['name'] == trading_name]
        expiry_dates = all_ins_df['expiry'].unique()[0:4]  # Only getting first few expiry dates for liquidity.
        return expiry_dates

    @staticmethod
    def get_options_for_expiry(trading_name, instrument_dump, expiry_date, is_df_already=True):
        if not is_df_already:
            instrument_dump = pd.DataFrame.to_csv(instrument_dump)
        all_ins_df = instrument_dump[instrument_dump['name'] == trading_name]
        option_tickers = all_ins_df[all_ins_df['expiry'] == expiry_date]
        option_names_temp = option_tickers['tradingsymbol'].unique()
        option_names = {}
        strikes = []
        for option_symbol in option_names_temp:
            temp = all_ins_df[all_ins_df['tradingsymbol'] == option_symbol]
            strike = temp['strike'].iloc[0]
            if strike % 500 == 0 and temp['segment'].iloc[0] == 'NFO-OPT':
                option_names["NFO:" + option_symbol] = strike
                strikes.append(strike)
        strikes = [*{*strikes}]  # Gets unique values from strikes
        strikes.sort()
        return [option_names, strikes]  # Returns the names of options and their strike prices.

    def get_quotes(self, option_names):
        quotes = self.kite_session.quote(option_names.keys())
        return quotes

    @staticmethod
    def quote_to_dataframe(quotes, options):
        # extracts relevant information from the quote and puts it into a data frame
        df = pd.DataFrame(index=list(options), columns=["strike", "bid", "ask", "type"])
        for option in options.keys():
            if option[-2:] == "CE":
                df.type[option] = 'call'
            else:
                df.type[option] = 'put'
            temp = quotes[option]
            df.strike[option] = options[option]
            df.bid[option] = temp['depth']['buy'][0]['price']
            df.ask[option] = temp['depth']['sell'][0]['price']
        return df

    @staticmethod
    def get_profit_long(strike_1, strike_2, df):
        # LONG POSITION ONLY, cannot short negative profits(as bid,ask would change)

        strike_payoff = strike_2 - strike_1
        call_lower = df.loc[(df['strike'] == strike_1) & (df['type'] == 'call')]
        put_lower = df.loc[(df['strike'] == strike_1) & (df['type'] == 'put')]
        call_higher = df.loc[(df['strike'] == strike_2) & (df['type'] == 'call')]
        put_higher = df.loc[(df['strike'] == strike_2) & (df['type'] == 'put')]
        try:
            call_lower_cost = call_lower['ask'][0]
            put_lower_cost = put_lower['bid'][0]
            call_higher_cost = call_higher['bid'][0]
            put_higher_cost = put_higher['ask'][0]
            option_cost = call_lower_cost + put_higher_cost - (call_higher_cost + put_lower_cost)
            total_payoff = strike_payoff - option_cost
            return total_payoff
        except IndexError:  # To account for some options where prices are unknown
            return -1

    def execute_option_box(self, stock, min_profit, sleep_time=10):
        """
        Executes searches for option boxes using Kite API
        :param stock: Stock whose options are to be used. Needs to be trading name (eg. "BANKNIFTY")
        :param min_profit: Minimum profit (in Rs) of option box in order for it to be shown
        :param sleep_time: Amount of time between two checks for option boxes.
        :return: List of strikes for which option box provides higher profit than min_profit
        """
        instrument_dump = self.get_instrument_dump() 
        expiry_dates = self.get_expiries(stock, instrument_dump, True)
        expiry_to_use = expiry_dates[0]
        print("Currently checking {date}".format(date=expiry_to_use))
        options_and_strike = self.get_options_for_expiry(stock, instrument_dump, expiry_to_use, True)
        options_on_expiry = options_and_strike[0]
        strikes = options_and_strike[1]
        iteration = 0
        while True:
            iteration += 1
            print(str(iteration))
            option_quotes = self.get_quotes(options_on_expiry)
            price_info = self.quote_to_dataframe(option_quotes, options_on_expiry)
            for i in range(0, len(strikes)-1):
                for j in range(i+1, len(strikes)):
                    profit = self.get_profit_long(strikes[i], strikes[j], price_info)
                    if profit > min_profit:
                        print(str(strikes[i]), str(strikes[j]), str(profit))
                        self.make_order(strikes[i], strikes[j])
            time.sleep(sleep_time)

    def make_order(self, option_1, option_2):
        pass
