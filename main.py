import asyncio
import json
import threading

import gspread
from google.oauth2 import service_account
from google.oauth2.service_account import Credentials
from gspread import Client
from starlette.staticfiles import StaticFiles

from api.socket.log import log_service
from cosine_similarity_evaluate import (
    compare,
    add_result_to_table,
    grouping_data_and_merge,
)
from data_processing import extract_gsheet_data, process_path_data, process_product_data
from gsheet_handler import create_result_sheet, write_to_gsheet
from web_crawler import crawl_and_save_data_mp, ENV_PHYSICAL, ENV_COLAB
from webpage_content_cleaner import run_extract, write_page_content_to_product
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect,Depends
from fastapi.responses import HTMLResponse

from api.socket.log import log_service


SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]
# FOLDER_ID = "1x5rCeO3XCejuG2xFknFPb9foQ98oMrLD"
FOLDER_ID ='1Xn-JPPm_ojeEdg8EeRrO5mfDygr-kGRU'
TEMPLATE_ID = "1GRlLeGr10fJE5-SLC29aFY-uXF58-fG9SJcPPzB6n4k"
SERVICE_ACCOUNT_FILE = "google_api_key.json"
HISTORY_URL = "https://docs.google.com/spreadsheets/d/1xh7pa7Glo8QLSRR0UG-wMyzO8uYIO8p-DHZ1cczGdoY/edit#gid=0"

"""
step 1: Load file history file (gsheet file) (contains all visited links) to 
        dict with url is the key and its content as value.
step 2: Crawl data.
    - For every url, if url is not existed in the history file => crawl.
    - Append url and content to file.
    - Continue.
step 3: filter out unnecessary words.
    Algorithm:
        1. For every url, extract url to (domain_name, url)
        2. Save domain_name as key, content as key in the domain and the list urls 
            that the line of content come from as the value of line.
        3. For every line from all the links in the domain name
            - if line is exist from the domain name => count 1
            - else add the word as key and count 1.
        4. calculate the mean of the frequency of word's occurrence in the page
            - Get all line in the first quarter of the distribution as important line.
            - The rest is non-valuable words.
        5. For every link, get all important lines from it.
        6. Using the summary model to summarize the content.
        7. Compare the name + keywords in link + summarized content with the path to improve performance.  
"""


def main(gsheet_client: Client, product_sheet_link: str, path_sheet_link: str) -> None:
    # creds: Credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    # gsheet_client: Client = gspread.authorize(creds)

    # get and extract desired values of the sheets.
    product_worksheet, path_worksheet = extract_gsheet_data(
        gsheet_client, product_sheet_link, path_sheet_link
    )

    # convert data from google sheet values (type list ) to pandas data frame.
    path_df = process_path_data(path_worksheet)
    product_data, product_df = process_product_data(product_worksheet)

    print("done extract data!")
    env = ENV_COLAB

    # crawl data from website and save it to the data sheet.
    crawl_and_save_data_mp(
        gsheet_client, product_df["Product site link EN"].tolist(), HISTORY_URL, env=env
    )
    history_workbook, url_content_map = run_extract(gsheet_client, HISTORY_URL)

    write_page_content_to_product(product_df, history_workbook, url_content_map)

    # Compare the cosine similarity of each product to each path by taking
    # dot product of 2 matrix, then get the top 5 highest scores & indices
    # and the highest score as well as the index of the result.
    top5_result, result = compare(path_df, product_df)

    # Add the result to dataframe "product_df".
    add_result_to_table(product_df, result, path_df)

    # Merge data to one data frame, group by scores ['Really-Low', 'Low', 'Medium', 'High', 'Really-High', "Abnormal"]
    # For data that labeled by human => Group them as "Human Labeled"
    final_labeled_sheet = grouping_data_and_merge(product_df)

    # Create result link
    result_file = create_result_sheet(gsheet_client, TEMPLATE_ID, FOLDER_ID)

    # Write data to the result sheet.
    result_url = write_to_gsheet(
        gsheet_client, final_labeled_sheet, product_data, result_file
    )

    print(
        "\n\n\n#########################################################################"
    )

    print("RESULT LINK: ", result_url)
    print("#########################################################################")


