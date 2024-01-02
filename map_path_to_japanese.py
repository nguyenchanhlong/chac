from google.oauth2 import service_account
from google.oauth2.service_account import Credentials
from gspread import Client, Worksheet
import gspread
from pandas import DataFrame

translate_link = "https://docs.google.com/spreadsheets/d/1bL6XVEBF6ffc8qRs2Vzx5qWxnH6Lo6bDkFXNqvoAlxs/edit#gid=1925610230"
# result_link = "https://docs.google.com/spreadsheets/d/1wWdzXlzqRSeRIqR8hAGzrF_iJ2BrferTlPrPx314poM/edit#gid=0"
result_link = "https://docs.google.com/spreadsheets/d/1X3T7FBouKerV94Eb6c02V4SWK0H4tKcbV0KrUr2JA4E/edit#gid=0"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
SERVICE_ACCOUNT_FILE = "google_api_key.json"

creds: Credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
gsheet_client: Client = gspread.authorize(creds)

product_category = gsheet_client.open_by_url(translate_link).worksheet(
    "Data_ProductCategory"
)
result = gsheet_client.open_by_url(result_link)

high: Worksheet
medium: Worksheet
low: Worksheet

high, medium, low = result.worksheets()

product_category_values = product_category.get_all_values()
print(product_category_values[0])
product_category_df = DataFrame(
    product_category_values[1:], columns=product_category_values[0]
)
product_category_dict = {}
for idx in range(product_category_df.shape[0]):
    product_category_dict[
        product_category_df.iloc[idx]["Full Path Category"].strip()
    ] = (
        product_category_df.iloc[idx]["Layer-5-jp"],
        product_category_df.iloc[idx]["Full Path Category JP"],
    )


def add_path(ws: Worksheet):
    """
    ws: this is the target workshet that we want to use.
    """
    values = ws.get_all_values()
    df = DataFrame(values[1:], columns=values[0])
    print(df.shape)
    for i in range(df.shape[0]):
        print(df.iloc[i]["Product category Layer-5 Full Path"].strip())
        data = product_category_dict.get(
            df.iloc[i]["Product category Layer-5 Full Path"].strip()
        )
        print(data)
        if data is None:
            data = ("", "")
        df.loc[i, "Product category Layer-5 Full Path JP"] = data[1]
        df.loc[i, "Product name JP"] = data[0]

        print(df.iloc[i])
    df = df.fillna("")
    ws.update("A2:K", df.values.tolist())


add_path(high)
add_path(medium)
add_path(low)
