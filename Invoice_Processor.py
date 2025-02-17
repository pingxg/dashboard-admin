import streamlit as st
import pytz
import calendar
import datetime
import pandas as pd
import numpy as np
from shareplum import Site
from shareplum import Office365
from shareplum.site import Version
from utils.send_email import send_email
from utils.get_master_data import get_master_data
from utils.db_query import init_connection
from utils.utilities import auth_widgets
from sqlalchemy import text
from io import BytesIO


st.set_page_config(layout="wide")

auth_widgets()

def add_position(df, col_name):
    """
    input: any dataframe
    output: dataframe with a column "Position", cumulative counting number starting from 0, and reset if the col_name change.
    """
    df["Position"] = df.groupby(col_name).cumcount()
    return df

def get_start_and_end_date_from_calendar_week(year, calendar_week):
    """
    input: year number, int; iso week number
    output: start date and end date of the week, data type: datetime
    """
    monday = datetime.datetime.strptime(
        f"{year}/{calendar_week}/1", "%Y/%W/%w"
    ).date()
    return monday, monday + datetime.timedelta(days=6.9)


# Start writing title
st.markdown("# Invoice CSV template 🎈")
st.markdown("### Upload raw sales data")

sok_data, delivery_data = st.tabs(["On-Site sales", "Delivery sales"])

