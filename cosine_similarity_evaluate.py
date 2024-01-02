from pandas import DataFrame
from sentence_transformers import SentenceTransformer, util
import torch
import torch.nn.functional as F
import pandas as pd
from torch import Tensor
from transformers import pipeline

from data_processing import extract_product_keywords
from api.socket.log import log_service


def encode_data(path_df: DataFrame, product_df: DataFrame) -> tuple[Tensor, Tensor]:
    model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

    # Encode data to tensor.
    path_encoded = model.encode(path_df["key_words"].to_list(), convert_to_tensor=True)

    # summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=0)
    #
    # tmp_data = summarizer(product_df.loc[:]["web_content"].to_list(), max_length=130, min_length=30,
    #                       do_sample=False)
    #
    # for idx in range(len(tmp_data)):
    #     product_df["web_content"].iloc[idx] = tmp_data[idx]["summary_text"]

    product_encoded = model.encode(
        product_df.apply(
            lambda data: ", ".join([data["key_words"], data["web_content"]]).lower(),
            axis=1,
        ).to_list(),
        convert_to_tensor=True,
    )

    # Normalize embeddings
    path_encoded = F.normalize(path_encoded, p=2, dim=1)
    product_encoded = F.normalize(product_encoded, p=2, dim=1)

    return path_encoded, product_encoded


def cosine_similarity(product_encoded: Tensor, path_encoded: Tensor):
    product_result = util.pytorch_cos_sim(product_encoded, path_encoded)
    return torch.topk(product_result, k=5, dim=1), torch.max(product_result, dim=1)


def compare(path_df: DataFrame, product_df: DataFrame):
    log_service.add_log('Comparing keywords ...')
    path_encoded, product_encoded = encode_data(path_df, product_df)

    return cosine_similarity(product_encoded, path_encoded)


def add_result_to_table(product_df, result, path_df):
    log_service.add_log('Adding results ...')
    labeled_path = []
    scores = []

    for i in range(result.values.shape[0]):
        labeled_path.append(path_df.iloc[result.indices[i].item()]["paths"])
        scores.append(result.values[i].item())

    # Write to data frame.
    product_df["Product category Layer-5 Full Path"].loc[:] = labeled_path
    product_df["Score"] = scores

    product_df.drop("", axis=1, inplace=True)
    product_df.drop("web_content", axis=1, inplace=True)




def grouping_data_and_merge(product_df):
    log_service.add_log('Grouping data ...')
    # Define the bins and labels
    bins = [0, 0.2, 0.4, 0.6, 0.8, 0.9, 1]
    labels = ["Really-Low", "Low", "Medium", "High", "Really-High", "Abnormal"]

    # Create the 'group' column
    product_df["Group"] = pd.cut(
        product_df["Score"], bins=bins, labels=labels, include_lowest=True
    )

    product_df.sort_values(["Score"], ascending=False, inplace=True)

    product_df["Score"].fillna("", inplace=True)
    product_df["Group"] = product_df["Group"].astype(dtype=str)
    product_df["Group"].replace("nan", "Human Labeled", inplace=True)
    log_service.add_log('Done.')
    return product_df
