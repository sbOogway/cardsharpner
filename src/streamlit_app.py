from pprint import pprint
import streamlit as st
import pandas as pd
from datetime import datetime
import logging
from decimal import Decimal
import streamlit_charts
import utils
import api

# import warnings
# warnings.simplefilter(action='ignore', category=FutureWarning)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.INFO)
# console_handler.setFormatter(log_format)

# logger.addHandler(console_handler)


# Page configuration

class HeroDataAnalyzer:
    def __init__(self):
        self.df = None
        self.sessions_retrieved = dict()

    def fetch_sessions(self, sessions_iterable, username):
        for session in sessions_iterable:
            if "session" == "all":
                continue
            id = session.split(" - ")[-1]
            try:
                # do not remove tmp variable otherwise st renders df on top of page
                tmp = st.session_state[session]
            except KeyError:
                data = api.get_player_hands(username, id)
                st.session_state[session] = pd.DataFrame.from_dict(data["data"]) 
    
    def update_hands_df(self, sessions_iterable):
        for session in sessions_iterable:
            if session == "all":
                continue
            self.df = pd.concat([self.df, st.session_state[session]])


    def display_sessions_all(self, username):
        sessions_iterable = st.session_state.poker_sessions
        self.fetch_sessions(sessions_iterable, username)
        self.update_hands_df(sessions_iterable)


    def display_sessions_from_select(self, username):
        sessions_iterable = st.session_state.poker_session_ids
        self.fetch_sessions(sessions_iterable, username)
        self.update_hands_df(sessions_iterable)

    def display_sessions(self, username):
        self.df = pd.DataFrame()
        if "all" in st.session_state.poker_session_ids:
            self.display_sessions_all(username)
        else:
            self.display_sessions_from_select(username)

    def get_hands(self, username: str, session_id: str = None):
        if session_id in self.data.keys():
            return
        
        data = api.get_player_hands(username, session_id)
        df = pd.DataFrame.from_dict(data["data"])
        self.data[session_id] = df
        self.df = df

    def calculate_key_metrics(self):
        """Calculate key performance metrics"""
        if self.df is None or self.df.empty:
            return {}

        self.df["timestamp"] = self.df["time"].apply(
            lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S%z")
        )
        self.df = self.df.sort_values("timestamp")


        # assertions
        fail_mask_1 = (
            (self.df["total_collected"].apply(lambda x: Decimal(str(x))) - self.df["total_contributed"].apply(lambda x : Decimal(str(x))))
            == self.df["net_profit"].apply(lambda x: Decimal(str(x)))
        )

        net_profit          = utils.to_decimal(self.df["net_profit"])
        rake_amount         = utils.to_decimal(self.df["rake_amount"])
        net_profit_before   = utils.to_decimal(self.df["net_profit_before_rake"])

        positive_mask = net_profit > 0
        negative_mask = ~positive_mask

        cond1 = (net_profit[positive_mask] + rake_amount[positive_mask]) == net_profit_before[positive_mask]
        cond2 = net_profit[negative_mask] == net_profit_before[negative_mask]

        assert cond1.all() and cond2.all()
        assert all(fail_mask_1)

        # calculations
        self.df["running_profit"] = self.df["net_profit"].cumsum()
        self.df["running_profit_before_rake"] = self.df[
            "net_profit_before_rake"
        ].cumsum()
        self.df["running_rake"] = (
            self.df["rake_amount"].where(self.df["net_profit"] > 0).cumsum()
        )
        self.df["hand_number"] = range(1, len(self.df) + 1)

        self.df["stakes"] = self.df["game"].apply(lambda x: x.split("_")[2])

        total_hands = len(self.df)
        total_profit = self.df["net_profit"].sum()
        total_profit_before_rake = self.df["net_profit_before_rake"].sum()
        # total_profit_after_rake = self.df["net_profit_after_rake"].sum()
        total_rake = self.df["rake_amount"].where(self.df["net_profit"] > 0).sum()

        avg_profit = self.df["net_profit"].mean()
        avg_profit_before_rake = self.df["net_profit_before_rake"].mean()
        avg_rake = self.df["rake_amount"].mean()
        total_pot_size = self.df["total_pot_size"].sum()
        rake_percentage = (
            (total_rake / total_pot_size * 100) if total_pot_size > 0 else 0
        )
        # vpip metrics (separate from pfr)
        vpip_hands = self.df["vpip"].sum()
        vpip_rate = (vpip_hands / total_hands) * 100 if total_hands > 0 else 0

        # flop metrics
        saw_flop = self.df["saw_flop"].sum()
        flop_rate = (saw_flop / total_hands) * 100 if total_hands > 0 else 0

        won_when_saw_flop = self.df["won_when_saw_flop"].sum()
        flop_win_rate = (won_when_saw_flop / saw_flop) * 100 if saw_flop > 0 else 0

        # showdown metrics (only calculated on hands where hero saw flop)
        went_to_showdown = self.df["went_to_showdown"].sum()
        showdown_rate = (went_to_showdown / saw_flop) * 100 if saw_flop > 0 else 0

        # won at showdown (w$sd) - percentage of showdowns won
        won_at_showdown = self.df["won_at_showdown"].sum()
        won_at_showdown_rate = (
            (won_at_showdown / went_to_showdown) * 100 if went_to_showdown > 0 else 0
        )

        # preflop metrics
        preflop_raised = self.df["preflop_raised"].sum()
        preflop_raise_rate = (
            (preflop_raised / total_hands) * 100 if total_hands > 0 else 0
        )

        preflop_called = self.df["preflop_called"].sum()
        preflop_call_rate = (
            (preflop_called / total_hands) * 100 if total_hands > 0 else 0
        )

        # c-bet metrics
        cbet_flop = self.df["cbet_flop"].sum()
        cbet_turn = self.df["cbet_turn"].sum()
        cbet_river = self.df["cbet_river"].sum()

        return {
            "total_hands": total_hands,
            "total_profit": total_profit,
            "total_profit_before_rake": total_profit_before_rake,
            # 'total_profit_after_rake': total_profit_after_rake,
            "total_rake": total_rake,
            "avg_profit": avg_profit,
            "avg_profit_before_rake": avg_profit_before_rake,
            "avg_rake": avg_rake,
            "rake_percentage": rake_percentage,
            "vpip_hands": vpip_hands,
            "vpip_rate": vpip_rate,
            "went_to_showdown": went_to_showdown,
            "showdown_rate": showdown_rate,
            "saw_flop": saw_flop,
            "flop_rate": flop_rate,
            "won_when_saw_flop": won_when_saw_flop,
            "flop_win_rate": flop_win_rate,
            "won_at_showdown": won_at_showdown,
            "won_at_showdown_rate": won_at_showdown_rate,
            "preflop_raised": preflop_raised,
            "preflop_raise_rate": preflop_raise_rate,
            "preflop_called": preflop_called,
            "preflop_call_rate": preflop_call_rate,
            "cbet_flop": cbet_flop,
            "cbet_turn": cbet_turn,
            "cbet_river": cbet_river,
        }


