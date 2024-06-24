import streamlit_authenticator as stauth
from utils.db_query import custom_query
import streamlit as st
import datetime

def user_authantication(user_list=custom_query("SELECT email, name, password FROM data.user;")):
    usernames = user_list['email'].to_list()
    names = user_list['name'].to_list()
    hashed_passwords = user_list['password'].to_list()
    authenticator = stauth.Authenticate(names, usernames, hashed_passwords, "sales_dashboard", "abcdef", cookie_expiry_days=30)
    name, authentication_status, username = authenticator.login("Login", "main")
    return name, authentication_status, username, authenticator

def auth_widgets():
    name, authentication_status, username, authenticator = user_authantication()

    if not authentication_status:
        st.stop()
        
    st.sidebar.write(f"Welcome *{name}*!")
    authenticator.logout('Logout', 'sidebar')


def add_position(df, col_name):
    """
    input: any dataframe
    output: dataframe with a column "Position", cumulative counting number starting from 0, and reset if the col_name change.
    """
    df['Position'] = df.groupby(col_name).cumcount()
    return df

def get_start_and_end_date_from_calendar_week(year, calendar_week):
    """
    input: year number, int; iso week number
    output: start date and end date of the week, data type: datetime
    """
    monday = datetime.datetime.strptime(f'{year}/{calendar_week}/1', "%Y/%W/%w").date()
    return monday, monday + datetime.timedelta(days=6.9)
