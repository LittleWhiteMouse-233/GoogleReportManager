import os
import pandas as pd
from .Base import Base
from .Report import Report
from . import utils
from . import workbookProcess as wbP


class SuiteReport(Base):
    def __init__(self, suite_dir: str):
        super().__init__()
        self.logger.info("SuiteReport loading start.")
        self.__path_suite = utils.absolute_path(suite_dir)
        self.__paths_report = self.search_valid_report(self.__path_suite)
        if len(self.__paths_report) == 0:
            self.logger.warning("No valid report path.")
        else:
            self.logger.info("Valid report paths [%d]: \n" +
                             '\n'.join(self.__paths_report), len(self.__paths_report))
        self.__report_list, self.__main_report, self.__suite_name = self.__load_suite_report(self.__paths_report)
        self.__verify_data()
        self.__summary_list, self.__build_list = self.__merge_update_summary_table()
        self.__failed_dict = self.__merge_update_failed_table()
        self.__failed_num = 0
        if self.__failed_dict is not None:
            self.__failed_num = sum(map(lambda x: x.shape[0], self.__failed_dict.values()))
        self.__incomplete = self.__merge_update_incomplete_table()
        self.__incomplete_num = 0
        if self.__incomplete is not None:
            self.__incomplete_num = self.__incomplete.shape[0]
        self.logger.info("SuiteReport loading completed.(%s)", self.__suite_name)

    @staticmethod
    def search_valid_report(suite_path: str):
        path_list = utils.dirs_sort_by_create(suite_path, reverse=True)
        valid_paths = [path for path in path_list if Report.is_report(path)]
        return valid_paths

    @classmethod
    def is_suite_report(cls, suite_path: str):
        if cls.search_valid_report(suite_path):
            return True
        else:
            return False

    def __verify_data(self):
        def func_assert():
            assert len(self.__report_list) > 0

        return self.try_except(func_assert)

    @classmethod
    def __load_suite_report(cls, path_list: list[str]):
        cls.logger.info("Loading suite report.")
        unknown = 'Unknown'
        report_list = []
        max_total_module = 0
        main_report_index = 0
        for i, path in enumerate(path_list):
            report = Report(path)
            report_list.append(report)
            total_module = report.get_module_result()[0]
            if total_module > max_total_module:
                max_total_module = total_module
                main_report_index = i
        main_report = report_list[main_report_index]
        suite_name = main_report.get_suite_name()
        valid_report_list = []
        for i, report in enumerate(report_list):
            if i == main_report_index:
                valid_report_list.append(report)
                cls.logger.info("[%s] use main report in dir [%s].", suite_name, main_report.get_dir_name())
                continue
            sn = report.get_suite_name()
            if sn == unknown:
                cls.logger.warning("Non-main report is ignored because suite name is Unknown.")
                continue
            if sn == suite_name:
                valid_report_list.append(report)
                cls.logger.info("Loaded non-main report from dir: [%s]", report.get_dir_name())
            else:
                cls.logger.warning("Non-main report is ignored because suite name [%s] != [%s]", sn, suite_name)
        cls.logger.info("Loading [%s] suite report completed.", suite_name)
        return valid_report_list, main_report, suite_name

    def get_suite_name(self):
        return self.__suite_name

    def get_dir_name(self):
        return os.path.split(self.__path_suite)[1]

    def __merge_update_summary_table(self):
        summary_list = [self.__main_report.get_summary()]
        build_list = []
        for report in self.__report_list:
            suite_build = report.search_summary('Suite / Build')
            if suite_build != self.__main_report.search_summary('Suite / Build'):
                summary_list.append(report.get_summary())
                build_list.append(suite_build)
                self.logger.debug("Different suite versions in report from [%s].", report.get_dir_name())
        return summary_list, build_list

    def __merge_update_failed_table(self):
        all_failed: dict[str, pd.DataFrame] = dict()
        for report in self.__report_list:
            failed_dict = report.get_failed()
            if failed_dict is None:
                continue
            failed_dict: dict[str, pd.DataFrame]
            for key, value in failed_dict.items():
                if key in all_failed.keys():
                    base = all_failed[key]
                    new = value[~value.iloc[:, 0].isin(base.iloc[:, 0])]
                    all_failed[key] = pd.concat([base, new]).reset_index(drop=True)
                    self.logger.debug("Merged [%d] failed case(s) in module [%s].", new.shape[0], key)
                else:
                    all_failed[key] = value
                    self.logger.debug("Merged failed module [%s] with [%d] case(s).", key, value.shape[0])
        if len(all_failed) == 0:
            self.logger.info("No failed.")
            return None
        self.logger.info("Merged all failed: [%d] module(s) with [%d] case(s). Start updating...",
                         len(all_failed), sum(map(lambda x: x.shape[0], all_failed.values())))
        for report in self.__report_list:
            drop_failed = report.judge_case_pass(all_failed)
            if len(drop_failed) == 0:
                continue
            for module_name, drop_i in drop_failed.items():
                if len(drop_i) == 0:
                    continue
                failed_cases = all_failed[module_name]
                dropped = failed_cases.drop(failed_cases.index[drop_i]).reset_index(drop=True)
                self.logger.debug("Updated pass [%d] case(s) from module [%s].",
                                  len(drop_i), module_name)
                if dropped.shape[0] == 0:
                    all_failed.pop(module_name)
                else:
                    all_failed[module_name] = dropped
            if len(all_failed) == 0:
                self.logger.info("Updated pass all failed.")
                return None
        self.logger.info("Updated all failed: [%d] module(s) with [%d] case(s).",
                         len(all_failed), sum(map(lambda x: x.shape[0], all_failed.values())))
        return all_failed

    def __merge_update_incomplete_table(self):
        total: pd.DataFrame | None = None
        for report in self.__report_list:
            incomplete = report.get_incomplete_table()
            if incomplete is None:
                continue
            if total is None:
                total = incomplete
                continue
            new = incomplete[~incomplete.iloc[:, 0].isin(total.iloc[:, 0])]
            total = pd.concat([total, new]).reset_index(drop=True)
            self.logger.debug("Merged [%d] incomplete module(s).", new.shape[0])
        if total is None:
            self.logger.info("No incomplete module.")
            return None
        self.logger.info("Merged all incomplete: [%d] module(s). Start updating...", total.shape[0])
        for report in self.__report_list:
            drop_i = report.judge_module_done(total)
            if len(drop_i) == 0:
                continue
            dropped = total.drop(total.index[drop_i]).reset_index(drop=True)
            self.logger.debug("Updated done [%d] module(s).")
            if dropped.shape[0] == 0:
                self.logger.info("Updated done all incomplete module(s).")
                return None
            else:
                total = dropped
        self.logger.info("Updated incomplete: [%d] module(s).", total.shape[0])
        return total

    def get_suite_sheet(self):
        self.logger.info("Getting suite [%s] sheet.", self.__suite_name)
        abstract = ("[%s] Fail case(s): [%d], Incomplete module(s): [%d]" %
                    (self.__suite_name, self.__failed_num, self.__incomplete_num))
        abstract = pd.Series(wbP.add_tag(abstract, wbP.Style.B))
        concat_list = [abstract]
        title = pd.Series(wbP.add_tag('Summary', wbP.Style.B))
        for summary in self.__summary_list:
            concat_list.append(title)
            concat_list.append(summary)
        if self.__failed_dict is not None:
            module_failed = list(
                map(lambda x: pd.concat([pd.Series(x[0], name=x[1].columns[0]), x[1]]), self.__failed_dict.items()))
            failed_table = pd.concat(module_failed).reset_index(drop=True)
            concat_list.append(wbP.b_header(failed_table))
        if self.__incomplete is not None:
            concat_list.append(wbP.b_header(self.__incomplete))
        sheet = pd.concat(concat_list).reset_index(drop=True)
        self.logger.info("Got suite [%s] sheet.", self.__suite_name)
        return sheet

    def get_device_info_table(self):
        self.logger.info("Get device info of [%s].", self.__suite_name)
        return self.__main_report.get_device_info_table()

    def get_top_table(self):
        self.logger.info("Get top table of [%s].", self.__suite_name)
        table_dict = {
            'Version:': 'V1.1',
            'Android OS Version:': self.__main_report.search_summary('Release (SDK)'),
            'Software Version:': '/',
            'Security Patch:': self.__main_report.search_summary('Security Patch'),
            'ABIs:': self.__main_report.search_summary('ABIs'),
            'Fingerprint:': self.__main_report.search_summary('Fingerprint'),
        }
        top_table = pd.concat([pd.Series(table_dict.keys()), pd.Series(table_dict.values())], axis=1)
        return top_table

    def get_abstract_table(self):
        self.logger.info("Get abstract table of [%s].", self.__suite_name)
        note_list = []
        if self.__failed_dict is not None:
            note_list.append('Failed case(s):')
            for key, value in self.__failed_dict.items():
                note_f = '\n'.join(['[%s]' % key] + list(value.iloc[:, 0]))
                note_list.append(note_f)
        if self.__incomplete is not None:
            note_list.append('Incomplete module(s):')
            note_i = '\n'.join(list(self.__incomplete.iloc[:, 0]))
            note_list.append(note_i)
        table_dict = {
            'Suite': self.__suite_name,
            'Suite / Build': self.__main_report.search_summary('Suite / Build'),
            'Pass': self.__main_report.search_summary('Tests Passed'),
            'Fail': self.__failed_num,
            'Daily Build/Num': '\n'.join(self.__build_list),
            'Result': 'Pass' if self.__failed_num == self.__incomplete_num == 0 else 'Fail',
            'Note': wbP.add_tag('\n'.join(note_list), wbP.Style.WW),
        }
        abstract = pd.DataFrame([list(table_dict.values())], columns=list(table_dict.keys()))
        return abstract
