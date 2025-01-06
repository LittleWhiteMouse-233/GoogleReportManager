import os
import argparse
import time
import shutil
from models.reportProcessing2 import XTSReport


def project_nickname(dir_path: str):
    front_path, nickname = os.path.split(dir_path)
    if nickname == '':
        front_path, nickname = os.path.split(front_path)
    project_name = os.path.basename(front_path)
    return project_name, nickname


if __name__ == '__main__':
    parser = argparse.ArgumentParser(usage='--dir <path> [--history]',
                                     description='GoogleReportManager v2.2.1.\nPower by sen7.huang.')
    parser.add_argument('--dir', type=str, required=True,
                        help="Path of the XTS Report.(absolute path is preferred)")
    parser.add_argument('--history', action='store_true',
                        help="Select to output history or not.")
    parser.add_argument('--unpack', action='store_true',
                        help="Select to load Report from package(*.zip|*.rar) or not.")
    args = parser.parse_args([
        # '--dir', r"E:\ProjectPyCharm\MOKA_IP\GoogleReportManager\GoogleReports\51M_JP2K SPL0805\0813",
        '--dir', r"E:\ProjectPyCharm\MOKA_IP\GoogleReportManager\GoogleReports\CTS+VTS",
        # '--history',
        # '--unpack',
    ])
    # args = parser.parse_args()
    xts_path: str = args.dir
    xts_report = XTSReport(xts_path, flag_unpack=args.unpack)
    workbook = xts_report.get_workbook()
    pn_name = project_nickname(xts_path)
    workbook.save(os.path.join(xts_path, '.'.join([*pn_name, time.strftime('%Y.%m.%d_%H.%M.%S'), 'xlsx'])))
    workbook.save('.'.join([*pn_name, 'xlsx']))
    if args.history:
        history_dir = '_'.join(['history', time.strftime('%Y.%m.%d_%H.%M.%S')])
        if not os.path.exists(history_dir):
            os.mkdir(history_dir)
        for filename in next(os.walk(xts_path))[2]:
            if filename.startswith('.'.join(pn_name)) and filename.endswith('.xlsx'):
                shutil.copyfile(os.path.join(xts_path, filename), os.path.join(history_dir, filename))
