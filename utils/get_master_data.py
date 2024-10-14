import pandas as pd
import streamlit as st
from shareplum import Site
from shareplum import Office365
from shareplum.site import Version
from io import BytesIO

@st.cache_data(ttl=600, show_spinner=False)
def get_master_data(sheet_name):
    # sharepoint authantification
    authcookie = Office365(st.secrets["OFFICE_SITE"], username=st.secrets["OFFICE_USN"], password=st.secrets["OFFICE_PSW"]).GetCookies()
    site = Site(st.secrets["SHAREPOINT_SITE"], version=Version.v365, authcookie=authcookie)      # go to the finance site
    folder = site.Folder(st.secrets["MASTER_DATA_LOCATION"])
    master_data = folder.get_file('Master Data.xlsx')
    master_data_df = pd.read_excel(BytesIO(master_data), sheet_name=sheet_name)
    if sheet_name=="SalesItem":
        master_data_df = master_data_df.dropna(subset=['EAN'])
        master_data_df['EAN'] = master_data_df['EAN'].astype(int)
    return master_data_df

LOCATION_MASTER = get_master_data("Location")
location_master_data = LOCATION_MASTER[['Location (NS)', 'Internal ID']].dropna().drop_duplicates()


def location_id2name(ids):
    """
    input: int, list of int of internal location id
    output: str, list of str of internal location name
    """
    location_dict = dict(zip(location_master_data['Internal ID'],location_master_data['Location (NS)']))
    if isinstance(ids, str):
        ids = int(ids)
        return location_dict[ids]
    elif isinstance(ids, list):
        return [location_dict[i] for i in ids]

def location_name2id(names):
    """
    input: str, list of str of internal location name
    ouput: int, list of internal location id
    """

    location_dict = dict(zip(location_master_data['Location (NS)'],location_master_data['Internal ID']))
    if isinstance(names, str):
        return location_dict[names]
    elif isinstance(names, list):
        return [location_dict[i] for i in names]

