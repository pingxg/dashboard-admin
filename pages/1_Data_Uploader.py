import time
import pytz
import datetime
import warnings
import pandas as pd
import sqlalchemy as db
import streamlit as st
import numpy as np
from utils.db_query import init_connection, custom_query
from utils.get_master_data import LOCATION_MASTER, get_master_data
from utils.send_email import send_email
from utils.utilities import auth_widgets
from io import BytesIO


warnings.filterwarnings('ignore')
st.set_page_config(layout="wide")

auth_widgets()

# Initialization of session
if 'upload_history' not in st.session_state:
    st.session_state['upload_history'] = dict()


# Get master location data
PRODUCT_MASTER = get_master_data('SalesItem')
location_master_data = LOCATION_MASTER[['Location (NS)', 'Internal ID']].dropna().drop_duplicates()
location_master_data_name2id = LOCATION_MASTER[['Ketjuyksikkö (SOK)', 'Internal ID']].dropna().drop_duplicates()
product_master_data = PRODUCT_MASTER[['EAN', 'Item Category', 'Sale Units', 'Internal ID PROD', 'Display Name/code']]
product_master_data = product_master_data.dropna().drop_duplicates()

account_master_data = custom_query("SELECT * FROM master.financial_account")


vendor_type = {
    '1426362 Kalaneuvos Oy':"Salmon",
    '1394052 HÄTÄLÄ OY F56451':'Salmon',
    '1389643 FINNISH FRESHFISH OY':'Salmon',
    '2000112 Fina Fisken Åland Ab':'Salmon',
    '2000009 Fisu Pojat Oy':'Salmon',
    '2000003 Domstein Sjømat AS':'Salmon',
    '1405002 KALAVALTANEN OY': 'Salmon',
    '2000219 Firewok Finland Oy': 'Salmon',
    '2000207 Itsudemo Finland Oy': 'Salmon',
    '1578999 Oy Golden Crop AB':"GC",
}

# Define file uploader and error checking
def file_uploader(label, type="csv", country="FI", sep=";", help=None, allow_multiple=False):
    df = None
    try:
        data = st.file_uploader(f'Upload {label.replace("_"," ")}', type=type, help=help, key=f"{label}_up", accept_multiple_files=allow_multiple)
        if data:
            if type == "csv" or type == "CSV":
                if label == "month_data" or label == "financial_data":
                    if country == "FI":
                        df = pd.read_csv(data, sep=sep, skiprows=6)
                elif label == 'workshift_data':
                    df = pd.read_csv(data, sep=sep, encoding='cp1252')
                else:
                    df = pd.read_csv(data, sep=sep, on_bad_lines='skip')

            elif type == "xlsx" or type == "xls":
                if label == "sales_data" and country == "NO":
                    if isinstance(data, list):
                        output = pd.DataFrame()
                        for file in data:
                            df = pd.read_excel(BytesIO(file.read()), engine='openpyxl')  # Convert to bytes-like object
                            output = pd.concat([df, output], sort=False)
                        df = output.copy()
                elif label in ["month_data", "financial_data"] and country == "EE":
                    df = pd.read_excel(BytesIO(data.read()), engine='openpyxl')  # Convert to bytes-like object
                elif label in ["month_data", "financial_data"] and country == "NO":
                    df = pd.read_excel(BytesIO(data.read()), engine='openpyxl')  # Convert to bytes-like object
                elif label == "invoice_data" and country == "EE":
                    df = pd.read_excel(BytesIO(data.read()), engine='openpyxl')  # Convert to bytes-like object
                if label == "sales_data" and country == "EE":
                    if isinstance(data, list):
                        output = pd.DataFrame()
                        for file in data:
                            df = pd.read_excel(BytesIO(file.read()), engine='openpyxl')  # Convert to bytes-like object

                            df = df.iloc[2:]
                            df = df.reset_index(drop=True)
                            # drop the columns if the first row is empty
                            df = df.loc[:, df.iloc[0].notna()]


                            # promot the first row to header
                            df.columns = df.iloc[0]
                            df.columns = df.columns.str.lower()
                            column_mapping = {
                                "store": "store_name",
                                "date": "date",
                                "product name": "product_name",
                                "sales excluding vat": "_amount",
                                "sales including vat": "_amount_vat",
                                "sales quantity": "quantity",
                            }
                            df.rename(columns=column_mapping, inplace=True)
                            df = df.iloc[1:]
                            
                            # remove the row with the empty amount for column "prouct_name"
                            df = df[df['product_name'].notna()]
                            df = df.reset_index(drop=True)
                            
                            # downfill all the empty values
                            df = df.ffill()
                            output = pd.concat([df, output], sort=False)

                        df = output.copy()
                    else:
                        df = pd.read_excel(BytesIO(data.read()), engine='openpyxl')  # Convert to bytes-like object

            elif type == "txt" or type == "TXT":
                if label == "purchase_data":
                    df = pd.read_csv(data, sep=sep, skiprows=4)
    except Exception as e:
        st.error(e, icon="🚨")
        print(e)
        st.stop()


    if df is not None:
        if isinstance(data, list):
            filenames = "".join([i.name for i in data])
        else:
            filenames = data.name
    
        return df, filenames
    else:
        return None, None