def run_crawl_data():
    product_sheet_link = "https://docs.google.com/spreadsheets/d/1d3nGcIRPn6dQ6xXHy11Wx8DRgvPLRzzOFx2I7DtlRg4/edit#gid=997280020"
    path_sheet_link = "https://docs.google.com/spreadsheets/d/15sbN2LDw4dxoAcFZuxBCTXNQWf6S7o2JCG-h8A_W5Qs/edit#gid=548273911"

    creds: Credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    gsheet_client: Client = gspread.authorize(creds)

    # get and extract desired values of the sheets.
    product_worksheet, path_worksheet = extract_gsheet_data(
        gsheet_client, product_sheet_link, path_sheet_link
    )

    # convert data from google sheet values (type list ) to pandas data frame.
    product_data, product_df = process_product_data(product_worksheet)

    env = ENV_PHYSICAL
    url_list = product_df["Product site link EN"].values.tolist()

    # crawl data from website and save it to the data sheet.
    crawl_and_save_data_mp(gsheet_client, url_list, HISTORY_URL, env)

    # write_page_content_to_product(product_df, run_extract(gsheet_client, HISTORY_URL))

    # print(product_df.to_csv("test.csv"))

    # print(product_df.apply(
    #     lambda data: get_keywords(data),
    #     axis=1).to_list())


def get_keywords(data) -> str:
    print(data[["key_words", "web_content"]])
    return ", ".join([data["key_words"], data["web_content"]])


def get_google_cli() -> Client:
    creds: Credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    gsheet_client: Client = gspread.authorize(creds)

    return gsheet_client

'''
    Using socket to communicate with client and send data to server to work
'''
def async_send_data(socket: WebSocket) -> None:
    while True:
        if log_service.new_log is True:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(socket.send_text(f'Update progress {log_service.get_logs()}'))

app = FastAPI()

# Mount the static files (images) at the "/static" path
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get():
    html = open("static/use_ai.html", "r").read()
    return HTMLResponse(content=html, status_code=200, headers={"Content-Type": "text/html"})
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    # Receive data as plain text
    data = await websocket.receive_text()
    # print("Received data:", data)
    subthread = threading.Thread(target=async_send_data, args=(websocket,))
    with threading.Lock():
        subthread.start()
    # Split the received data into product_link and path_link
    try:
        # Split using a delimiter, for example '/'
        parts = data.split('*')
        if len(parts) >= 2:
            product_link = parts[0].strip()
            path_link = parts[1].strip()

            main(get_google_cli(), product_link, path_link)

            # Your logic to use product_link and path_link here

            # await websocket.send_text(f'Received Product Link: {product_link}, Path Link: {path_link}')
        else:
            raise ValueError("Invalid data format: not enough values to unpack")
    except Exception as e:
        print("Error processing data:", e)
        await websocket.send_text(f"Error processing data: {str(e)}")

    # product_sheet_link = "https://docs.google.com/spreadsheets/d/1d3nGcIRPn6dQ6xXHy11Wx8DRgvPLRzzOFx2I7DtlRg4/edit#gid=997280020"
    # path_sheet_link = "https://docs.google.com/spreadsheets/d/1d3nGcIRPn6dQ6xXHy11Wx8DRgvPLRzzOFx2I7DtlRg4/edit#gid=997280020"

















# if __name__ == "__main__":
    # product_sheet_link = "https://docs.google.com/spreadsheets/d/1d3nGcIRPn6dQ6xXHy11Wx8DRgvPLRzzOFx2I7DtlRg4/edit#gid=997280020"
    # path_sheet_link = "https://docs.google.com/spreadsheets/d/15sbN2LDw4dxoAcFZuxBCTXNQWf6S7o2JCG-h8A_W5Qs/edit#gid=548273911"
    #
    # main_aaa(get_google_cli(), product_sheet_link, path_sheet_link)
    # #
    # app = FastAPI()
    #
    # html = open("/static/index.html", "r").read()








    # run_crawl_data()