with sok_data:

    # Input field for NS external ID
    last_externalID_ns = int(
        st.number_input(
            "Insert last Internal ID in NetSuite.", step=1, key="on_site_external_id"
        )
    )
    # Create file uploader
    sok_data = st.file_uploader(
        "Upload SOK sales report",
        type="txt",
        help="Find it from SOK",
        accept_multiple_files=True,
    )

    # Start the main loop, if both file holder is NOT empty, then start the process
    if last_externalID_ns is not None and sok_data is not None:
        # sharepoint authantification
        authcookie = Office365(
            st.secrets["OFFICE_SITE"],
            username=st.secrets["OFFICE_USN"],
            password=st.secrets["OFFICE_PSW"],
        ).GetCookies()

        site = Site(
            st.secrets["SHAREPOINT_SITE"],
            version=Version.v365,
            authcookie=authcookie
        )
        folder = site.Folder(st.secrets["MASTER_DATA_LOCATION"])
        master_data = folder.get_file("Master Data.xlsx")
        master_sok = pd.read_excel(BytesIO(master_data), sheet_name="SOK")
        master_location = pd.read_excel(BytesIO(master_data), sheet_name="Location")
        master_sale_item = pd.read_excel(BytesIO(master_data), sheet_name="SalesItem")
        master_customer = pd.read_excel(BytesIO(master_data), sheet_name="Customer")
        master_sale_item = master_sale_item.dropna(subset=["EAN"])

        if isinstance(sok_data, list):
            output = pd.DataFrame()
            for file_index in range(len(sok_data)):
                # if file_index ==0:
                df = pd.read_csv(
                    sok_data[file_index], sep=";", encoding="utf-16", skiprows=[0, 1]
                ).fillna(0)
                output = pd.concat([df, output], sort=False)
            df = output.copy().reset_index(drop=True)
        else:
            df = pd.read_csv(
                sok_data, sep=";", encoding="utf-16", skiprows=[0, 1]
            ).fillna(0)
        if not df.empty:

            df = df.drop(
                ["Etiketin lisäteksti", "KP koko", "My vol (kilo, litra)", "AOK"], axis=1
            )  # delete these columns
            df.columns = [
                "Delivery Note Date",
                "Store",
                "EAN",
                "Product Name",
                "Sales Unit",
                "Tax Rate",
                "ALV14",
                "Quantity",
            ]  # rename columns according to current order

            df["ALV14"] = (
                df["ALV14"].astype(str).str.replace(" ", "")
            )  # remove all the spaces in the value
            df["ALV14"] = (
                df["ALV14"].astype(str).str.replace(",", ".").astype(float)
            )  # replace all the "," to "." in the value
            df["Quantity"] = (
                df["Quantity"].astype(str).str.replace(" ", "")
            )  # remove all the spaces in the value
            df["Quantity"] = (
                df["Quantity"].astype(str).str.replace(",", ".").astype(float)
            )  # replace all the "," to "." in the value
            df['Delivery Note Date'] = df['Delivery Note Date'].astype(str).str.replace(r"[^\d\.]", "", regex=True)
            df['Delivery Note Date'] = pd.to_datetime(df['Delivery Note Date'], format="%d.%m.%Y", errors="coerce")
            # df["Delivery Note Date"] = pd.to_datetime(
            #     df["Delivery Note Date"], format="%d.%m.%Y"
            # )
            df = df.sort_values(by="Store")

            # -----------------------------
            df["Operating department"] = df["Store"].map(
                dict(zip(master_sok["Ketjuyksikkö"], master_sok["Operating department"]))
            )
            df["Customer code and name"] = df["Store"].map(
                dict(
                    zip(
                        master_location["Ketjuyksikkö (SOK)"],
                        master_location["Customer code and name"],
                    )
                )
            )
            df["Tax code internalID"] = df["Customer code and name"].map(
                dict(
                    zip(master_customer["ID+Name"], master_customer["Tax code internalID"])
                )
            )
            df["Location (NS)"] = df["Store"].map(
                dict(
                    zip(
                        master_location["Ketjuyksikkö (SOK)"],
                        master_location["Location (NS)"],
                    )
                )
            )
            df["PO"] = df["Store"].map(
                dict(
                    zip(
                        master_location["Ketjuyksikkö (SOK)"], master_location["#PO number"]
                    )
                )
            )
            df["invoice-specific message"] = df["Store"].map(
                dict(
                    zip(
                        master_location["Ketjuyksikkö (SOK)"],
                        master_location["invoice-specific message"],
                    )
                )
            )
            df["Sales Item Internal ID"] = df["EAN"].map(
                dict(zip(master_sale_item["EAN"], master_sale_item["Internal ID PROD"]))
            )

            df["Sales Item Category"] = df["EAN"].map(
                dict(zip(master_sale_item["EAN"], master_sale_item["Item Category"]))
            )
            df["Department"] = df["EAN"].map(
                dict(zip(master_sale_item["EAN"], master_sale_item["Department"]))
            )
            df["Class"] = df["EAN"].map(
                dict(zip(master_sale_item["EAN"], master_sale_item["Class"]))
            )
            df["split_month"] = df["Customer code and name"].map(
                dict(zip(master_customer["ID+Name"], master_customer["split_month"]))
            )
            df["Commission Rate"] = df["Store"].map(
                dict(
                    zip(master_location["Ketjuyksikkö (SOK)"], master_location["commision"])
                )
            )
            df["Amount"] = (df["ALV14"] / 1.14) * df["Commission Rate"]
            df["Unit Price"] = df["Amount"] / df["Quantity"]

            # Some special situation that needs to be set seperately
            plant_by_product_list = [
                8801043157742,
                8801043150620,
                8801073113428,
                8801073113404,
                8936036020373,
                6970399920057,
                6970399920439,
                4902494008004,
                5710067001968,
                4902494090153,
            ]
            df["Department"].loc[
                (df["Store"] == "PRISMA RIIHIMÄKI")
                & (df["EAN"].isin(plant_by_product_list))
                & (df["Delivery Note Date"] < "2023-01-22")
                & (df["Delivery Note Date"] > "2022-05-01")
            ] = "Food Plant"
            df["Department"].loc[
                (df["Store"] == "PRISMA LAUNE")
                & (df["EAN"].isin(plant_by_product_list))
                & (df["Delivery Note Date"] < "2023-01-22")
                & (df["Delivery Note Date"] > "2022-05-01")
            ] = "Food Plant"
            df["Department"].loc[
                (df["Store"] == "PRISMA FORSSA")
                & (df["EAN"].isin(plant_by_product_list))
                & (df["Delivery Note Date"] < "2023-01-22")
                & (df["Delivery Note Date"] > "2022-05-01")
            ] = "Food Plant"
            df["Department"].loc[
                (df["Operating department"] == "Food Plant")
            ] = "Food Plant"

            df["Amount"].loc[
                (df["Store"] == "S-MARKET MANHATTAN")
                & (df["Sales Item Category"] == "Sushi")
            ] *= 0.9444444
            df["Amount"].loc[
                (df["Store"] == "S-MARKET NIKKILÄ")
                & (df["Delivery Note Date"] >= "2023-08-01")
            ] *= 1.088235

            df = df.drop(
                df.loc[
                    (df["Store"] == "SOKOS TAMPERE PT")
                    & (df["Delivery Note Date"] > "2022-11-06")
                ].index
            )
            df = df.drop(
                df.loc[
                    (df["Store"] == "S-MARKET MYYRMANNI")
                    & (df["Delivery Note Date"] > "2022-11-05")
                ].index
            )
            df["Location (NS)"].loc[
                (df["Store"] == "S-MARKET MÄNTSÄLÄ")
                & (df["Delivery Note Date"] > "2022-11-06")
            ] = "L102 Food Plant Espoo"
            df["Department"].loc[
                (df["Store"] == "S-MARKET MÄNTSÄLÄ")
                & (df["Delivery Note Date"] > "2022-11-06")
            ] = "Food Plant"
            df["Location (NS)"].loc[
                (df["Department"] == "Food Plant")
            ] = "L102 Food Plant Espoo"

            df["Location (NS)"].loc[
                (df["Store"] == "PRISMA PIRKKALA")
                & (df["Delivery Note Date"] >= "2023-02-01")
            ] = "L29 Sushibar Pirkkala Prisma Pirkkala"
            df["Department"].loc[
                (df["Store"] == "PRISMA PIRKKALA")
                & (df["Delivery Note Date"] >= "2023-02-01")
            ] = "Food Kiosk Sushibar"
            df["Operating department"].loc[
                (df["Store"] == "PRISMA PIRKKALA")
                & (df["Delivery Note Date"] >= "2023-02-01")
            ] = "Food Kiosk Sushibar"

            df["Location (NS)"].loc[
                (df["Store"] == "S-MARKET HANSA HERKKU")
                & (df["Delivery Note Date"] >= "2023-05-22")
            ] = "L23 Sushibar Manhattan S-Market Turku"
            df["Department"].loc[
                (df["Store"] == "S-MARKET HANSA HERKKU")
                & (df["Delivery Note Date"] >= "2023-05-22")
            ] = "Food Kiosk Sushibar"
            df["Operating department"].loc[
                (df["Store"] == "S-MARKET HANSA HERKKU")
                & (df["Delivery Note Date"] >= "2023-05-22")
            ] = "Food Kiosk Sushibar"

            df["Location (NS)"].loc[
                (df["Store"] == "PRISMA TAMPEREENTIE TURKU")
                & (df["Delivery Note Date"] >= "2024-01-25")
            ] = "L17 Sushibar Itäharju Prisma Turku"
            df["Department"].loc[
                (df["Store"] == "PRISMA TAMPEREENTIE TURKU")
                & (df["Delivery Note Date"] >= "2024-01-25")
            ] = "Food Kiosk Sushibar"
            df["Operating department"].loc[
                (df["Store"] == "PRISMA TAMPEREENTIE TURKU")
                & (df["Delivery Note Date"] >= "2024-01-25")
            ] = "Food Kiosk Sushibar"

            df["Location (NS)"].loc[
                (df["Store"] == "PRISMA MYLLY")
                & (df["Delivery Note Date"] >= "2023-03-06")
                & (df["Delivery Note Date"] < "2023-06-02")
                & (df["Sales Item Category"] == "Sushi")
            ] = "L41 Sushibar Länsikeskus Prisma Turku"

            df["Department"].loc[
                (df["Store"] == "MESTARIN HERKKU")
                & (df["Location (NS)"] == "L84 Itsudemo Sokkari Jyväskylä")
            ] = "Restaurant"
            df["Operating department"].loc[
                (df["Store"] == "MESTARIN HERKKU")
                & (df["Location (NS)"] == "L84 Itsudemo Sokkari Jyväskylä")
            ] = "Restaurant"

            df["Location (NS)"].loc[
                (df["Customer code and name"].str.contains("TURUN OSUUSKAUPPA", case=False))
                & (df["Delivery Note Date"] >= "2023-08-01")
                & (df["Sales Item Category"] == "Firewok")
            ] = "L23 Sushibar Manhattan S-Market Turku"
            df["Location (NS)"].loc[
                (df["Store"] == "PRISMA ITÄHARJU")
                & (df["Delivery Note Date"] >= "2024-05-13")
                & (df["Sales Item Category"] == "Firewok")
            ] = "L17 Sushibar Itäharju Prisma Turku"

            df["Location (NS)"].loc[
                (df["Delivery Note Date"] >= "2023-09-01")
                & (df["Location (NS)"] == "L43 Sushibar Kaari Prisma Helsinki")
                & (df["Sales Item Category"] == "Firewok")
            ] = "L72 Firewok Kaari Helsinki"
            df["Department"].loc[
                (df["Delivery Note Date"] >= "2023-09-01")
                & (df["Location (NS)"] == "L43 Sushibar Kaari Prisma Helsinki")
                & (df["Sales Item Category"] == "Firewok")
            ] = "Restaurant"
            df["Operating department"].loc[
                (df["Delivery Note Date"] >= "2023-09-01")
                & (df["Location (NS)"] == "L43 Sushibar Kaari Prisma Helsinki")
                & (df["Sales Item Category"] == "Firewok")
            ] = "Restaurant"
            df["Class"].loc[
                (df["Delivery Note Date"] >= "2023-09-01")
                & (df["Location (NS)"] == "L43 Sushibar Kaari Prisma Helsinki")
                & (df["Sales Item Category"] == "Firewok")
            ] = "Firewok"

            df["Location (NS)"].loc[
                (df["Delivery Note Date"] >= "2024-03-04")
                & (df["Location (NS)"] == "L9 Sushibar Linnainmaa Prisma Tampere")
                & (df["Sales Item Category"] == "Firewok")
            ] = "L29 Sushibar Pirkkala Prisma Pirkkala"


            df = df.sort_values(
                by=["Store", "Delivery Note Date"], ascending=True
            ).reset_index()
            split_df = df.loc[df["split_month"] == True]
            split_df["month"] = split_df["Delivery Note Date"].dt.month
            if len(split_df.month.unique()) == 2:
                before, after = (
                    split_df.month.unique().tolist()[0],
                    split_df.month.unique().tolist()[1],
                )
                moved_df = split_df.loc[split_df["month"] == after]
                df = df.drop(index=moved_df.index)
                df = pd.concat(
                    [add_position(df, "Store"), add_position(moved_df, "Store")], axis=0
                )
            else:
                df = add_position(df, "Store")

            st.markdown(
                "### Following data will be removed, please check if there is any unclassified data"
            )
            st.dataframe(
                df[
                    (df["Operating department"].isnull())
                    | (df["Customer code and name"].isnull())
                    | (df["Location (NS)"].isnull())
                    | (df["Sales Item Internal ID"].isnull())
                ].reset_index(),
                1500,
                1000,
                use_container_width=True,
            )

            nan = df[
                (df["Operating department"].isnull())
                | (df["Customer code and name"].isnull())
                | (df["Location (NS)"].isnull())
                | (df["Sales Item Internal ID"].isnull())
            ].index
            new_df = df.drop(index=nan, inplace=True)
            new_df = df.drop(df[df["Operating department"] == "Delivery"].index)
            # new_df = new_df.drop(new_df[(new_df['Store'].isin(['PRISMA HALIKKO','PRISMA NUMMELA'])) & (new_df['Product Name'] == 'FIREWOK BUFFET')].index)

            new_df["Sales Item Internal ID"] = new_df["Sales Item Internal ID"].astype(int)
            new_df["Tax code internalID"] = new_df["Tax code internalID"].astype(int)
            # new_df['EAN'] = new_df['EAN'].astype(int, errors='ignore')
            new_df.insert(0, "ExternalID", 0)
            # new_df = new_df.sort_values(by=["Store", "Delivery Note Date"], ascending=True).reset_index(drop=True)
            new_df["next"] = new_df[["Store"]].shift(1)

            new_df["ExternalID"] = (
                new_df["Store"] != new_df["next"]
            ).cumsum() + last_externalID_ns

            new_df["month"] = new_df["Delivery Note Date"].dt.month
            new_df["year"] = new_df["Delivery Note Date"].dt.year
            new_df["Term"] = new_df["Customer code and name"].map(
                dict(zip(master_customer["ID+Name"], master_customer["terms"]))
            )

            last_day_externaliID = (
                new_df.sort_values("Delivery Note Date")
                .groupby("ExternalID")
                .tail(1)[["ExternalID", "Delivery Note Date"]]
            )

            last_day_externaliID_dict = dict(
                zip(
                    last_day_externaliID["ExternalID"],
                    last_day_externaliID["Delivery Note Date"],
                )
            )

            # new_df['invoice_date']=new_df['ExternalID'].map(last_day_externaliID_dict)
            new_df["invoice_date"] = pd.Timestamp.now()

            new_df["due_date"] = new_df["invoice_date"] + pd.to_timedelta(
                new_df["Term"], unit="D"
            )
            week_num = list(new_df["Delivery Note Date"].tail(1).dt.isocalendar().week)[0]
            if len(new_df.year.unique()) == 2:
                start_of_week, end_of_week = get_start_and_end_date_from_calendar_week(
                    pd.Timestamp.now().year - 1, week_num
                )
            else:
                start_of_week, end_of_week = get_start_and_end_date_from_calendar_week(
                    pd.Timestamp.now().year, week_num
                )

            new_df["invoice_text_1"] = (
                f"{start_of_week.strftime('%d.%m')}-{end_of_week.strftime('%d.%m.%Y')} - Week {week_num}"
            )

            if len(new_df.month.unique()) == 2:
                prev_month_last_day = datetime.date(
                    start_of_week.year,
                    start_of_week.month,
                    calendar.monthrange(start_of_week.year, start_of_week.month)[1],
                )
                this_month_first_day = datetime.date(end_of_week.year, end_of_week.month, 1)
                new_df.loc[
                    (new_df["month"] == start_of_week.month)
                    & (new_df["split_month"] == True),
                    "invoice_text_1",
                ] = f"{start_of_week.strftime('%d.%m')}-{prev_month_last_day.strftime('%d.%m.%Y')} - Week {week_num}"
                new_df.loc[
                    (new_df["month"] == end_of_week.month)
                    & (new_df["split_month"] == True),
                    "invoice_text_1",
                ] = f"{this_month_first_day.strftime('%d.%m')}-{end_of_week.strftime('%d.%m.%Y')} - Week {week_num}"
                new_df["invoice_date"].loc[
                    (new_df["split_month"] == True)
                    & (new_df["month"] == start_of_week.month)
                ] = (new_df["invoice_text_1"].str.split("-", expand=True)[1].str.strip())

            col1, col2 = st.columns([1, 1])

            with col1:
                st.header("Download CSV file")

                total_wo_vat = new_df["Amount"].sum()
                df_without_converting_decimal = new_df.copy()
                new_df = new_df.replace([np.inf, -np.inf], 0)
                new_df["Unit Price"] = new_df["Unit Price"].fillna(0)
                new_df["Quantity"] = (
                    new_df["Quantity"]
                    .round(decimals=2)
                    .astype(str)
                    .str.replace(".", ",", regex=False)
                )
                new_df["Amount"] = (
                    new_df["Amount"]
                    .round(decimals=2)
                    .astype(str)
                    .str.replace(".", ",", regex=False)
                )
                new_df["Unit Price"] = (
                    new_df["Unit Price"]
                    .round(decimals=2)
                    .astype(str)
                    .str.replace(".", ",", regex=False)
                )
                new_df["Delivery Note Date"] = new_df["Delivery Note Date"].dt.strftime(
                    "%d.%m.%Y"
                )
                new_df["invoice_date"] = new_df["invoice_date"].dt.strftime("%d.%m.%Y")
                new_df["due_date"] = new_df["due_date"].dt.strftime("%d.%m.%Y")

                new_df = new_df.drop(
                    [
                        "index",
                        "next",
                        "ALV14",
                        "Commission Rate",
                        "Tax Rate",
                        "split_month",
                        "month",
                    ],
                    axis=1,
                    errors="ignore",
                )

                csv = new_df.to_csv(sep=";", index=False).encode("utf-8")

                st.write(f"Total (VAT0): {round(total_wo_vat,2)}")

                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name=f'{datetime.datetime.now(pytz.timezone("Europe/Helsinki")).strftime("%Y%m%d%H%M")}.csv',
                    mime="text/csv",
                )

            with col2:
                st.header("Send sales data to franchisee")
                send_data_options = st.multiselect(
                    "Stores that you need to send sales data?",
                    list(np.unique(np.array(new_df["Location (NS)"]))),
                    [
                        "L56 Sushibar Lippulaiva Prisma Espoo",
                        "L36 Sushibar Syke Prisma Lahti",
                    ],
                )

                if st.button("Send"):
                    for i in send_data_options:
                        try:
                            receiver = master_location.loc[
                                master_location["Location (NS)"] == i
                            ]["email"].values[0]
                            data_to_be_send = pd.pivot_table(
                                df_without_converting_decimal.loc[
                                    df_without_converting_decimal["Location (NS)"] == i
                                ],
                                values=["Amount"],
                                index=["Delivery Note Date"],
                                columns=["Sales Item Category"],
                                aggfunc="sum",
                                fill_value=0,
                                margins=True,
                                #    dropna=True,
                                margins_name="Total",
                                #    observed=False
                            )

                            if pd.notna(receiver):
                                data_to_be_send = data_to_be_send.round(2)
                                st.write(
                                    f"Sending {i} week {week_num} sales data to {receiver}"
                                )
                                send_email(
                                    receiver,
                                    f"Week {week_num} sales - {i}",
                                    data_to_be_send,
                                )
                            else:
                                st.write(
                                    f"Cannot find email address for receiving {i}'s sales data"
                                )
                        except:
                            pass
                    st.balloons()


