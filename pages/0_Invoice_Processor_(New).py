import pandas as pd
import streamlit as st
from sqlalchemy import text
from utils.utilities import auth_widgets, add_position, get_start_and_end_date_from_calendar_week

st.set_page_config(layout="wide")
auth_widgets()

# Start writing title
st.markdown("# Invoice CSV template 🎈")

sok_tab, delivery_tab = st.tabs(["On-Site sales", "Delivery sales"])

# Input field for NS external ID
last_external_id = int(sok_tab.number_input('Insert last Internal ID in NetSuite.', step=1, key='last_external_id'))

# Create file uploader
sok_data = sok_tab.file_uploader('Upload SOK sales report', type='xlsx', help="Find it from SOK", accept_multiple_files=False)
if sok_data is not None:
    # Read the Excel file
    df = pd.read_excel(sok_data)

    # Display the dataframe
    st.write(df)

