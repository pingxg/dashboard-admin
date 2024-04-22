import sqlalchemy as db
from sqlalchemy import text
from sqlalchemy import create_engine, select, func, MetaData

import streamlit as st
import hashlib
import pandas as pd
from utils.get_master_data import get_master_data

product_master_data = get_master_data('SalesItem')
account_master_data = get_master_data('AccountID')

# Initialize connection and only run once using streamlit caching function
@st.cache_resource(ttl=600, show_spinner=False)
def init_connection():
    return db.create_engine(f'mysql+mysqlconnector://{st.secrets["DB_USER"]}:{st.secrets["DB_PSW"]}@{st.secrets["DB_HOST"]}:{st.secrets["DB_PORT"]}/{st.secrets["DB_NAME"]}')

# def get_row_number(engine, table_name):
#     meta_data = db.MetaData(bind=engine)
#     db.MetaData.reflect(meta_data)
#     # GET THE TABLE FROM THE METADATA OBJECT
#     table = meta_data.tables[table_name]
#     # SELECT COUNT(*) FROM Actor
#     result = db.select([db.func.count()]).select_from(table).scalar()
#     return result

def get_row_number(engine, table_name):
    # Create a MetaData instance
    meta_data = MetaData()
    
    # Reflect the tables from the database
    meta_data.reflect(bind=engine)
    
    # Get the table from the metadata object
    table = meta_data.tables[table_name]
    
    # Construct a select query to count the rows in the specified table
    # Note: The syntax can vary slightly between SQLAlchemy versions; adjust as needed
    query = select(db.func.count()).select_from(table)
    
    # Execute the query and fetch the scalar result (the row count)
    with engine.connect() as connection:
        result = connection.execute(query).scalar()
    
    return result


def run_query(engine, query):
    with engine.connect() as cur:
        cur.execute(query)


@st.cache_resource(ttl=600, show_spinner=False)
def querying_data(table_name, ids, start, end):
    conn = init_connection().connect()

    if table_name == "month_data":

        query = text(f"""
        SELECT *\n
        FROM (\n
        SELECT *,\n
            DATE(CONCAT(year, '-', month, '-01')) AS date_column\n
        FROM data.{table_name}\n
        ) AS t\n
        WHERE date_column >= DATE("{int(start.strftime('%Y'))}-{int(start.strftime('%m'))}-01")\n
        AND date_column <= DATE("{int(end.strftime('%Y'))}-{int(end.strftime('%m'))}-01")\n
        AND location_internal_id in ({", ".join([str(i) for i in ids])});
        """)

        df = pd.read_sql(query, con = conn)
        df['quarter'] = (df['month']-1)//3 + 1
        df['actual'] = df['account_id'].map(dict(zip(account_master_data["account_id"],account_master_data["actual"])))
        df['adj'] = df['account_id'].map(dict(zip(account_master_data["account_id"],account_master_data["adj"])))
        df['adj_coef'] = df['account_id'].map(dict(zip(account_master_data["account_id"],account_master_data["adj_coef"])))
        df['account_name'] = df['account_id'].map(dict(zip(account_master_data["account_id"],account_master_data["account_name"])))

    elif table_name == "invoice_data":
        query = text(f"""
        SELECT * FROM data.{table_name}\n
        WHERE location_internal_id in ({", ".join([str(i) for i in ids])})\n
        AND account_type = 'Material';
        """)
        df = pd.read_sql(query, con = conn, parse_dates=['date'])
        df['week'] = df['date'].dt.isocalendar().week
        df['month']= df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['year'] = df['date'].dt.year

    elif table_name == "purchase_data":

        query = text(f"""
        SELECT * FROM data.{table_name}
        WHERE location_internal_id in ({", ".join([str(i) for i in ids])})
        AND date BETWEEN '{start}' AND '{end}'
        UNION ALL
        SELECT 
        salmon_orders.id,
        salmon_orders.date,
        'Firewok Finland Oy' AS vendor,
        salmon_orders.quantity,
        'salmon' AS product_category,
        salmon_orders.price * salmon_orders.quantity AS amount,
        'kg' AS unit,
        salmon_customer.location_internal_id,
        salmon_orders.date AS upload_time
        FROM salmon_orders
        JOIN salmon_customer ON salmon_orders.customer = salmon_customer.customer
        WHERE salmon_customer.location_internal_id in ({", ".join([str(i) for i in ids])})
        AND salmon_orders.product LIKE "%Lohi%"
        AND date BETWEEN '{start}' AND '{end}';
        """)

        df = pd.read_sql(query, con = conn, parse_dates=['date'])
        df['week'] = df['date'].dt.isocalendar().week
        df['month']= df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['year'] = df['date'].dt.year


    else:
        query = text(f"""
        SELECT * FROM data.{table_name}\n
        WHERE location_internal_id in ({", ".join([str(i) for i in ids])})\n
        AND date BETWEEN '{start}' AND '{end}';"
        """)

        df = pd.read_sql(query, con = conn, parse_dates=['date'])
        df['week'] = df['date'].dt.isocalendar().week
        df['month']= df['date'].dt.month
        df['quarter'] = df['date'].dt.quarter
        df['year'] = df['date'].dt.year

    df['store_name_selected'] = df['location_internal_id'].map(dict(zip(st.session_state["store_id_selected"],[i.split(" ")[2] for i in st.session_state["store_name_selected"]])))

    if table_name == "sales_data":
        df['product_name'] = df['product_internal_id'].map(dict(zip(product_master_data['Internal ID PROD'], product_master_data['Display Name/code'])))
    # conn.close()
    return df

@st.cache_resource(ttl=600, show_spinner=False)
def custom_query(query) -> pd.DataFrame:
    conn = init_connection().connect()
    if query.strip().upper().startswith("SELECT"):
        df = pd.read_sql(text(query), con = conn)
        conn.close()
        return df
    else:
        conn.execute(text(query))
        conn.close()

def custom_query_wo_cache(query) -> pd.DataFrame:
    conn = init_connection().connect()
    if query.strip().upper().startswith("SELECT"):
        df = pd.read_sql(text(query), con = conn)
        conn.close()
        return df
    else:
        conn.execute(text(query))
        conn.close()

def add_hash_id(df, key_combination):
    df['id'] = list(map(lambda x: hashlib.sha256('|'.join([col_value for col_value in x]).encode('utf-8')).hexdigest(), df[key_combination].astype(str).values))
    return df