import streamlit_authenticator as stauth
from utils.db_query import custom_query

def user_authantication(user_list=custom_query("SELECT email, name, password FROM data.user;")):
    usernames = user_list['email'].to_list()
    names = user_list['name'].to_list()
    hashed_passwords = user_list['password'].to_list()
    authenticator = stauth.Authenticate(names, usernames, hashed_passwords, "sales_dashboard", "abcdef", cookie_expiry_days=30)
    name, authentication_status, username = authenticator.login("Login", "main")
    return name, authentication_status, username, authenticator