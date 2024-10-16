import streamlit as st
import time
import pandas as pd
from utils.send_email import send_email
from utils.db_query import get_row_number, init_connection
from utils.utilities import auth_widgets
from sqlalchemy import text
from io import BytesIO
st.set_page_config(layout="wide")

auth_widgets()


st.markdown("# Process delivery data")
con = init_connection()
with con.connect() as conn:
    result = conn.execute(text("DESCRIBE delivery;")).fetchall()
    delivery_store = [i[0] for i in result if i[0] != 'date']

raw_data = st.file_uploader("Upload delivery data", type='xlsx')
if raw_data is not None:
    df = pd.read_excel(BytesIO(raw_data.read()), engine='openpyxl')
    df = df.fillna(0)
    df['date'] = pd.to_datetime(df['date']).dt.date
    for i in delivery_store:
        if i not in df.columns.values.tolist():
            df[i] = 0

    if df is not None:
        st.dataframe(df, use_container_width=True)
        info_placeholder = st.empty()
        upload_btn = info_placeholder.button("Upload to Database", key=f"delivery_upload_button")
        if upload_btn and df is not None:
            try:
                info_placeholder.info(f'Start uploading {df.shape[0]} rows of delivery data...',icon="ℹ️")
                start_time = time.time()
                old_row_number = get_row_number(engine=con, table_name='delivery')
                df.to_sql(name='delivery', con=con, schema="data", index=False, if_exists='append', chunksize=1000, method='multi')
                new_row_number = get_row_number(engine=con, table_name='delivery')
                end_time = time.time()
                if new_row_number - old_row_number != 0:
                    info_placeholder.success(f'{new_row_number - old_row_number} of rows of delivery data has been added to the database in {round(end_time - start_time,2)} seconds.',icon="✅")
            except Exception as e:
                info_placeholder.error(f'Something is wrong when uploading data to the database.', icon="🚨")
                if st.secrets['EMAIL_ALERT']:
                    send_email(st.secrets["OFFICE_USN"], f'Error message when uploading delivery data', e)
                st.stop()
            finally:
                time.sleep(5)
                info_placeholder.empty()
