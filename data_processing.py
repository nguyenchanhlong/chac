from gspread import Client, Worksheet
from pandas import DataFrame
import numpy as np
from urllib.parse import urlparse
from gensim.parsing.preprocessing import remove_stopwords

from api.socket.log import log_service


# Define a function to process data from a Google Sheets worksheet
async def process_path_data(path_worksheet: Worksheet) -> DataFrame:
    await log_service.add_log('Processing path data...')
    # Create a DataFrame from the data in the worksheet, starting from the 4th row
    path_df: DataFrame = DataFrame(path_worksheet.get_all_values()[3:])

    # Remove the first column (index 0) from the DataFrame
    path_df = path_df.drop([0], axis=1)

    # Rename the remaining column to "paths"
    path_df.columns = ["paths"]

    # Replace empty cells with NaN values
    path_df.replace("", np.nan, inplace=True)

    # Remove rows with all NaN values
    path_df = path_df.dropna(how='all')

    # Apply the "extract_path_keyword" function to each cell in the "paths" column and create a new "key_words" column
    path_df["key_words"] = path_df.iloc[:].applymap(extract_path_keyword)

    # Find duplications in the "paths" column
    duplications = path_df[path_df["paths"].duplicated()]

    # Drop rows with duplicated paths
    path_df = path_df.drop(duplications.index)

    # Reset the index of the DataFrame (Note: This line doesn't update the DataFrame in place)
    path_df.reset_index()
    await log_service.add_log('Done')
    # Return the processed DataFrame
    return path_df


def has_numbers(input_string: str):
    return any(char.isdigit() for char in input_string)


def extract_path_keyword(path: str) -> str:
    # Define a list of words to be eliminated from the path
    eliminate_words = ["Electronics", "components", "Electronic", "field", "Industrial", "Factory", "production",
                       "solution", "communication", "url"]

    # Convert the path to lowercase for case-insensitive comparison
    path = path.lower()

    # Iterate over eliminate_words and remove them from the path
    for ew in eliminate_words:
        path = path.replace(ew.lower(), "")

    # Initialize an empty result string
    result = ""

    # Process the path to extract keywords
    path_elements: list = (path
                           .replace("-", " ")
                           .replace("/", ",")
                           .replace(">>", ",", 1)
                           .replace("&", ", ")
                           .replace(">>", ",")
                           .split(","))

    for word in path_elements:
        if word.strip() != "":
            # Remove leading and trailing spaces and append the word to the result
            result += word.strip() + ","

    # Return the resulting keywords with a trailing comma
    return result


def word_valid(string):
    # Define a list of unvaluable words
    unvaluable = ['product', "category", "html", "pdf", "catalog", "index", "en-us", "vn-vi", "eng", 'url']

    # Define a list of regions
    regions = ["en", "us", "vn", 'vi']

    # Check if any of the unvaluable words are present in the string or its components
    for word in unvaluable:
        if (
                any([region in regions for region in string.split("-")]) or  # Check if any region is in the string
                word in regions or  # Check if the word is in the list of regions
                word in string or  # Check if the word is in the string
                string.strip() == "" or  # Check if the string is empty after stripping spaces
                len(string.strip()) < 2  # Check if the string has fewer than 2 characters after stripping spaces
        ):
            return False  # The string is not valid if any of the conditions are met

    return True  # If none of the conditions are met, the string is considered valid


# Define a function to extract keywords from a product name and URL
def extract_product_keywords(name, url):
    # Extract the path from the URL and replace file extensions with spaces
    http_link = urlparse(url.replace("https://www.google.com/url?q=", "")).path.replace(".html", " ").replace(".pdf",
                                                                                                              " ")

    # Initialize a list to store valid words
    valid_words = []

    # Store the original product name
    old_name = name

    # Initialize a list to store word validation results
    word_result = []

    # Iterate through words in the URL path
    for word in http_link.split("/"):
        word_split = word.strip().split(" ")
        if len(word_split) > 1:
            for subword in word_split:
                # Append the subword and its validity to word_result
                word_result.append((subword.strip(), word_valid(subword.strip())))
                if word_valid(subword):
                    valid_words.append(subword)
        else:
            # Append the word and its validity to word_result
            word_result.append((word.strip(), word_valid(word.strip())))
            if word_valid(word.strip()):
                valid_words.append(word)

    # Convert valid words to a comma-separated string
    http_link = ", ".join(valid_words)

    # Store the original product name
    name = old_name

    # Initialize a list to store filtered result words
    result = []

    # Split the product name and http_link, remove unwanted characters, and convert to lowercase
    for char_filter in f"{name}, {http_link}".replace("/", "").lower().split(" "):
        if not has_numbers(char_filter):
            if char_filter in ["i/o", "i-o"]:
                char_filter = char_filter.replace("/", "").replace("-", "")
            result.append(char_filter.strip())

    # Remove stopwords, replace underscores and hyphens, and remove ampersands

    # print(web_content)
    return remove_stopwords(" ".join(result)).replace("_", ", ").replace("-", " ").replace("&", "")


