import os
from .Report import Report
from . import utils


class ReportPath:
    def __init__(self, report: Report, keep_report=False):
        self.__real = report.report_path
        self.__logical = self.__real
        self.__suite_name = report.suite_name
        self.__miss_rp = report.check_path(show_log=False)
        self.__dir_name = report.start_datetime.strftime('%Y.%m.%d_%H.%M.%S')
        if keep_report:
            self.__report = report
        else:
            self.__report = None

    def update_logical(self, base_path: str, replace_path: str):
        utils.CheckPath.assert_start_with(self.__logical, base_path)
        self.__logical = '::'.join([replace_path, self.__logical[len(base_path):]])

    @property
    def real(self):
        return self.__real

    @property
    def logical(self):
        return self.__logical

    @property
    def suite_name(self):
        return self.__suite_name

    @property
    def miss_rp(self):
        return self.__miss_rp

    @property
    def dir_name(self):
        return self.__dir_name

    @property
    def report(self):
        if self.__report is None:
            raise ValueError("If you want the ReportPath to come with Report, with_report should be set to True.")
        self.__report: Report
        return self.__report


class ReportFinder:
    def __init__(self, target_path: str, flag_keep_report=False):
        if not os.path.exists(target_path):
            raise ValueError("The target_path is not exists, ReportFinder unable to start working.")
        self.__flag_keep_report = flag_keep_report
        self.__target = utils.absolute_path(target_path)
        self.__temp = utils.SafePath.avoid_duplicate(utils.absolute_path('temp'))
        utils.CheckPath.assert_not_existed(self.__temp)
        self.rp_list = self.__walk_dir(self.__target)

    def __walk_dir(self, dir_path: str):
        root, dirs, files = next(os.walk(dir_path))
        if Report.is_report(root):
            print("Found Report in: %s, Analyzing and generating ReportPath ..." % root)
            return [ReportPath(Report(root, show_log=False), keep_report=self.__flag_keep_report)]
        rp_list = []
        for fn in files:
            rp_list += self.__walk_file(os.path.join(root, fn))
        for dn in dirs:
            rp_list += self.__walk_dir(os.path.join(root, dn))
        return rp_list

    def __walk_file(self, file_path: str):
        if not utils.is_package(file_path):
            return []
        unpack_dir = utils.path_basename(file_path) + '_'
        unpack_path = utils.SafePath.avoid_duplicate(str(os.path.join(self.__temp, unpack_dir)))
        utils.CheckPath.assert_not_existed(unpack_path)
        utils.extract(file_path, unpack_path)
        rp_list = self.__walk_dir(unpack_path)
        for rp in rp_list:
            rp.update_logical(unpack_path, file_path)
        return rp_list

    def report_path_found(self, show_print=True):
        if len(self.rp_list) == 0:
            print("Not a single report was found.")
            return None
        if show_print:
            for rp in self.rp_list:
                print("Found [%s] Report in: %s" % (rp.suite_name, rp.logical))
            print("Total [%d] Report(s)." % len(self.rp_list))
        return self.rp_list

    def xts_report_path_found(self, show_print=True):
        if len(self.rp_list) == 0:
            print("Not a single report was found.")
            return None
        xts_path_dict = dict()
        for rp in self.rp_list:
            suite_name = rp.suite_name
            if suite_name in xts_path_dict.keys():
                xts_path_dict[suite_name].append(rp)
            else:
                xts_path_dict[suite_name] = [rp]
        if show_print:
            for suite_name, rp_list in sorted(xts_path_dict.items(), key=lambda x: x[0]):
                print("\nFound [%d] Report(s) of [%s] in:" % (len(rp_list), suite_name))
                for rp in rp_list:
                    print(rp.logical)
                    miss_rp = rp.miss_rp
                    if miss_rp:
                        print("### Missing key_rp: %s ###" % ', '.join(miss_rp))
            print("\nTotal [%d] Report(s) of [%d] suite(s).\n"
                  % (sum(map(lambda x: len(x), xts_path_dict.values())), len(xts_path_dict)))
        return xts_path_dict
