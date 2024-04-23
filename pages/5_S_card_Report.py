import streamlit as st
st.set_page_config(
    layout='wide',
    initial_sidebar_state='auto')
import time
import datetime
from utils.get_master_data import location_name2id, LOCATION_MASTER
from utils.db_query import custom_query
import utils.custom_theme as ct
from st_aggrid.grid_options_builder import GridOptionsBuilder
from st_aggrid import AgGrid, ColumnsAutoSizeMode
from st_aggrid.grid_options_builder import GridOptionsBuilder
import plotly.express as px
from utils.utilities import user_authantication

COLOR_5 = ct.color_gradient(st.secrets['START_COLOR'], st.secrets['END_COLOR'], n=5, alpha=st.secrets['OPACITY'])

location_master_data = LOCATION_MASTER.copy()
unique_store_list = location_master_data['Location (NS)'].loc[location_master_data['Location (NS)'].str.contains('Sushibar', na=False)].unique().tolist()
unique_store_id_list = location_master_data['Internal ID'].loc[location_master_data['Location (NS)'].str.contains('Sushibar', na=False)].unique().tolist()
unique_manager_list = location_master_data['store_manager'].dropna().unique().tolist()
unique_op_list = location_master_data['OP'].dropna().unique().tolist()

# Init session_state
if 'store_name_selected' not in st.session_state:
    st.session_state['store_name_selected'] = None
if 'store_id_selected' not in st.session_state:
    st.session_state['store_id_selected'] = None


def update_location(type):
    if type == "store":
        st.session_state['store_name_selected'] = st.session_state['stores_selected']
    elif type == 'manager':
        st.session_state['store_name_selected'] = location_master_data['Location (NS)'].loc[location_master_data['store_manager'].isin(st.session_state['managers_selected'])].tolist()
    elif type == 'op':
        st.session_state['store_name_selected'] = location_master_data['Location (NS)'].loc[location_master_data['OP'].isin(st.session_state['op_selected'])].tolist()

    elif type == 'all' and st.session_state['view_all']:
        st.session_state['store_name_selected'] = unique_store_list
    else:
        st.session_state['store_name_selected'] = None
    st.session_state['store_id_selected'] = location_name2id(st.session_state['store_name_selected'])
    st.session_state['location_update_time_stamp'] = time.time()

name, authentication_status, username, authenticator = user_authantication()
if authentication_status:
    st.sidebar.write(f"Welcome *{name}*!")
    authenticator.logout('Logout', 'sidebar')

with st.sidebar:
    st.write("Please select stores of your interests")
    view_all = st.checkbox(label="view all stores", value=False, key="view_all", on_change=update_location, kwargs=dict(type='all'))
    filtering = st.checkbox("filter data", value=True,key="filter",help="Select if you only want to see the unauthorized purchase.")

    if not view_all:
        store, manager, op = st.tabs(["Store", "Manager", "OP Member"])
        stores_selected = store.multiselect(
            label="by store name",
            options=unique_store_list,
            key='stores_selected',
            help="Select stores of your interest",
            on_change=update_location,
            kwargs=dict(type='store'))

        managers_selected = manager.multiselect(
            label="by store manager",
            options=unique_manager_list,
            key='managers_selected',
            help="Select by manager name",
            on_change=update_location,
            kwargs=dict(type='manager'))

        op_selected = op.multiselect(
            label="by OP team member", 
            options=unique_op_list, 
            key='op_selected', 
            help="Select by operation team member name", 
            on_change=update_location, 
            kwargs=dict(type='op'))

    start, end = st.columns(2)
    min_date = custom_query("SELECT MIN(purchase_date) FROM data.s_card_purchase_data;").iloc[0, 0]
    
    max_date = custom_query("SELECT MAX(purchase_date) FROM data.s_card_purchase_data;").iloc[0, 0]
    start_date = start.date_input(
        "select start date",
        value=datetime.datetime(2023, 4, 1),
        min_value=min_date,
        max_value=max_date,
        key='start_date',
        on_change=None)

    end_date = end.date_input("select end date", 
    value=max_date,
    min_value=min_date,
    max_value=max_date,
    key='end_date', 
    on_change=None)


st.write("# S-Business Card Purchase History")

graph, data = st.tabs(['Chart','Data'])

if st.session_state['store_id_selected'] is not None:
    if len(st.session_state['store_id_selected'])>0:
        ignore_list = [44,56,36,29,67,76]
        query =f"""
        SELECT location_internal_id,s_card_purchase_data.ean,product_name_en,for_sushibar,amount,purchase_date FROM s_card_purchase_data INNER JOIN s_card_master_data ON s_card_purchase_data.ean=s_card_master_data.ean
        WHERE location_internal_id in ({", ".join([str(int(i)) for i in st.session_state['store_id_selected']])})
        AND purchase_date BETWEEN '{start_date}' AND '{end_date}';
        """    
        purchase_df = custom_query(query)
        purchase_df['for_sushibar'] = purchase_df['for_sushibar'].replace({1: True, 0: False})
        purchase_df = purchase_df.loc[(purchase_df['for_sushibar']!=filtering)&(~purchase_df['location_internal_id'].isin(ignore_list))]
        location_short_name_mapping = location_master_data[['Internal ID','short_name']].drop_duplicates()
        location_short_name_mapping = location_short_name_mapping.dropna()
        purchase_df['store_name'] = purchase_df['location_internal_id'].map(dict(zip(location_short_name_mapping['Internal ID'],location_short_name_mapping['short_name'])))
        purchase_df.drop(['for_sushibar','location_internal_id'],inplace=True,axis=1)

        with data:
            gb = GridOptionsBuilder.from_dataframe(purchase_df)
            gb.configure_pagination(paginationPageSize=10)
            gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
            gridOptions = gb.build()
            AgGrid(
                purchase_df,
                gridOptions=gridOptions,
                columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
                enable_enterprise_modules=True,
                conversion_errors='coerce',
                allow_unsafe_jscode=True,
                custom_css=ct.custom_css,
            )
        with graph:
            fig = px.scatter(purchase_df, x="purchase_date", y="amount", color='store_name',hover_name="store_name", hover_data=['ean'])
            fig.update_traces(mode="markers")
            fig.update_layout(
                height=700,
                title=f"Purchase Record",
                xaxis_title="Purchase Time",
                yaxis_title="Amount (with VAT)",
                legend_title_text='Store Name',
            )
            st.plotly_chart(fig, use_container_width=True)
