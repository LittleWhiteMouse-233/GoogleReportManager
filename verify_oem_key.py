import argparse
import pandas as pd
import time
from openpyxl import Workbook
from models.reportProcessing2 import Report, ReportFinder
from models.reportProcessing2 import workbookProcess as wbP


def matching_brand(reference_table: pd.DataFrame, brand: str):
    row_num, col_num = reference_table.shape
    for i in range(row_num):
        for j in range(col_num):
            content = reference_table.iloc[i, j]
            if type(content) is not str:
                continue
            if content.strip() == brand:
                return str(content), str(reference_table.iloc[i, j + 1])
    return None, None


def create_device_info_sheet(di_list: list[pd.DataFrame]):
    sheet = di_list[0]
    on_column = sheet.columns[0]
    for di in di_list[1:]:
        sheet = pd.merge(sheet, di, how='outer', on=on_column)
    sheet = Report.filter_property(sheet, on=on_column)
    di_sheet = wbP.b_header(sheet)
    return di_sheet


if __name__ == '__main__':
    parser = argparse.ArgumentParser(usage='--dir <path> --map <filepath>',
                                     description='GoogleReportManager v2.2.1.\nPower by sen7.huang.')
    parser.add_argument('--dir', type=str, required=True,
                        help="Path of the Report(s).(absolute path is preferred)")
    parser.add_argument('--map', type=str, required=True,
                        help="Mapping table between brand and oem.key.")
    # args = parser.parse_args([
    #     '--dir', r"E:\ProjectPyCharm\MOKA_IP\GoogleReportManager\GoogleReports\51M_JP2K SPL0805\0813\tvts",
    #     '--map', r".\参考\附件二RT2841A_GTV 派生品牌oem.key.xlsx",
    # ])
    args = parser.parse_args()
    ref_map = pd.read_excel(args.map, header=None)
    report_finder = ReportFinder(args.dir, flag_keep_report=True)
    report_path_list = report_finder.report_path_found(show_print=False)
    if not report_path_list:
        print("No Report has been loaded.")
        exit()
    device_info_list = []
    kw_f = 'ro.build.fingerprint'
    kw_o = 'ro.oem.key1'
    for report_path in report_path_list:
        report = report_path.report
        device_info = report.get_device_info_table()
        if device_info is None:
            print("\nFound [%s] Report in: %s, but without device_info." % (report.suite_name, report_path.logical))
            continue
        print("\nFound [%s] Report with device_info in: %s." % (report.suite_name, report_path.logical))
        fingerprint = str(report.search_device_info(kw_f))
        oem_key = str(report.search_device_info(kw_o))
        match_brand, match_oem_key = matching_brand(ref_map, fingerprint.split(':')[0])
        match_result = oem_key == match_oem_key
        print("ro.build.fingerprint: %s" % fingerprint)
        print("Match brand: %s" % match_brand)
        print("ro.oem.key1: %s" % oem_key)
        print("Match oem_key: %s" % match_oem_key)
        print("Verify result: %s" % match_result)
        device_info.columns = [device_info.columns[0], report_path.logical]
        if match_brand is None:
            device_info = wbP.highlight_map_table(device_info, kw_f, wbP.Style.WARNING)
        if not match_result:
            device_info = wbP.highlight_map_table(device_info, kw_o, wbP.Style.WRONG)
        device_info_list.append(device_info)
    if not device_info_list:
        print("There are %d Report loaded, but no valid device_info." % len(report_path_list))
        exit()
    device_info_sheet = create_device_info_sheet(device_info_list)
    workbook = Workbook()
    worksheet = workbook.active
    column_width = {}
    column_width.update(map(lambda x: (x, 50), range(1, device_info_sheet.shape[1] + 1)))
    worksheet = wbP.enter_sheet(worksheet, device_info_sheet, column_width=column_width)
    workbook.worksheets[0] = worksheet
    savefile = '.'.join(["oem_keyVerificationReport", time.strftime('%Y.%m.%d_%H.%M.%S'), 'xlsx'])
    workbook.save(savefile)
    print("The verified device info sheet is save as: %s." % savefile)