with delivery_data:
    # Input field for NS external ID
    last_externalID_ns = int(
        st.number_input(
            "Insert last Internal ID in NetSuite.",
            step=1,
            key="delivery_external_id"
        )
    )

    con = init_connection()

    delivery_price = get_master_data("DeliveryPrice")
    location_master_data = get_master_data("Location").dropna(subset=["delivery_name"])
    # delivery_price.str.replace('now',  datetime.date.today())

    delivery_price["start_date"] = pd.to_datetime(
        delivery_price["start_date"], dayfirst=True
    ).dt.date
    delivery_price["end_date"] = pd.to_datetime(
        delivery_price["end_date"], dayfirst=True
    ).dt.date

    # Generate a list of dates between start and end date for each row
    delivery_price["date"] = delivery_price.apply(
        lambda x: pd.date_range(x["start_date"], x["end_date"], freq="D"), axis=1
    )

    # Expand the date column into multiple rows
    delivery_price = delivery_price.explode("date")

    # drop the unnecessary column
    delivery_price.drop(columns=["start_date", "end_date"], inplace=True)
    # delivery_price['date'] = pd.to_datetime(delivery_price['date']).dt.date
    delivery_price["date"] = pd.to_datetime(delivery_price["date"])

    current_delivery_stores = [
        "sm_kivistö",
        "sm_megakeskus",
        "sm_pajuluoma",
        "p_roo",
        "p_vanalinn",
        "p_tiskre",
        "varuboden",
    ]
    with con.connect() as conn:
        # result = conn.execute(text("DESCRIBE delivery;")).fetchall()
        # delivery_store = [i[0] for i in result if i[0] != 'date']

        select_all = delivery_data.checkbox("Select all stores:", value=False)
        if select_all:
            store_selected = current_delivery_stores
        else:
            store_selected = delivery_data.multiselect(
                "Please select store you need to calculate delivery sales:",
                options=current_delivery_stores,
                default=current_delivery_stores,
            )

        start, end = st.columns(2)
        start_date = start.date_input(
            "select start date",
            min_value=None,
            max_value=datetime.datetime.now(pytz.timezone(st.secrets["TIMEZONE"])),
            key="start_date",
            on_change=None,
        )

        end_date = end.date_input(
            "select end date",
            min_value=None,
            max_value=datetime.datetime.now(pytz.timezone(st.secrets["TIMEZONE"])),
            key="end_date",
            on_change=None,
        )

        query = f"SELECT date, {', '.join([str(i) for i in store_selected])} FROM data.delivery WHERE date BETWEEN '{start_date}' AND '{end_date}';"

        df_store_selected = pd.read_sql(text(query), con=conn, parse_dates=["date"])

    if not df_store_selected.empty:
        melted_df = pd.melt(
            df_store_selected,
            id_vars=["date"],
            value_vars=store_selected,
            var_name="store",
            value_name="Quantity",
        )
        melted_df["date"] = pd.to_datetime(melted_df["date"])
        merged_df = pd.merge(melted_df, delivery_price, on=["date", "store"])
        fi_data = merged_df.copy()

        fi_data["Product Name"] = "SOK delivery sales"
        fi_data["Sales Unit"] = "KG"
        fi_data["Tax code internalID"] = 8
        fi_data["Sales Item Internal ID"] = 1552
        fi_data["Sales Item Category"] = "Sushi"
        fi_data["Department"] = "Food Kiosk Sushibar"
        fi_data["Class"] = "Itsudemo"
        fi_data["amount"] = fi_data["price"] * fi_data["Quantity"]
        fi_data["Amount"] = (
            fi_data["amount"]
            .round(decimals=2)
            .astype(str)
            .str.replace(".", ",", regex=False)
        )
        fi_data["Quantity"] = (
            fi_data["Quantity"]
            .round(decimals=2)
            .astype(str)
            .str.replace(".", ",", regex=False)
        )

        fi_data["Store"] = fi_data["store"].map(
            dict(
                zip(
                    location_master_data["delivery_name"],
                    location_master_data["Ketjuyksikkö (SOK)"],
                )
            )
        )
        fi_data["Location (NS)"] = fi_data["location_internal_name"]

        fi_data["Delivery Note Date"] = fi_data["date"].dt.strftime("%d.%m.%Y")
        fi_data["Customer code and name"] = fi_data["Store"].map(
            dict(
                zip(
                    location_master_data["Ketjuyksikkö (SOK)"],
                    location_master_data["Customer code and name"],
                )
            )
        )
        fi_data["PO"] = fi_data["Store"].map(
            dict(
                zip(
                    location_master_data["Ketjuyksikkö (SOK)"],
                    location_master_data["#PO number"],
                )
            )
        )
        fi_data["invoice-specific message"] = fi_data["Store"].map(
            dict(
                zip(
                    location_master_data["Ketjuyksikkö (SOK)"],
                    location_master_data["invoice-specific message"],
                )
            )
        )
        fi_data["Unit Price"] = (
            fi_data["price"]
            .round(decimals=2)
            .astype(str)
            .str.replace(".", ",", regex=False)
        )
        fi_data["Term"] = 7
        fi_data.loc[fi_data["Store"] == "MESTARIN HERKKU", "Term"] = 14

        fi_data["invoice_date"] = pd.Timestamp.now()
        fi_data["due_date"] = fi_data["invoice_date"] + pd.to_timedelta(
            fi_data["Term"], unit="D"
        )

        fi_data["invoice_date"] = fi_data["invoice_date"].dt.strftime("%d.%m.%Y")
        fi_data["due_date"] = fi_data["due_date"].dt.strftime("%d.%m.%Y")

        fi_data["year"] = fi_data["date"].dt.year
        fi_data["Store"].fillna(fi_data["store"], inplace=True)

        week_num = fi_data["date"].max().isocalendar().week
        if len(fi_data.year.unique()) == 2:
            start_of_week, end_of_week = get_start_and_end_date_from_calendar_week(
                pd.Timestamp.now().year - 1, week_num
            )
        else:
            start_of_week, end_of_week = get_start_and_end_date_from_calendar_week(
                pd.Timestamp.now().year, week_num
            )

        fi_data["invoice_text_1"] = (
            f"{fi_data['date'].min().strftime('%d.%m')}-{fi_data['date'].max().strftime('%d.%m.%Y')} - Week {week_num}"
        )

        fi_data = fi_data.sort_values(by=["Store", "date"], ascending=True).reset_index(
            drop=True
        )
        fi_data = fi_data.loc[fi_data["amount"] > 0]
        fi_data = add_position(fi_data, "Store")

        fi_data.insert(0, "ExternalID", 0)
        # new_df = new_df.sort_values(by=["Store", "Delivery Note Date"], ascending=True).reset_index(drop=True)
        fi_data["next"] = fi_data[["Store"]].shift(1)

        fi_data["ExternalID"] = (
            fi_data["Store"] != fi_data["next"]
        ).cumsum() + last_externalID_ns

        invoicing_df = fi_data.loc[
            ~fi_data["location_internal_id"].isin([103, 104, 105, 309, 310, 85])
        ]

        fi_data = fi_data.drop(
            [
                "next",
                "date",
                "store",
                "location_internal_id",
                "location_internal_name",
                "price",
                "year",
                "amount",
            ],
            axis=1,
            errors="ignore",
        )
        invoicing_df = invoicing_df.drop(
            [
                "next",
                "date",
                "store",
                "location_internal_id",
                "location_internal_name",
                "price",
                "year",
                "amount",
            ],
            axis=1,
            errors="ignore",
        )

        st.dataframe(fi_data)

        csv_delivery = fi_data.to_csv(sep=";", index=False).encode("utf-8")

        st.download_button(
            label="Download FULL delivery data as CSV for dashboard",
            data=csv_delivery,
            file_name=f'{datetime.datetime.now(pytz.timezone("Europe/Helsinki")).strftime("%Y%m%d%H%M")}_dashboard.csv',
            mime="text/csv",
        )

        st.download_button(
            label="Download FI delivery data as CSV for invoicing",
            data=invoicing_df.to_csv(sep=";", index=False).encode("utf-8"),
            file_name=f'{datetime.datetime.now(pytz.timezone("Europe/Helsinki")).strftime("%Y%m%d%H%M")}.csv',
            mime="text/csv",
        )