def process_data(df, filename, table_name, country=None, month=None, year=None):
    upload_df = None
    try:
        if table_name == "sales_data":
            if country == "FI":
                    upload_df = df[['Delivery Note Date','Store', 'Sales Unit', 'Quantity', 'Location (NS)', 'Sales Item Internal ID', 'Sales Item Category', 'Amount']]
                    upload_df.rename(columns={
                        'Delivery Note Date': 'date_str',
                        'Store': 'store_name',
                        'Sales Unit': 'unit',
                        'Quantity': 'quantity',
                        'Location (NS)': 'location_internal_name',
                        'Sales Item Internal ID': 'product_internal_id',
                        'Sales Item Category': 'product_catagory',
                        'Amount': 'amount',
                        }, inplace=True)
                    upload_df['location_internal_id'] = upload_df['location_internal_name'].map(dict(zip(location_master_data['Location (NS)'],location_master_data['Internal ID']))).astype(int)
                    upload_df['quantity'] = upload_df['quantity'].astype(str)
                    upload_df['amount'] = upload_df['amount'].astype(str)
                    upload_df['quantity'] = upload_df['quantity'].str.replace(',', '.', regex=False).astype(float).round(decimals=2)
                    upload_df['amount'] = upload_df['amount'].str.replace(',', '.', regex=False).astype(float).round(decimals=2)
                    upload_df["date"] =  pd.to_datetime(upload_df["date_str"], format="%d.%m.%Y").dt.date
                    upload_df.drop(columns='date_str',inplace=True, errors='ignore')
                    upload_df.drop(columns="location_internal_name", inplace=True)
                    current_time = datetime.datetime.now(pytz.timezone(st.secrets['TIMEZONE']))
                    upload_df['upload_time'] = current_time
            elif country == "EE" :
                upload_df = df.copy().reset_index(drop=True)

                upload_df['unit'] = upload_df['product_name'].map(dict(zip(product_master_data['Display Name/code'],product_master_data['Sale Units'])))
                upload_df['product_internal_id'] = upload_df['product_name'].map(dict(zip(product_master_data['Display Name/code'],product_master_data['Internal ID PROD'])))
                upload_df['product_catagory'] = upload_df['product_name'].map(dict(zip(product_master_data['Display Name/code'],product_master_data['Item Category'])))
                upload_df['location_internal_id'] = upload_df['store_name'].map(dict(zip(location_master_data_name2id['Ketjuyksikkö (SOK)'],location_master_data_name2id['Internal ID'])))
                upload_df.dropna(inplace=True)
                upload_df["date"] =  pd.to_datetime(upload_df["date"]).dt.date

                drop_rocca_delivery = upload_df.loc[(upload_df['store_name']=='PRISMA ROCCA AL MARE')&(upload_df['date']<pd.to_datetime('2022-09-26').date())].index
                drop_siku_delivery = upload_df.loc[(upload_df['store_name']=='PRISMA SIKUPILLI')&(upload_df['date']<pd.to_datetime('2022-12-08').date())].index
                drop_other_delivery = upload_df.loc[(upload_df['store_name']=='PRISMA TISKRE')|(upload_df['store_name']=='PRISMA VANALINN')|(upload_df['store_name']=='PRISMA ROO')].index

                upload_df.drop(drop_rocca_delivery , inplace=True)
                upload_df.drop(drop_siku_delivery , inplace=True)
                upload_df.drop(drop_other_delivery , inplace=True)




                
                upload_df['quantity'] = upload_df['quantity'].astype(str)
                upload_df['_amount'] = upload_df['_amount'].astype(str)
                upload_df['location_internal_id'] = upload_df['location_internal_id'].astype(int)
                upload_df['product_internal_id'] = upload_df['product_internal_id'].astype(int)
                upload_df['quantity'] = upload_df['quantity'].str.replace(',', '.', regex=False).astype(float).round(decimals=2)
                upload_df['_amount'] = upload_df['_amount'].str.replace(',', '.', regex=False).astype(float).round(decimals=2)
                upload_df['amount'] = upload_df['_amount']*0.85
                def generate_invoice_text(upload_df):
                    invoice_texts = []
                    # First group by store and month/year to handle cross-month data
                    upload_df['month'] = pd.DatetimeIndex(upload_df['date']).month
                    upload_df['year'] = pd.DatetimeIndex(upload_df['date']).year
                    grouped = upload_df.groupby(['store_name', 'year', 'month'])

                    for (store_name, year, month), group in grouped:
                        # Get the date range for the current store and month
                        start_date = group['date'].min()
                        end_date = group['date'].max()
                        total_amount = str((group['_amount']).sum().round(2)).replace('.', ',')
                        total_amount_after_commission = str(group['amount'].sum().round(2)).replace('.', ',')
                        invoice_text = f"Sushibar {start_date.day}.-{end_date.day}.{month}.{year} {store_name} {total_amount}*85%={total_amount_after_commission}"
                        invoice_texts.append(invoice_text)
                    invoice_texts = sorted(invoice_texts)

                    return invoice_texts
                # Generate the invoice text for the current upload_df
                invoice_texts = generate_invoice_text(upload_df)
                for invoice_text in invoice_texts:
                    st.write(invoice_text)


                upload_df.drop(columns='_amount',inplace=True, errors='ignore')
                upload_df.drop(columns='_amount_vat',inplace=True, errors='ignore')
                upload_df.drop(columns='product_name',inplace=True, errors='ignore')
                upload_df.drop(columns='month',inplace=True, errors='ignore')
                upload_df.drop(columns='year',inplace=True, errors='ignore')
                current_time = datetime.datetime.now(pytz.timezone(st.secrets['TIMEZONE']))
                upload_df['upload_time'] = current_time

                
                

            elif country == "NO" :
                upload_df = df.copy()
                upload_df.dropna(how='all', inplace=True, axis=0)
                upload_df.dropna(how='all', inplace=True, axis=1)
                upload_df.columns = ['a', 'date', 'b','store_name','c','ean', 'd','e','quantity','_amount','f','g','h','i']
                upload_df = upload_df[['date', 'store_name','ean', 'quantity','_amount']]
                upload_df = upload_df[upload_df['ean'].astype(str).str.isdigit()]
                upload_df['ean'] = upload_df['ean'].astype(int)
                upload_df['unit'] = upload_df['ean'].map(dict(zip(product_master_data['EAN'],product_master_data['Sale Units'])))
                upload_df['product_internal_id'] = upload_df['ean'].map(dict(zip(product_master_data['EAN'],product_master_data['Internal ID PROD'])))
                upload_df['product_catagory'] = upload_df['ean'].map(dict(zip(product_master_data['EAN'],product_master_data['Item Category'])))
                upload_df['location_internal_id'] = 85

                upload_df['amount'] = (upload_df['_amount']/10)*0.8
                upload_df['quantity'] = (upload_df['quantity'])
                
                upload_df.drop(columns="_amount", inplace=True)
                upload_df.drop(columns="ean", inplace=True)
                upload_df.dropna(inplace=True)
                try:
                    upload_df['date'] = pd.to_datetime(upload_df["date"]).dt.date
                    upload_df['amount'] = upload_df['amount'].astype(float)
                    upload_df['quantity'] = upload_df['quantity'].astype(float)
                    upload_df['product_internal_id'] = upload_df['product_internal_id'].astype(int)
                except:
                    pass

                current_time = datetime.datetime.now(pytz.timezone(st.secrets['TIMEZONE']))
                upload_df['upload_time'] = current_time

        elif table_name == "financial_data":
            if country == "FI" and month is not None and year is not None:
                upload_df = df.copy()
                upload_df.columns = upload_df.columns.str.strip()
                upload_df['Financial Row'] = upload_df['Financial Row'].replace('  ', np.nan)
                upload_df = upload_df.dropna()
                upload_df[['account_id', 'account_desc']] = upload_df['Financial Row'].str.split(' - ', expand=True)
                upload_df['account_id'] = pd.to_numeric(upload_df['account_id'], errors='coerce')
                upload_df = upload_df.dropna().reset_index()
                upload_df['account_id'] = upload_df['account_id'].astype(int)
                upload_df[upload_df.columns[:-1]] = upload_df[upload_df.columns[:-1]].replace('[\€]', '', regex=True)
                upload_df = upload_df.replace(' ', '', regex=True).replace(',', '.', regex=True)
                upload_df = upload_df.apply(pd.to_numeric, errors='ignore')
                upload_df = pd.melt(upload_df, id_vars=['account_id'], var_name='location_internal_name', value_name='amount')
                upload_df['amount'] = pd.to_numeric(upload_df['amount'], errors='coerce')
                upload_df['amount'] = upload_df['amount'].round(decimals=2)
                upload_df = upload_df.loc[(upload_df!=0).all(axis=1)]
                upload_df['year'] = year
                upload_df['month'] = month
                upload_df['country'] = country
                upload_df['account_id'] = upload_df["country"] +"-"+ upload_df['account_id'].astype(str)
                location_master_data_copy = location_master_data[['Location (NS)','Internal ID']].copy().dropna()
                
                # Filter rows where 'location_internal_name' matches the pattern "L[1-3 digits] ..."
                upload_df = upload_df[upload_df['location_internal_name'].str.match(r'^L\d{1,3}\s.+')]

                # Extract the numeric ID and store in 'location_id'
                upload_df['location_id'] = upload_df['location_internal_name'].str.extract(r'^L(\d{1,3})')

                # Convert 'location_id' to integer
                upload_df['location_id'] = upload_df['location_id'].astype(int)
                # st.write(upload_df)
                # upload_df['location_id'] = upload_df['location_internal_name'].map(dict(zip(location_master_data_copy['Location (NS)'],location_master_data_copy['Internal ID'])))
                # upload_df = upload_df.loc[~((upload_df['location_id'].isna()) & (upload_df['location_internal_name'] != '- No Location -'))]
                upload_df.drop(columns=['location_internal_name','country'], inplace=True, errors='ignore')
            elif country == "EE":
                upload_df = df.copy()
                upload_df['location_id'] = st.session_state['ee_month_up_int_id']
                upload_df = upload_df.fillna(0)
                upload_df['account_id'] = country +"-"+ upload_df['Account code'].astype(str)
                upload_df.drop(columns=['Description','Account name','Account code'], inplace=True, errors='ignore')
                upload_df = upload_df.melt(id_vars=['location_id','account_id'], var_name='date_str', value_name='amount')
                upload_df['month']=pd.to_datetime(upload_df["date_str"], format="%d.%m.%Y").dt.month
                upload_df['year']=pd.to_datetime(upload_df["date_str"], format="%d.%m.%Y").dt.year
                upload_df.drop(columns=['date_str'], inplace=True, errors='ignore')
                upload_df = upload_df.loc[upload_df['amount']!=0]
                upload_df['amount'] = upload_df['amount']
            elif country == "NO":
                upload_df = df.copy()
                upload_df['account_id'] = upload_df['Statement of income'].str[:4]
                upload_df['account_id'] = pd.to_numeric(upload_df['account_id'], errors='coerce')
                upload_df = upload_df.dropna(subset=['account_id'])
                upload_df['amount'] = upload_df['Unnamed: 1']
                upload_df = upload_df[['account_id','amount']]
                upload_df['account_id'] = upload_df['account_id'].astype(int)
                upload_df.dropna(inplace=True)
                upload_df['amount'] = upload_df['amount']
                upload_df['account_id'] = country+ "-" + upload_df['account_id'].astype(str)
                upload_df['year'] = year
                upload_df['month'] = month
                upload_df['location_id'] = st.session_state['no_month_up_int_id']
                upload_df = upload_df.loc[upload_df['amount']!=0]
        elif table_name == "workshift_data":
                upload_df = df[['Date', 'Employee number', 'Occupational title', 'Workplace', 'Duration', 'Working hour type']]
                upload_df.rename(columns={
                    'Date': 'date_str',
                    'Employee number': 'employee_id',
                    'Occupational title': 'job_title',
                    'Duration': 'hour',
                    'Workplace': 'location_internal_name',
                    'Working hour type': 'hour_type',
                    }, inplace=True)
                upload_df['hour'] = upload_df['hour'].str.replace(',', '.', regex=False).astype(float).round(decimals=2)
                upload_df = upload_df[upload_df['hour'] != 0]
                upload_df['job_title'].replace(['Assistant Chef','Kokki','Kokkiapulainen','kokkiapulainen','Courier','Waiter','Warehouse assistant and chef'],'Chef', inplace=True)
                upload_df['hour_type'].replace(['Illness of child'],'Illness', inplace=True)
                maraplan_location_master_data = get_master_data('MaraplanData')[['maraplan_location_name', 'location_internal_id']].dropna().drop_duplicates()
                upload_df['location_internal_id'] = upload_df['location_internal_name'].map(dict(zip(maraplan_location_master_data['maraplan_location_name'],maraplan_location_master_data['location_internal_id'])))
                upload_df = upload_df.dropna()
                upload_df['location_internal_id'] = upload_df['location_internal_id'].astype(int)
                upload_df = upload_df.loc[upload_df['hour_type'].isin(['Normal','Training','Illness'])]
                upload_df["date"] =  pd.to_datetime(upload_df["date_str"], format="%d.%m.%Y").dt.date
                upload_df.drop(columns='date_str',inplace=True,errors='ignore')
                upload_df.drop(columns="location_internal_name", inplace=True)
                current_time = datetime.datetime.now(pytz.timezone(st.secrets['TIMEZONE']))
                upload_df['upload_time'] = current_time
        elif table_name == "purchase_data":
                upload_df = df[['Voucher date', 'Person', 'Supplier', 'Product Group','Net amount', 'Count', 'Unit']]
                
                upload_df.rename(columns={
                    'Voucher date': 'date_str',
                    'Person': 'bw_approver',
                    'Supplier': 'vendor',
                    'Product Group': 'product_category',
                    'Net amount': 'amount',
                    'Count': 'quantity',
                    'Unit': 'unit',
                    }, inplace=True)
                try:
                    upload_df['quantity'] = upload_df['quantity'].astype(str)
                    upload_df['amount'] = upload_df['amount'].str.replace(' ', '')
                    upload_df['quantity'] = upload_df['quantity'].str.replace(' ', '')
                    upload_df['amount'] = upload_df['amount'].str.replace(',', '.', regex=False).astype(float).round(decimals=2)
                    upload_df['quantity'] = upload_df['quantity'].str.replace(',', '.', regex=False).astype(float).round(decimals=2)
                    upload_df['unit'] = upload_df['unit'].str.lower()
                    upload_df['product_category'] = upload_df['product_category'].str.lower()
                except:
                    pass

                location_bw_name_master_data = LOCATION_MASTER[['bw_approver', 'Internal ID']].dropna().drop_duplicates()

                upload_df['location_internal_id'] = upload_df['bw_approver'].map(dict(zip(location_bw_name_master_data['bw_approver'],location_bw_name_master_data['Internal ID'])))
                upload_df = upload_df.dropna()
                upload_df['location_internal_id'] = upload_df['location_internal_id'].astype(int)
                upload_df["date"] =  pd.to_datetime(upload_df["date_str"], format="%d.%m.%Y").dt.date
                upload_df.drop(columns='date_str',inplace=True,errors='ignore')
                upload_df.drop(columns="bw_approver", inplace=True)

                upload_df['product_category'] = upload_df['product_category'].str.lower()
                # Change product_category containing "fish" to "salmon"
                upload_df.loc[upload_df['product_category'].str.contains('fish'), 'product_category'] = 'salmon'
                # Updating date if product_category is "salmon"
                upload_df.loc[upload_df['product_category'] == 'salmon', 'date'] += datetime.timedelta(days=7)

                current_time = datetime.datetime.now(pytz.timezone(st.secrets['TIMEZONE']))
                upload_df['upload_time'] = current_time
        elif table_name == "invoice_data":
            if country=="FI":
                upload_df = df.copy()
                upload_df['account_id'] = "FI-"+upload_df['Account'].str[:4]
                upload_df['amount'] = upload_df['Amount (Net)'].str.replace("€","")
                upload_df['amount'] = upload_df['amount'].str.replace("\s+","",regex=True)
                upload_df['amount'] = upload_df['amount'].str.replace(",",".")
                upload_df['amount'] = upload_df['amount'].str.replace("'","")
                upload_df['amount'].loc[upload_df['amount'].str.contains('kr')] = upload_df['amount'].loc[upload_df['amount'].str.contains('kr')].str.replace('kr', '').astype(float)/10
                upload_df['amount'] = upload_df['amount'].astype(float).round(2)
                upload_df['date'] = pd.to_datetime(upload_df['Date'],format='%d.%m.%Y')
                upload_df['vendor'] = upload_df['Vendor']
                upload_df['inv_num'] = upload_df['Document Number/ID']
                
                # upload_df['location_internal_id'] = upload_df['Location'].map(dict(zip(location_master_data['Location (NS)'],location_master_data['Internal ID']))).astype(int)
                upload_df['location_internal_id'] = upload_df['Location'].str.extract('(\d+)').astype(int)
                upload_df['account_type'] = upload_df['account_id'].map(dict(zip(account_master_data['account_id'],account_master_data['account_type'].str.capitalize())))
                upload_df['vendor_type'] =  upload_df['vendor'].map(vendor_type)
                # upload_df =  upload_df.loc[upload_df['account_type']=="Material"]
                upload_df['vendor'] = upload_df['vendor'].fillna("Not sure")
                upload_df['vendor_type'] = upload_df['vendor_type'].fillna("Other")
                upload_df.drop(columns=['Date','Vendor','Document Number/ID','Amount (Net)','Type','Location','Account'], inplace=True)
            elif country =="EE":
                location = {
                    'Sushibar Kristiine':103,
                    'Sushibar Lasnamäe':104,
                    'Sushibar Mustamäe':105,
                    'Sushibar Rocca al Mare':309,
                    'Sushibar Sikupilli':310,
                }
                vendor = {
                    'GC': ['FORTIMER OÜ', 'Fruit Xpress OÜ', 'Global Marine Supply OÜ', 'MISAFOODS OÜ', 'OY Golden Crop AB', 'Vegelog OÜ'],
                    'Salmon': ['Heimon Kala OÜ', 'On-Trade OÜ','Testingpro OÜ','Up Point OÜ', 'Selectfood OÜ']
                }
                # Create a reverse mapping of the vendor dictionary
                reverse_vendor = {vendor_type: key for key, values in vendor.items() for vendor_type in values}


                upload_df = df.copy()
                upload_df = upload_df[['Vendor', 'Doc. No.', 'Tr. Date', 'Invoice Total ', 'Department']]
                upload_df = upload_df.rename(columns={'Vendor':'vendor', 'Doc. No.':'inv_num','Tr. Date':'date','Invoice Total ':'amount','Department':'sushibar'})
                upload_df.loc[upload_df['vendor'] != 'OY Golden Crop AB', 'amount'] /= 1.2
                upload_df['sushibar'] = upload_df['sushibar'].fillna('Sushibar Kristiine')
                upload_df['date'] = pd.to_datetime(upload_df['date'],format='%d.%m.%Y')
                upload_df['location_internal_id'] = upload_df['sushibar'].map(location).astype(int)

                # Map the values in 'Vendor' column to the vendor type using the reverse mapping
                upload_df['vendor_type'] = upload_df['vendor'].map(reverse_vendor)
                upload_df['vendor_type'] = upload_df['vendor_type'].fillna('Other')
                # Create a function to check if vendor exists in the dictionary
                def check_vendor(vendor_name):
                    for key, values in vendor.items():
                        if vendor_name in values:
                            return 'Material'
                    return 'Other cost'

                # Add a new column based on vendor existence
                upload_df['account_type'] = upload_df['vendor'].apply(check_vendor)
                account_tyoe_id = {"Material":"EE-4002","Other cost":"EE-4395"}
                upload_df['account_id'] = upload_df['account_type'].map(account_tyoe_id)
                upload_df.drop(columns=['sushibar'], inplace=True)

            elif country =="NO":
                pass



    except Exception as e:
        st.error(f'Something wrong with uploaded file: {e}', icon="🚨")
        if st.secrets['EMAIL_ALERT']:
            send_email(st.secrets["OFFICE_USN"], f'Error message when processing file "{filename}" for {table_name.replace("_", " ")}', e)
        st.stop()
    return upload_df


