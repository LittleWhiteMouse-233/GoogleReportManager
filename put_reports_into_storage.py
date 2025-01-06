import os
import shutil
import argparse
from models.reportProcessing2 import ReportFinder
from models.reportProcessing2 import utils


def avoid_duplicate_dir_zip(dir_path: str):
    pass_name = []
    only_dir = dir_path
    for _ in range(100):
        only_root, only_name = utils.split_end(only_dir)
        only_zip = os.path.join(only_root, only_name + '.zip')
        if os.path.exists(only_dir) or os.path.exists(only_zip):
            pass_name.append(only_name)
        else:
            return str(only_dir), str(only_zip)
        only_dir = utils.SafePath.avoid_duplicate(dir_path, pass_name=pass_name)
    raise ValueError("It is too many duplicate folder and zip file.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(usage='-i <inPath> -o <outPath> -p <projectName> -n <nickname>',
                                     description='GoogleReportManager v2.2.1.\nPower by sen7.huang.')
    parser.add_argument('-i', '--inPath', type=str, required=True,
                        help="Path of the Report(s) to be filed.(absolute path is preferred)")
    parser.add_argument('-o', '--outPath', type=str, required=True,
                        help="Path to filed the Report(s).(absolute path is preferred)")
    parser.add_argument('-p', '--projectName', type=str, required=True,
                        help="Name of Project.")
    parser.add_argument('-n', '--nickname', type=str, required=True,
                        help="Nickname of XTS Report.")
    # args = parser.parse_args([
    #     '-i', r"E:\ProjectPyCharm\MOKA_IP\GoogleReportManager\GoogleReports\TEST",
    #     '-o', r".\Warehouse",
    #     '-p', "TestP2",
    #     '-n', "TestXTS2",
    # ])
    args = parser.parse_args()
    xts_path = utils.absolute_path(str(os.path.join(args.outPath, args.projectName, args.nickname)))
    report_finder = ReportFinder(args.inPath)
    xts_path_dict = report_finder.xts_report_path_found()
    if xts_path_dict is not None:
        command = input('\n'.join([
            "Please confirm the above information",
            "enter \'Y\' to start copying into storage: [%s]" % xts_path,
            "enter \'N\' to exit ...",
        ]))
        if command.upper() == 'Y':
            for suite_name, report_path_list in xts_path_dict.items():
                for report_path in report_path_list:
                    target_path = os.path.join(xts_path, suite_name, report_path.dir_name)
                    target_dir, target_zip = avoid_duplicate_dir_zip(str(target_path))
                    utils.CheckPath.assert_not_existed(target_dir)
                    utils.CheckPath.assert_not_existed(target_zip)
                    print("Copying: [%s]\nInto: [%s]\nWith zip: [%s]\n" % (report_path.logical, target_dir, target_zip))
                    from_path = utils.SafePath.avoid_length_limited(report_path.real)
                    shutil.copytree(from_path, utils.SafePath.avoid_length_limited(target_dir))
                    utils.pack(from_path, target_zip)
        else:
            print("The program is aborted because the input: \'%s\' is not \'Y\'." % command)