def main():
    st.set_page_config(
    page_title="Poker Session analyzer",
    page_icon=":material/poker_chip:",
    layout="wide",
    initial_sidebar_state="expanded",
)

    if "analyzer" not in st.session_state:
        st.session_state.analyzer = HeroDataAnalyzer()

    # if "sessions" not in st.session_state:
    #     st.session_state.poker_session_ids = []

    analyzer = st.session_state.analyzer

    sessions = api.get_sessions()
    sessions = utils.format_sessions_selection(sessions)
    st.session_state.poker_sessions = sessions
    # pprint(sessions)

    st.title("📊 Poker Session Analyzer")

    
    c1, c2 = st.columns([3, 1])

    with c2:
        username = st.text_input("Your username", "caduceus369")

    with c1:
        st.multiselect("sessions", ["all"] + sessions, default=[], on_change=analyzer.display_sessions, key="poker_session_ids", args=(username,))
        
    


    with st.sidebar:
        files = st.file_uploader("📤 Upload file", accept_multiple_files=True)

        currency = st.text_input("currency", "€")
        
        session_id = st.text_input("Session id", "M62C33044BB297NJ")
        

        if st.button("🔄 Upload Data"):
            for file in files:
                response = api.upload_hands(
                    {"file": (file.name, file.getvalue(), "text/plain")}
                )
                if response["status"] != "got em":
                    st.toast("error uploading data", icon="❌")
                logger.info(response)
            st.toast(f"uploaded {len(files)} hand files to database", icon="✅")

        if st.button("🔁 Reload Data"):
            if session_id:
                analyzer.get_hands(username, session_id)
            else:
                analyzer.get_hands(username, "all")
            st.toast(f"retrieved {len(analyzer.df)} hands from database", icon="✅")

        if st.button("🔬 Analyze Data"):
            response = api.analyze_hands(username)
            logger.info(response)
            st.toast(f"analyzed hands from {username}", icon="✅")


    if analyzer.df is not None and not analyzer.df.empty:
        metrics = analyzer.calculate_key_metrics()
            
        st.header("📈 Overview Metrics")
        streamlit_charts.render_overview_metrics(metrics)

        st.header("💰 Results")
        streamlit_charts.render_results_chart(analyzer.df, currency=currency)

        st.header("📍 Position Analysis")
        streamlit_charts.render_position_analysis(analyzer.df)

        st.header("💵 Stakes Analysis")
        streamlit_charts.render_stakes_analysis(analyzer.df)

        # st.header("🃏 Hand Type Analysis")
        # streamlit_charts.render_hand_strength_analysis(analyzer.df)

        st.header("📋 Detailed Hand Data")
        streamlit_charts.render_detailed_data(analyzer.df)

        # Export section
        st.header("💾 Export Data")
        streamlit_charts.export_data(analyzer.df)



    streamlit_charts.render_external_tools()


if __name__ == "__main__":
    main()
