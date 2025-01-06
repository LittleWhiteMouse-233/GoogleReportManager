import pandas as pd
import fuzzywuzzy.process as fuzzysearch


def dict2map(_dict: dict):
    return pd.concat([pd.Series(_dict.keys()), pd.Series(_dict.values())], axis=1)


def reset_column(data: pd.DataFrame | pd.Series, drop=False):
    if type(data) is pd.Series:
        data = pd.DataFrame(data)
    return data.T.reset_index(drop=drop).T


def locate_map_table(map_table: pd.DataFrame, keyword: str, col=0):
    _, score, index = fuzzysearch.extractOne(keyword, map_table.iloc[:, col])
    if score > 90:
        return index
    else:
        return None