# Init database connection
con = init_connection()


st.markdown("# Select table you need to modify?")
# This will print all the avaliable table names
table_options = ['< Please select one table >']+db.inspect(con).get_table_names()
# table_options = list(table_options).remove('delivery')
table_options.remove('delivery')
db_option_up = st.selectbox("Available database table options:",table_options, key='db_option_up')
display_report = False
month_list = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
month = None
year = None
type = None
sep = None
country = None
help = None

if db_option_up != '< Please select one table >':
    allow_multiple = False
    if db_option_up == 'month_data' or db_option_up == 'financial_data':
        country = st.radio("Which country does the data belong to?",('FI','EE','NO'), horizontal=True)
        if country == "FI":
            col1, col2 = st.columns([1, 3])
            year = col1.number_input('Year', value=datetime.datetime.now().year, step=1, key='year_up')
            month_selected = col2.select_slider('Month', options=month_list, key='month_up')
            month = month_list.index(month_selected) + 1
            type, sep, help, allow_multiple = 'csv', ',', 'Download from NetSuite each month.', False
        elif country == "EE":
            location = {
                'Kristiine': 103,
                'Lasnamäe': 104,
                'Mustamäe': 105,
                'Rocca al Mare': 309,
                'Sikupilli': 310,
                'Head Office': 516,
            }
            ee_store_selected = st.select_slider('Select which store:', options=location.keys(), key='ee_month_up')
            st.session_state['ee_month_up_int_id'] =location[ee_store_selected]
            type, sep, help, allow_multiple = 'xlsx', None, 'Download from Merit each month.', False
        elif country == "NO":
            location = {
                'Mega Metro': 85,
            }
            col1, col2 = st.columns([1, 3])
            year = col1.number_input('Year', value=datetime.datetime.now().year, step=1, key='year_up_no')
            month_selected = col2.select_slider('Month', options=month_list, key='month_up_no')
            month = month_list.index(month_selected) + 1
            # no_store_selected = st.select_slider('Select which store:', options=location.keys(), key='no_month_up')
            st.session_state['no_month_up_int_id'] =location['Mega Metro']
            type, sep, help, allow_multiple = 'xlsx', None, 'Download from Cozone each month.', False

    elif db_option_up == 'sales_data':
        country = st.radio("Which country does the data belong to?",('FI','EE','NO'), horizontal=True)
        if country == "NO":
            type, sep, help, allow_multiple = 'xlsx', None, "File you upload to NetSuite or received raw weekly report.", True
        elif country == "EE":
            type, sep, help, allow_multiple = 'xlsx', None, "File you upload to NetSuite or received raw weekly report.", True
        else:
            type, sep, help, allow_multiple = 'csv', ';', "File you upload to NetSuite or received raw weekly report.", False
    elif db_option_up == 'workshift_data':
        type, sep, hel, allow_multiple = 'csv', ';', 'Download from Maraplan.', False
    elif db_option_up == 'purchase_data':
        type, sep, help, allow_multiple = 'txt', '\t', 'Download from Basware.', False
    elif db_option_up == 'invoice_data':
        country = st.radio("Which country does the data belong to?",('FI','EE','NO'), horizontal=True)
        if country == "FI":
            type, sep, help, allow_multiple = 'csv', ';', 'Download from Netsuite Suite Analytics.', False
        elif country == "EE":
            type, sep, help, allow_multiple = 'xlsx', ';', 'Download from Netsuite Suite Analytics.', False
    df, filename = file_uploader(db_option_up, type=type, country=country, sep=sep, help=help, allow_multiple=allow_multiple)
    if df is not None and filename not in st.session_state['upload_history'].keys():
        upload_df = process_data(df=df, filename=filename, table_name=db_option_up, country=country, month=month, year=year)
        if upload_df is not None:
            st.dataframe(upload_df, use_container_width=True)
        info_placeholder = st.empty()
        upload_btn = st.button("Upload to Database", key=f"{db_option_up}_upload_button")
        if db_option_up == 'financial_data':
            update_btn = st.button("Update records", key=f"{db_option_up}_update_button")


            if update_btn and upload_df is not None:
                if filename not in st.session_state['upload_history'].keys():
                    try:
                        info_placeholder.info(f'Start updateing {upload_df.shape[0]} rows of {db_option_up.replace("_"," ")}...',icon="ℹ️")
                        custom_query(f"""
                            SET SQL_SAFE_UPDATES = 0
                            DELETE FROM financial_data
                            WHERE month={month} AND year={year} AND account_id LIKE '{country}-%'
                            SET SQL_SAFE_UPDATES = 1;
                            """)
                        upload_df.to_sql(name=db_option_up, con=con, schema="data", index=False, if_exists='append', chunksize=1000, method='multi')
                        st.session_state['upload_history'][filename] = 'uploaded'
                    except Exception as e:
                        info_placeholder.error(f'Something is wrong when updating data to the database.', icon="🚨")
                        st.write(e)
                        if st.secrets['EMAIL_ALERT']:
                            send_email(st.secrets["OFFICE_USN"], f'Error message when uploading {db_option_up.replace("_", " ")}', e)
                        st.stop()
                    finally:
                        time.sleep(5)
                        # Clear all those elements:
                        info_placeholder.empty()
                else:
                    st.error(f"You have already updated this data, please don't upload again!", icon="🚨")
                    st.stop()


        if upload_btn and upload_df is not None:
            if filename not in st.session_state['upload_history'].keys():
                try:
                    info_placeholder.info(f'Start uploading {upload_df.shape[0]} rows of {db_option_up.replace("_"," ")}...',icon="ℹ️")
                    # start_time = time.time()
                    # old_row_number = get_row_number(engine=con, table_name=db_option_up)
                    upload_df.to_sql(name=db_option_up, con=con, schema="data", index=False, if_exists='append', chunksize=1000, method='multi')
                    # new_row_number = get_row_number(engine=con, table_name=db_option_up)
                    # end_time = time.time()
                    st.session_state['upload_history'][filename] = 'uploaded'
                    # Replace the text with a success msg:
                    # if new_row_number - old_row_number != 0:
                    #     info_placeholder.success(f'{new_row_number - old_row_number} of rows of {db_option_up.replace("_"," ")} has been added to the database in {round(end_time - start_time,2)} seconds.',icon="✅")
                except Exception as e:
                    info_placeholder.error(f'Something is wrong when uploading data to the database.', icon="🚨")
                    st.write(e)
                    if st.secrets['EMAIL_ALERT']:
                        send_email(st.secrets["OFFICE_USN"], f'Error message when uploading {db_option_up.replace("_", " ")}', e)
                    st.stop()
                finally:
                    time.sleep(5)
                    # Clear all those elements:
                    info_placeholder.empty()
            else:
                st.error(f"You have already uploaded this data, please don't upload again!", icon="🚨")
                st.stop()