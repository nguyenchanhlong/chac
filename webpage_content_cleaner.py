from typing import Dict, Union
from urllib.parse import urlparse

import numpy as np
from gspread import Client, Worksheet
from pandas import DataFrame
from transformers import Pipeline, pipeline
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from web_crawler import load_link_history
import json
import re
from api.socket.log import log_service


def write_page_content_to_product(
    product_df: DataFrame, history_workbook: Worksheet, link_data_map: dict[str, str]
):
    log_service.add_log('Writing product content...')
    product_df["web_content"] = ""
    summarizer: Pipeline = pipeline(
        "summarization", model="facebook/bart-large-cnn", device=0
    )

    for idx in range(len(product_df)):
        print("\n\n\n\n RUN: ", idx + 1, product_df.iloc[idx]["Product site link EN"])
        result = ""

        if link_data_map.get(product_df.iloc[idx]["Product site link EN"]) is not None:
            key = product_df.iloc[idx]["Product site link EN"]
            page_content: Union[str, None] = link_data_map.get(key)

            if page_content is None:
                page_content = ""

            pro_name = product_df.iloc[idx]["Product name EN"]

            tmp_lines = []
            if len(page_content) > 1024:
                length = 0
                for line in page_content.splitlines():
                    if pro_name.lower() in line.lower():
                        length += len(line)
                        if length < 1024:
                            tmp_lines.append(line)
                        else:
                            break
                if len(tmp_lines) == 0 or sum([len(line) for line in tmp_lines]) < 100:
                    length = 0
                    for line in page_content.splitlines():
                        length += len(line)
                        if length < 1024:
                            tmp_lines.append(line)
                        else:
                            break
                page_content = "\n".join(tmp_lines)

            if len(page_content) > 0:
                print(len(page_content), page_content)
                result = summarizer(
                    page_content,
                    max_length=130,
                    min_length=30,
                    do_sample=False,
                )[0]["summary_text"]
                print(result)
                # history_workbook.update_cell(idx + 1, 3, value=result)
        log_service.add_log('Done.')
        product_df["web_content"].iloc[idx] = result


# def write_page_content_to_product(product_df: DataFrame, history_workbook: Worksheet, link_data_map: dict[str, str]):
#     product_df['web_content'] = ""
#     summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=0)
#
#     # Load model directly
#
#     tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")
#     model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn")
#
#     for idx in range(len(product_df)):
#         if link_data_map.get(product_df.iloc[idx]['Product site link EN']) is not None:
#
#             page_content: str = link_data_map.get(product_df.iloc[idx]['Product site link EN'])
#             pro_name = product_df.iloc[idx]["Product name EN"]
#
#             tmp_lines = []
#             if len(page_content) > 1024:
#                 length = 0
#                 for line in page_content.splitlines():
#                     if pro_name.lower() in line.lower():
#                         length += len(line)
#                         if length < 1024:
#                             tmp_lines.append(line)
#                         else:
#                             break
#                 if len(tmp_lines) == 0 or sum([len(line) for line in tmp_lines]) < 100:
#                     length = 0
#                     for line in page_content.splitlines():
#                         length += len(line)
#                         if length < 1024:
#                             tmp_lines.append(line)
#                         else:
#                             break
#                 page_content = "\n".join(tmp_lines)
#
#             print("RUN: ", idx + 1, product_df.iloc[idx]['Product site link EN'])
#             print("\n\n\n\n", len(page_content), page_content)
#             result = summarizer(page_content, max_length=130, min_length=30, do_sample=False)[0]["summary_text"]
#             print(result)
#             # history_workbook.update_cell(idx + 1, 3, value=result)
#
#             product_df['web_content'].iloc[idx] = result


def run_extract(gc: Client, history_url: str) -> tuple[Worksheet, dict[str, str]]:
    history_workbook, history_memcache = load_link_history(gc, history_url)
    all_data = history_workbook.get_all_values()

    history_df: DataFrame = DataFrame(all_data[1:], columns=all_data[0])
    data_cache, domain_pages = construct_data_trees(history_df)
    url_content_map: dict[str, str] = {}
    for idx in range(len(history_df)):
        url: str = history_df.iloc[idx]["url"]
        if not any([url.endswith(tail) for tail in ["png", "pdf", "jpeg", "jpg"]]):
            parsed_url = urlparse(url)
            if parsed_url is not None:
                url_content_map[url] = extract_keywords_from_content(
                    str(history_df.iloc[idx]["content"]).splitlines(),
                    parsed_url.hostname,
                    data_cache,
                )
    return history_workbook, url_content_map


# Extract web content.
def construct_data_trees(
    data: DataFrame
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    data_cache: dict[str, dict[str, int]] = {}
    domain_pages: dict[str, int] = {}

    for idx in range(len(data)):
        url: str = data.iloc[idx]["url"]
        if not url.endswith("pdf"):
            domain = urlparse(url).hostname

            if data_cache.get(domain) is None:
                data_cache[domain] = {}
                domain_pages[domain] = 0

            content: list[str] = str(data.iloc[idx]["content"]).splitlines()

            domain_pages[domain] += 1
            for line in content:
                if line.strip() != "":
                    if data_cache[domain].get(line.strip()) is None:
                        data_cache[domain][line.strip()] = 1
                    else:
                        data_cache[domain][line.strip()] += 1

    return data_cache, domain_pages


def extract_keywords_from_content(
    url_content: list[str], domain: str, data_cache: dict[str, dict[str, int]]
) -> str:
    """
    This function will extract keywords from an url by querying the cache and fred data.
    :param domain:
    :param url_content:
    :param data_cache: cache that store line of data by domain as key and the count of each line in entire domain.
    :return: the key word extracted from data by url.
    """
    lines = []
    for line in url_content:
        line = line.strip()
        if (
            data_cache[domain].get(line) is not None
            and data_cache[domain].get(line) < 2
        ):
            lines.append(line)
    return "\n".join(lines)
