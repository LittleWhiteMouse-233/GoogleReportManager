import os
import re
import pandas as pd


def absolute_path(path: str):
    return os.path.join('' if os.path.isabs(path) else os.getcwd(), path)


def clean_string(string: str):
    string = re.sub(r'[\n\r]+', r'<br/>', string)
    string = re.sub(r'[ \f\t\v]+', ' ', string)
    string = re.sub(r'\s+', ' ', string)
    string = re.sub(r'\s+$', '', string)
    string = re.sub(r'^\s+', '', string)
    string = re.sub(r'&amp;', '&', string)
    string = re.sub(r'<br/>', '\n', string)
    string = re.sub(r'<.*?>', '', string)
    return string


def paths_sort_by_create(path_list: list[str], reverse=False):
    return sorted(path_list, key=lambda x: os.path.getctime(x), reverse=reverse)


def listdir_sort_by_create(path: str, reverse=False):
    return paths_sort_by_create(list(map(lambda x: os.path.join(path, x), os.listdir(path))), reverse=reverse)


def dirs_sort_by_create(path: str, reverse=False):
    return paths_sort_by_create(list(map(lambda x: os.path.join(path, x), next(os.walk(path))[1])), reverse=reverse)


def limit_suffix(path_list: list[str], suffix: list[str]):
    limit_list = []
    for path in path_list:
        if os.path.splitext(path)[1] in suffix:
            limit_list.append(path)
    return limit_list


def files_sort_by_create(path: str, suffix: list[str] = None, reverse=False):
    path_list = list(map(lambda x: os.path.join(path, x), next(os.walk(path))[2]))
    if suffix:
        path_list = limit_suffix(path_list, suffix)
    return paths_sort_by_create(path_list, reverse=reverse)


def reset_column(data: pd.DataFrame | pd.Series, drop=False):
    if type(data) is pd.Series:
        data = pd.DataFrame(data)
    return data.T.reset_index(drop=drop).T


def any_scale_to_decimal(num_list: list[int], origin_scale: int, natural=True):
    if natural:
        num_list.reverse()
    decimal_num = 0
    for i, num in enumerate(num_list):
        decimal_num += num * pow(origin_scale, i)
    return decimal_num
