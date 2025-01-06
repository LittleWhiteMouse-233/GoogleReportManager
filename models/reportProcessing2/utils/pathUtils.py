import os
from typing import Callable


def absolute_path(path: str):
    return os.path.normpath(os.path.join('' if os.path.isabs(path) else os.getcwd(), path, ''))


def split_end(path: str):
    base_path, base_name = os.path.split(path)
    if base_name == '':
        return os.path.split(base_path)
    else:
        return base_path, base_name


def path_basename(path: str):
    return split_end(path)[1]


class LSPath:
    @staticmethod
    def __path2path_list(path: str, items_func: Callable[[str], list[str]]):
        return list(map(lambda x: os.path.join(path, x), items_func(path)))

    @staticmethod
    def paths_sort_by_create(path_list: list[str], reverse=False):
        return sorted(path_list, key=lambda x: os.path.getctime(x), reverse=reverse)

    @classmethod
    def listdir_sort_by_create(cls, path: str, reverse=False):
        return cls.paths_sort_by_create(cls.__path2path_list(path, lambda x: os.listdir(x)), reverse=reverse)

    @classmethod
    def dirs_sort_by_create(cls, path: str, reverse=False):
        return cls.paths_sort_by_create(cls.__path2path_list(path, lambda x: next(os.walk(x))[1]), reverse=reverse)

    @classmethod
    def files_sort_by_create(cls, path: str, suffix: list[str] = None, reverse=False):
        files_list = next(os.walk(path))[2]
        if suffix:
            for filename in files_list[-1::-1]:
                if os.path.splitext(filename)[1] not in suffix:
                    files_list.remove(filename)
        return cls.paths_sort_by_create(cls.__path2path_list(path, lambda _: files_list), reverse=reverse)


class CheckPath:
    @staticmethod
    def assert_not_existed(path: str):
        if os.path.exists(path):
            raise FileExistsError("The dir [%s] is already existed! "
                                  "Please delete manually if you want to overwrite it." % path)

    @staticmethod
    def assert_start_with(path: str, root: str):
        if not path.startswith(root):
            raise ValueError("Path [%s] should be start with [%s]." % (path, root))


class SafePath:
    @staticmethod
    def avoid_duplicate(path: str, pass_name: list = None):
        base_path, base_name = split_end(path)
        only_base_name = base_name
        for i in range(1, 100):
            if not (pass_name is not None and only_base_name in pass_name):
                only_dir_path = os.path.join(base_path, only_base_name)
                if not os.path.exists(only_dir_path):
                    return only_dir_path
            only_base_name = base_name + '(%d)' % i
        raise ValueError("It is too many duplicate folder.")

    @staticmethod
    def avoid_length_limited(path: str):
        abs_path = absolute_path(path)
        prefix = '\\\\?\\'
        if not abs_path.startswith(prefix):
            return '\\\\?\\' + abs_path
        else:
            return abs_path
