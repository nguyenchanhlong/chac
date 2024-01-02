# Import selenium driver.
import multiprocessing
from datetime import datetime
from multiprocessing import Process, Queue
from time import sleep

from gspread import Client, Spreadsheet, Worksheet
from pandas import DataFrame
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver

# from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from gsheet_handler import append_data_to_sheet
from api.socket.log import log_service
ENV_COLAB = "colab"
ENV_PHYSICAL = "physical"


def load_link_history(gc: Client, history_url) -> tuple[Worksheet, dict[str, str]]:
    # load history file.
    history_file: Spreadsheet = gc.open_by_url(history_url)
    history_worksheet: Worksheet = history_file.get_worksheet(0)

    data: list[list] = history_worksheet.get_all_values()

    if len(data) > 2:
        history_df = DataFrame(data[1:], columns=data[0])
    else:
        history_df = DataFrame(columns=data[0])

    # convert to dict and return the dict
    history_mem_cache: dict[str, str] = {}
    for idx in range(history_df.shape[0]):
        history_mem_cache[history_df.iloc[idx]["url"]] = history_df.iloc[idx]["content"]

    return history_worksheet, history_mem_cache


def concurrent_crawler(
    wait_list: list[str],
    concurrency: int,
    list_of_driver_instances: list[WebDriver],
    history_worksheet: Worksheet,
    history_mem_cache: dict,
):
    # if the wait list is equal to the concurrency number then process the wait list.
    proccesses: list[Process] = []
    results: list[list[str]] = []

    queue_list: list[Queue[list[str]]] = []
    for i in range(concurrency):
        queue_list.append(Queue())

    # simultaneously run the process to crawl data from the wait list's urls.
    for i in range(concurrency):
        process = Process(
            target=crawl_webpage_content,
            args=(wait_list[i], list_of_driver_instances[i], queue_list[i]),
        )
        proccesses.append(process)

    for pro in proccesses:
        pro.start()

    for pro in proccesses:
        pro.join(timeout=10)

    # get result from the queue.
    print("here!")

    for q in queue_list:
        results.append(q.get())

    print("here!", len(results))
    # append data to sheet.
    if len(results) > 0:
        for result in results:
            print(len(result[1]))
            if len(result[1]) > 50000:
                result[1] = result[1][:49000]
        append_data_to_sheet(history_worksheet, results)

    # update the memcache
    for result in results:
        history_mem_cache[result[0]] = result[1]


def crawl_and_save_data_mp(
    gc: Client, urls: list[str], history_url: str, env=ENV_PHYSICAL
) -> Worksheet:
    log_service.add_log('Crawling data ...')
    history_mem_cache: dict[str, str]
    history_worksheet: Worksheet

    history_worksheet, history_mem_cache = load_link_history(gc, history_url)

    concurrency: int = int(multiprocessing.cpu_count() / 2) + 2

    get_driver = open_driver if env == ENV_PHYSICAL else open_driver_colab

    list_of_driver_instances: list[WebDriver] = [
        get_driver() for _ in range(concurrency)
    ]

    # check if url is existed in the db.
    # content: list[str]
    #
    # place to save urls that are need to be crawled.
    wait_list: list[str] = []
    url_len: int = len(urls)  # all urls
    url_count = 0  # count urls to crawled

    # for index in the total url
    for idx in range(url_len):
        # if the url is not processed => append to the wait list.
        if history_mem_cache.get(urls[idx]) is None:
            wait_list.append(urls[idx])
            url_count += 1

        if len(wait_list) == concurrency:
            # crawl data
            concurrent_crawler(
                wait_list,
                concurrency,
                list_of_driver_instances,
                history_worksheet,
                history_mem_cache,
            )
            # move the idx to the next n element and reset the wait list.
            idx += url_count
            wait_list: list[str] = []
    log_service.add_log('Done.')
    return history_worksheet


def open_driver_colab() -> WebDriver:
    chrome_options = webdriver.ChromeOptions()

    # add chrome options.
    chrome_options.add_argument("--headless")  # ensure GUI is off
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920, 1200")
    chrome_options.add_experimental_option(
        "prefs", {"profile.default_content_settings.cookies": 2}
    )
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    return webdriver.Chrome(options=chrome_options)


def open_driver() -> WebDriver:
    chrome_options = webdriver.ChromeOptions()

    # add chrome options.
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920, 1200")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    return webdriver.Chrome(options=chrome_options)


def pre_process_url(url: str) -> str:
    result = url.replace("https://www.google.com/url?q=", "")
    return result


def crawl_webpage_content(url, driver: WebDriver, queue: Queue):
    try:
        url = pre_process_url(url)
        print(url)
        sleep(1)
        driver.get(url)

        # Wait 5 secs for webpage is fully loaded as well as
        # prevent too much connection to the host => they
        # will block us as an attacker.
        start = datetime.now()
        print("start waiting for ", url, start)

        sleep(5)

        body = driver.find_element(By.TAG_NAME, value="body")
        text = body.get_attribute("innerText")

        if text is None:
            text = ""
        else:
            text = text.splitlines()

        print("end wait for ", url, (datetime.now() - start).seconds)
        queue.put([url, "\n".join(text)])
        print("done!")

    except Exception as e:
        print(e)
        queue.put([url, "ERROR, " + str(e)])
