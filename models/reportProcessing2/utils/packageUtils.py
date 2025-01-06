import os
import zipfile
import rarfile
from . import pathUtils
from .pathUtils import CheckPath, SafePath


def extract(from_file: str, to_dir: str):
    if zipfile.is_zipfile(from_file):
        extract_zip(from_file, to_dir)
    elif rarfile.is_rarfile(from_file):
        extract_rar(from_file, to_dir)
    else:
        raise ValueError("%s is not supported to be extracted." % from_file)


def extract_zip(from_file: str, to_dir: str):
    with zipfile.ZipFile(from_file, 'r') as zip_f:
        zip_f.extractall(SafePath.avoid_length_limited(to_dir))


def extract_rar(from_file: str, to_dir: str):
    with rarfile.RarFile(from_file, 'r') as rar_f:
        rar_f.extractall(SafePath.avoid_length_limited(to_dir))


def is_package(pkg_path: str):
    if zipfile.is_zipfile(pkg_path) or rarfile.is_rarfile(pkg_path):
        return True
    return False


def pack(from_dir: str, to_file: str):
    CheckPath.assert_not_existed(to_file)
    with zipfile.ZipFile(to_file, 'w') as zip_f:
        root_out_pkg = pathUtils.split_end(from_dir)[0]
        for root, dirs, files in os.walk(from_dir):
            CheckPath.assert_start_with(root, root_out_pkg)
            root_in_pkg = root[len(root_out_pkg):]
            for file in files:
                zip_f.write(os.path.join(root, file), os.path.join(root_in_pkg, file))
