import time
import streamlit as st
import pandas as pd
import sqlalchemy as db
from utils.get_master_data import location_id2name, location_name2id
from utils.send_email import send_email
from utils.db_query import run_query, get_row_number, init_connection
from utils.utilities import  user_authantication
st.set_page_config(layout="wide")

name, authentication_status, username, authenticator = user_authantication()
if authentication_status:
    st.sidebar.write(f"Welcome *{name}*!")
    authenticator.logout('Logout', 'sidebar')

    def change_state(df_len, con, table_name, query, placeholder):
        delete_query = query.replace("SELECT", "DELETE").replace("* ", "")
        placeholder.info(preview_query)
        try:
            placeholder.info(f'Start deleting {df_len} rows of {table_name.replace("_"," ")}...',icon="ℹ️")
            start_time = time.time()
            old_row_number = get_row_number(engine=con, table_name=table_name)
            run_query(con, delete_query)
            new_row_number = get_row_number(engine=con, table_name=table_name)
            end_time = time.time()
            if new_row_number - old_row_number != 0:
                placeholder.success(f'{old_row_number - new_row_number} of rows of {table_name.replace("_"," ")} has been deleted from the database in {round(end_time - start_time,2)} seconds.',icon="✅")
        except Exception as e:
            placeholder.error(f'Something is wrong when deleting data to the database.', icon="🚨")
            if st.secrets['EMAIL_ALERT']:
                send_email(st.secrets["OFFICE_USN"], f'Error message when deleting {table_name.replace("_", " ")}', e)
            st.stop()
        finally:
            time.sleep(5)
            placeholder.empty()

    # Init database connection
    con = init_connection()


    st.markdown("# Select table you need to modify?")
    # This will print all the avaliable table names
    table_options = ['< Please select one table >']+db.inspect(con).get_table_names()
    table_options.remove('delivery')
    db_option_de = st.selectbox("Available database table options:",table_options, key='db_option_de')
    display_report = False
    month_list = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    month = None
    year = None

    if db_option_de != '< Please select one table >':
        if db_option_de == 'month_data':
            criteria_columns = ['month','country_code']
        elif db_option_de == 'sales_data':
            criteria_columns = st.selectbox("Select fields you need to filter: ",['date', 'upload_time', 'location_internal_id'],key=f"{db_option_de}_criteria_columns")
        elif db_option_de == 's_card_purchase_data' or db_option_de == 'workshift_data' or db_option_de == 'purchase_data':
            criteria_columns = st.selectbox("Select fields you need to filter: ",['date', 'upload_time'], key=f"{db_option_de}_criteria_columns")
        elif db_option_de == 'invoice_data':
            criteria_columns = st.selectbox("Select fields you need to filter: ",['date', 'location_internal_id'], key=f"{db_option_de}_criteria_columns")

        if 'month' in criteria_columns:
            st.markdown("### Select year and month of the data you wish to delete.")
            year_col, month_col = st.columns([1,3])
            year = year_col.number_input('Year', value=2022, step=1, key=f"{db_option_de}_year_delete")
            month_selected = month_col.select_slider('Month', options=month_list, key=f"{db_option_de}_month_delete")
            month = month_list.index(month_selected) + 1
            if 'country_code' in criteria_columns:
                country_code = st.radio("Please select contry code:",('FI', 'EE', 'NO'),horizontal=True)

        if 'date' in criteria_columns:
            start_col, end_col = st.columns([1,1])
            start_date = start_col.date_input("Start date:", key=f"{db_option_de}_start_date_delete")
            end_date = end_col.date_input("End date:", key=f"{db_option_de}_end_date_delete")

        if 'upload_time' in criteria_columns:
            list_upload_time = pd.read_sql(f"""SELECT DISTINCT(upload_time) FROM data.{db_option_de}""", con)['upload_time'].astype(str).values.tolist()
            upload_time_selected = st.selectbox("Select the data upload time you need to delete: ",list_upload_time, key=f"{db_option_de}_upload_time_delete")
        if 'location_internal_id' in criteria_columns:
            list_intenal_id = pd.read_sql(f"""SELECT DISTINCT(location_internal_id) FROM data.{db_option_de}""", con)['location_internal_id'].values.tolist()
            list_intenal_name = location_id2name(list_intenal_id)
            internal_name_selected = st.multiselect("Select the location name you need to delete: ",list_intenal_name, key=f"{db_option_de}_internal_name_selected_delete")
            internal_id_selected = location_name2id(internal_name_selected)

        preview_query = f"""SELECT * FROM data.{db_option_de}\n"""
        if 'month' in criteria_columns:
            preview_query += f"WHERE month = {month} AND year = {year}\n"
            if 'country_code' in criteria_columns:
                preview_query += f"AND account_id LIKE '{country_code}%';"

        if 'date' in criteria_columns:
            preview_query += f"WHERE date BETWEEN '{start_date}' AND '{end_date}';"
        if 'upload_time' in criteria_columns:
            preview_query += f"WHERE upload_time = '{pd.to_datetime(upload_time_selected)}';"
        if 'location_internal_id' in criteria_columns:
            preview_query += f'WHERE location_internal_id in ({", ".join([str(i) for i in internal_id_selected])});'
        
        
        preview_btn = st.button("Preview", key=f"{db_option_de}_preview_btn")
        delete_btn = False
        df = None
        if preview_btn:
            st.info(preview_query)
            df = pd.read_sql(preview_query, con)
            st.dataframe(df)
            placeholder = st.empty()

            delete_btn = placeholder.button(
                "Delete from database",
                key=f"{db_option_de}_del_btn",
                on_click=change_state,
                kwargs=dict(
                    df_len=df.shape[0],
                    con=con,
                    table_name=db_option_de,
                    query=preview_query,
                    placeholder=placeholder
                )
            )

