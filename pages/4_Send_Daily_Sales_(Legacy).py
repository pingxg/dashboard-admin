import streamlit as st
from utils.utilities import auth_widgets
from utils.get_master_data import get_master_data
import pandas as pd
import numpy as np
from utils.send_email import send_email
st.set_page_config(layout="wide")

auth_widgets()

st.markdown("# Send Daily Sales")

with st.form("my_form"):
    txt_data = st.file_uploader('Upload SOK daily sales report', type='txt', help="Find it from SOK", accept_multiple_files=False)
    submitted = st.form_submit_button("Submit")
    if txt_data is not None:
        email_master_data = get_master_data("Location")[['Ketjuyksikkö (SOK)','email']]
        master_sale_item = get_master_data("SalesItem")[['Display Name/code','Item Category']]
        master_sale_item = master_sale_item.drop_duplicates()

        email_master_data.dropna(inplace=True)
        email_master_data = email_master_data.drop_duplicates()

        df = pd.read_csv(txt_data, sep=";", encoding="utf-16", skiprows=[0,1]).fillna(0)        # read the sok data, with utf-16 encoding, skip first 2 rows and fill NaN value with 0
        df = df.drop(['Etiketin lisäteksti', 'KP koko', 'My vol (kilo, litra)','AOK'], axis=1)      # delete these columns
        df.columns = ["Date", "Store", "EAN","Product Name","Sales Unit","Tax Rate","Amount (ALV14)", "Quantity"]       # rename columns according to current order
        df['Amount (ALV14)'] = df['Amount (ALV14)'].astype(str).str.replace(' ', '')      # remove all the spaces in the value
        df['Amount (ALV14)'] = df['Amount (ALV14)'].astype(str).str.replace(',', '.').astype(float)       # replace all the "," to "." in the value
        df['Quantity'] = df['Quantity'].astype(str).str.replace(' ', '')        # remove all the spaces in the value
        df['Quantity'] = df['Quantity'].astype(str).str.replace(',', '.').astype(float)     # replace all the "," to "." in the value
        df['Date'] = pd.to_datetime(df['Date'],format='%d.%m.%Y')

        result = pd.merge(df, email_master_data, left_on='Store', right_on='Ketjuyksikkö (SOK)',how='left')
        result= pd.merge(result, master_sale_item, left_on='Product Name', right_on='Display Name/code',how='left')

        result = result.drop(['Ketjuyksikkö (SOK)','Tax Rate','Display Name/code'], axis=1)
        result = result.dropna()

        result['Date'] = result['Date'].astype(str)
        result = result[~result['Item Category'].isin(['Valmisruoat', 'Tuore Valmisruoat'])]
        st.dataframe(result, use_container_width=True)

        if submitted:
            for i in list(np.unique(result['email'])):
                sub_result = result.loc[result['email']==i]
                sub_result = sub_result.sort_values(by=['Date', 'Item Category'], ascending=[False, True])

                # Create a pivot table
                pivot_df = sub_result.melt(id_vars=['Store', 'Date', 'Item Category'], 
                                value_vars=['Amount (ALV14)', 'Quantity'], 
                                var_name='Metrics', 
                                value_name='Values')

                pivot_df = pivot_df.pivot_table(
                    index=['Store', 'Date'],
                    columns=['Item Category', 'Metrics'],
                    values='Values',
                    aggfunc='sum'
                )

                pivot_df=pivot_df.sort_index(level=['Store', 'Date'], ascending=[True, False])
                pivot_df = pivot_df.fillna(0)

                subject = f"Last 7 day sales - {sub_result['Store'].iloc[0]} ({sub_result['Date'].iloc[-1]}~{sub_result['Date'].iloc[0]})"
                send_email(i, subject, pivot_df)
                st.success(f'{i}', icon="✅")
            st.balloons()