# # Define a function to process product data from a Google Sheets worksheet
# def process_product_data(product_worksheet: Worksheet) -> tuple[DataFrame, DataFrame, DataFrame]:
#     # Extract all data from the worksheet
#     product_data = product_worksheet.get_all_values()
#
#     # Create a DataFrame from the data, starting from the 3rd row
#     product_df = DataFrame(product_data[2:])
#
#     # Set the column names based on the 2nd row of the data
#     product_df.columns = product_data[1]
#
#     # Filter rows with both "Product category Layer-5 Full Path" and "Product name EN" not empty
#     human_labeled = product_df.loc[
#         (product_df["Product category Layer-5 Full Path"] != "") &
#         (product_df["Product name EN"] != "")
#         ]
#
#     # Reset the index and add an empty "key_words" column
#     human_labeled.reset_index(drop=True, inplace=True)
#     human_labeled["key_words"] = ""
#
#     # Filter rows with "Product category Layer-5 Full Path" empty and "Product name EN" not empty
#     unlabeled_product_and_link = product_df.loc[
#         (product_df["Product category Layer-5 Full Path"] == "") &
#         (product_df["Product name EN"] != "")
#         ]
#
#     # Replace empty values with NaN and select specific columns
#     (unlabeled_product_and_link.replace('', np.nan)[["Product category Layer-5 Full Path", "Product name EN"]]
#      .dropna(inplace=True))
#     unlabeled_product_and_link.reset_index(drop=True, inplace=True)
#
#     # Reset the index of the unlabeled product data and add an empty "key_words" column
#     unlabeled_product_and_link.reset_index(drop=True, inplace=True)
#     unlabeled_product_and_link["key_words"] = [
#         # Process product data for each row in the DataFrame
#         extract_product_keywords(
#             unlabeled_product_and_link.iloc[idx]["Product name EN"],
#             unlabeled_product_and_link.iloc[idx]["Product site link EN"]
#         )
#         for idx in range(0, unlabeled_product_and_link.shape[0])
#     ]
#
#     # Return the processed DataFrames for unlabeled and human-labeled data
#     return product_data, unlabeled_product_and_link, human_labeled


# Define a function to process product data from a Google Sheets worksheet
def process_product_data(product_worksheet: Worksheet) -> tuple[DataFrame, DataFrame]:
    log_service.add_log('Processing product data...')
    # Extract all data from the worksheet
    product_data = product_worksheet.get_all_values()

    # Create a DataFrame from the data, starting from the 3rd row
    product_df = DataFrame(product_data[2:])

    # Set the column names based on the 2nd row of the data
    product_df.columns = product_data[1]

    # Replace empty values with NaN and select specific columns
    (product_df.replace('', np.nan)[["Product category Layer-5 Full Path", "Product name EN"]]
     .dropna(inplace=True))
    product_df.reset_index(drop=True, inplace=True)

    # Reset the index of the unlabeled product data and add an empty "key_words" column
    # product_df.reset_index(drop=True, inplace=True)
    product_df["key_words"] = [
        # Process product data for each row in the DataFrame
        extract_product_keywords(
            product_df.iloc[idx]["Product name EN"],
            product_df.iloc[idx]["Product site link EN"]
        )
        for idx in range(0, product_df.shape[0])
    ]

    # Return the processed DataFrames for unlabeled and human-labeled data
    return product_data, product_df



# Define a function to extract data from two Google Sheets given their URLs
def extract_gsheet_data(gc: Client, product_url: str, path_url: str) -> tuple[Worksheet, Worksheet]:
    # await log_service.add_log('Extracting google sheet data...')
    # Access the product and path sheets using their URLs
    product_sheet = gc.open_by_url(product_url)
    path_sheet = gc.open_by_url(path_url)

    # Get the first worksheet of the product and path sheets
    path_worksheet = path_sheet.get_worksheet(0)
    product_worksheet = product_sheet.get_worksheet(0)

    print("done reading data!")
    # log_service.add_log('Done extract google sheet data')
    # Return the product and path worksheets as a tuple
    # await log_service.add_log('Done.')
    return product_worksheet, path_worksheet
