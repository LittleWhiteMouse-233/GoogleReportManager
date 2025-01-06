import os
import shutil
import pandas as pd
import numpy as np
from .Base import Base
from .Report import Report
from . import utils
from .ModuleCase import CaseNum, ModuleNum, CaseResult, Case, Module
from . import workbookProcess as wbP


class SuiteReport(Base):
    __unpack_dir = '.unpack'

    def __init__(self, suite_dir: str, flag_unpack=False):
        self.wrong_spl = False
        self.inconsistent_summary: list[str] = []
        super().__init__()
        self.__suite_path = utils.absolute_path(suite_dir)
        report_path_list = self.valid_report_path(self.__suite_path, flag_unpack=flag_unpack)
        if len(report_path_list) == 0:
            raise NoReportException
        self.__main_report, self.__all_reports = self.__load_suite_report(report_path_list)
        self.__has_failed_record, self.__case_num = self.__merge_update_cases()
        self.__incomplete, self.__module_num = self.__merge_update_modules()
        self.__verity()
        self.__summary_diff = self.__inspect_summary()

    @classmethod
    def valid_report_path(cls, suite_path: str, flag_unpack=False):
        # 重置 .unpack
        unpack_path = os.path.join(suite_path, cls.__unpack_dir)
        if os.path.exists(unpack_path):
            shutil.rmtree(utils.SafePath.avoid_length_limited(unpack_path))
        # 搜索文件夹和文件
        root, dirs, files = next(os.walk(suite_path))
        report_path_list = []
        if flag_unpack:
            os.mkdir(unpack_path)
        for dfn in dirs + files:
            dfn_path = str(os.path.join(root, dfn))
            report_path_list += cls.__recursive_search(dfn_path, unpack_path, flag_unpack=flag_unpack)
        return report_path_list

    @classmethod
    def __recursive_search(cls, path: str, unpack_path: str, flag_unpack=False):
        def extract(_root: str, _fn: str):
            _from = os.path.join(_root, _fn)
            _to = os.path.join(unpack_path, _fn + '_')
            _to = utils.SafePath.avoid_duplicate(str(_to))
            utils.CheckPath.assert_not_existed(_to)
            utils.extract(_from, _to)
            return _to

        # 判定文件夹或文件
        if os.path.isfile(path):
            if flag_unpack and utils.is_package(path):
                path = extract(*utils.split_end(path))
            else:
                return []
        if Report.is_report(path):
            return [path]
        # 递归搜索
        root, dirs, files = next(os.walk(path))
        path_list = []
        for dfn in dirs + files:
            dfn_path = str(os.path.join(root, dfn))
            path_list += cls.__recursive_search(dfn_path, unpack_path, flag_unpack=flag_unpack)
        return path_list

    @classmethod
    def is_suite_report(cls, suite_path: str, flag_unpack=False):
        if cls.valid_report_path(suite_path, flag_unpack=flag_unpack):
            return True
        else:
            return False

    @staticmethod
    def __load_suite_report(path_list: list[str]):
        loaded_report = []
        # 加载 Report
        for path in path_list:
            report = Report(path)
            loaded_report.append(report)
        # 按报告创建时间戳由小到大（由旧到新）排序
        loaded_report.sort(key=lambda x: x.start_timestamp, reverse=False)
        max_num = 0
        main_report_index = 0
        # 查找 main_report：用例数最多的同时最旧的报告
        for i, report in enumerate(loaded_report):
            case_total_num = report.module_total_case_num
            if case_total_num > max_num:
                max_num = case_total_num
                main_report_index = i
        main_report = loaded_report[main_report_index]
        suite_name = main_report.suite_name
        valid_report = []
        # 筛选 suite_name 与 main Report 一致的 Report
        for report in loaded_report:
            if report.suite_name == suite_name:
                valid_report.append(report)
        # 按报告顺序添加 identify_name
        for i, report in enumerate(valid_report):
            if report is main_report:
                report.identify_name = 'main'
            else:
                report.identify_name = str(i)
        return main_report, valid_report

    def __verity(self):
        assert len(self.__all_reports) > 0
        if self.__case_num.is_failed():
            assert len(self.__has_failed_record) > 0

    @property
    def suite_name(self):
        return self.__main_report.suite_name

    @property
    def suite_dir(self):
        return utils.path_basename(self.__suite_path)

    @property
    def main_summary_spl(self):
        return self.search_main_summary('Security Patch')

    def search_main_device_info(self, ro_property: str):
        return self.__main_report.search_device_info(ro_property)

    def search_main_summary(self, row_title: str):
        return self.__main_report.search_summary(row_title)

    def __merge_update_cases(self):
        module_name_set = set()
        list(map(lambda x: module_name_set.update(x.module_name_list), self.__all_reports))
        case_record_list = []
        case_num = CaseNum()
        for module_name in module_name_set:
            valuable_reports = []
            case_result_map = None
            for report in self.__all_reports:
                module = report.find_module_by_name(module_name)
                if module is None:
                    continue
                module: Module
                valuable_reports.append(report)
                cr_map = module.generate_case_result_map()
                if cr_map is None:
                    assert module.case_total_num == 0
                    continue
                cr_map.columns = ['case_name', report.identify_name]
                if case_result_map is None:
                    case_result_map = cr_map
                else:
                    case_result_map = pd.merge(case_result_map, cr_map, how='outer', on=case_result_map.columns[0])
            if case_result_map is None:
                continue
            case_num.update_by_case_result_map(case_result_map)
            has_failed_row = case_result_map.iloc[:, 1:].eq(CaseResult.FAILED.result_id).any(axis=1)
            has_failed_map = case_result_map[has_failed_row]
            if has_failed_map.shape[0] == 0:
                continue
            assert has_failed_map.shape[1] == len(valuable_reports) + 1
            for i in range(has_failed_map.shape[0]):
                case_name = has_failed_map.iloc[i, 0]
                case_record = CaseRecord(case_name, module_name)
                case_record.add_records_from_case_result_series(has_failed_map.iloc[i, :], valuable_reports)
                case_record_list.append(case_record)
        assert sum(map(lambda x: int(x.still_failed()), case_record_list)) == case_num.of(CaseResult.FAILED)
        return case_record_list, case_num

    def __merge_update_modules(self):
        module_num = ModuleNum()
        module_done_map = None
        for r_i, report in enumerate(self.__all_reports):
            md_map = report.generate_module_done_map()
            md_map.columns = ['module_name', str(r_i)]
            if module_done_map is None:
                module_done_map = md_map
            else:
                module_done_map = pd.merge(module_done_map, md_map, how='outer', on=module_done_map.columns[0])
        incomplete_modules = module_done_map[~module_done_map.iloc[:, 1:].any(axis=1)]
        module_num.update(total=module_done_map.shape[0], incomplete=incomplete_modules.shape[0])
        assert incomplete_modules.shape[1] == len(self.__all_reports) + 1
        incomplete_table = pd.DataFrame(incomplete_modules.iloc[:, 0]).reset_index(drop=True)
        incomplete_table.columns = ['Incomplete Modules']
        return incomplete_table, module_num

    def __inspect_summary(self):
        check_list = ['Suite / Plan', 'Suite / Build', 'Host Info',
                      'Fingerprint', 'Security Patch', 'Release (SDK)', 'ABIs']
        summary_diff: list[list[str]] = list(map(lambda _: [], range(len(self.__all_reports))))
        for key in check_list:
            main_value = self.__main_report.search_summary(key)
            if main_value is None:
                raise KeyError("The value that needs to be checked does not exist in main Report summary: %s." % key)
            for i, report in enumerate(self.__all_reports):
                if report.search_summary(key) != main_value:
                    summary_diff[i].append(key)
        return summary_diff

    def __create_has_failed_record_table(self):
        record_detail_dict: dict[str, list[pd.DataFrame]] = dict()
        # 导出 case record 并按 module_name 分组
        for case_record in self.__has_failed_record:
            record_detail = case_record.get_record_detail()
            module_name = case_record.from_module
            if module_name in record_detail_dict.keys():
                record_detail_dict[module_name].append(record_detail)
            else:
                record_detail_dict[module_name] = [record_detail]
        if len(record_detail_dict) == 0:
            return None
        module_record_list = []
        # 按 module_name 分组合并子表
        for key, value in record_detail_dict.items():
            case_details = pd.concat(value).reset_index(drop=True)
            module_failed = pd.concat([pd.Series(key, name=case_details.columns[0]), case_details])
            module_record_list.append(module_failed)
        has_failed_record = pd.concat(module_record_list).reset_index(drop=True)
        return has_failed_record

    def __create_has_failed_detail_table(self, ref_report: Report):
        case_detail_dict: dict[str, list[pd.DataFrame]] = dict()
        # 导出 case detail 并按 module_name 分组
        for case_record in self.__has_failed_record:
            case_detail = case_record.get_case_detail_of_report(ref_report)
            # 跳过没有记录的 CaseRecord
            if case_detail is None:
                continue
            module_name = case_record.from_module
            if module_name in case_detail_dict.keys():
                case_detail_dict[module_name].append(case_detail)
            else:
                case_detail_dict[module_name] = [case_detail]
        if len(case_detail_dict) == 0:
            return None
        module_detail_list = []
        # 按 module_name 分组合并子表
        for key, value in case_detail_dict.items():
            case_details = pd.concat(value).reset_index(drop=True)
            module_title = pd.Series(wbP.add_tag(key, wbP.Style.B), name=case_details.columns[0])
            module_failed = pd.concat([module_title, case_details])
            module_detail_list.append(module_failed)
        has_failed_detail = pd.concat(module_detail_list).reset_index(drop=True)
        return has_failed_detail

    def get_suite_sheet(self):
        blank = pd.Series([np.nan])

        def bold_title(_content: str):
            return pd.Series(wbP.add_tag(_content, wbP.Style.B))

        # 合并后数值总览子表
        abstract = {
            'Suite': self.__main_report.suite_name,
            'Case (Total)': self.__case_num.total,
        }
        for cr in CaseResult:
            abstract.update({'Case (%s)' % cr.result_type: self.__case_num.of(cr)})
        abstract.update({
            'Module (Total)': self.__module_num.total,
            'Module (Done)': self.__module_num.done,
            'Module (Incomplete)': self.__module_num.incomplete,
        })
        abstract_table = pd.DataFrame(map(lambda x: (wbP.add_tag(x[0], wbP.Style.B),
                                                     wbP.add_tag(str(x[1]), wbP.Style.B)), abstract.items()))
        concat_list = [
            abstract_table,
            blank,
            bold_title("Record of CaseHasFailed: %d" % len(self.__has_failed_record)),
        ]
        # 合并后存在 Fail 记录的 Case（即 has_failed_case）在所有 Report 中的记录子表
        has_failed_record = self.__create_has_failed_record_table()
        if has_failed_record is not None:
            concat_list.append(wbP.b_header(has_failed_record))
        concat_list.append(blank)
        # 主报告的 Summary 子表，如果 SPL 有异常则红色高亮
        main_summary = self.__main_report.get_summary_table()
        if self.wrong_spl:
            main_summary = wbP.highlight_map_table(main_summary, 'Security Patch', wbP.Style.WRONG)
        # 横向校验：如果套件件 Summary 值不一致则黄色高亮
        for row_title in self.inconsistent_summary:
            main_summary = wbP.highlight_map_table(main_summary, row_title, wbP.Style.WARNING)
        concat_list.append(bold_title("Main Report Summary-[%s](from path: %s)"
                                      % (self.__main_report.identify_name, self.__main_report.report_path)))
        concat_list.append(main_summary)
        concat_list.append(blank)
        # 主报告中 has_failed_case 的 detail 子表（如果在主报告中有记录的话），没有则缺省
        has_failed_detail = self.__create_has_failed_detail_table(self.__main_report)
        if has_failed_detail is not None:
            concat_list.append(bold_title("Detail of CaseHasFailed in Report-[%s]" % self.__main_report.identify_name))
            concat_list.append(wbP.b_header(has_failed_detail))
            concat_list.append(blank)
        # 主报告中 incomplete 的 module 子表，没有则缺省
        if self.__module_num.is_incomplete():
            concat_list.append(wbP.b_header(self.__incomplete))
            concat_list.append(blank)
        concat_list.append(blank)
        # 遍历补充报告
        for i, report in enumerate(self.__all_reports):
            # 跳过主报告
            if report is self.__main_report:
                continue
            # 补充报告的 summary 子表，纵向校验：如有与主报告不一致的条目则黄色高亮
            summary = report.get_summary_table()
            for row_title in self.__summary_diff[i]:
                summary = wbP.highlight_map_table(summary, row_title, wbP.Style.WARNING)
            concat_list.append(bold_title("Additional Report Summary-[%s](from path: %s)"
                                          % (report.identify_name, report.report_path)))
            concat_list.append(summary)
            concat_list.append(blank)
            # 补充报告中 has_failed_case 的 detail 子表（如果有记录的话），没有则缺省
            has_failed_detail = self.__create_has_failed_detail_table(report)
            if has_failed_detail is not None:
                concat_list.append(bold_title("Detail of CaseHasFailed in Report-[%s]" % report.identify_name))
                concat_list.append(wbP.b_header(has_failed_detail))
                concat_list.append(blank)
            concat_list.append(blank)
        sheet = pd.concat(concat_list).reset_index(drop=True)
        return sheet

    def get_device_info_table(self):
        device_info = self.__main_report.get_device_info_table()
        if device_info is None:
            return None
        if self.wrong_spl:
            device_info = wbP.highlight_map_table(device_info, 'ro.build.version.security_patch', wbP.Style.WRONG)
        return device_info

    def get_top_table(self):
        top_dict = {
            'Version:': 'V1.3 by GRMv2.1',
            'Android OS Version:': self.__main_report.search_summary('Release (SDK)'),
            'Software Version:': '/',
            'Security Patch:': self.__main_report.search_summary('Security Patch'),
            'ABIs:': self.__main_report.search_summary('ABIs'),
            'Fingerprint:': self.__main_report.search_summary('Fingerprint'),
        }
        top_table = utils.dict2map(top_dict)
        return top_table

    def get_abstract_table(self):
        build_list = []
        note_list = []
        row_title = 'Suite / Build'
        for i, diffs in enumerate(self.__summary_diff):
            if row_title in diffs:
                report = self.__all_reports[i]
                build_list.append(report.search_summary(row_title))
                note_list.append(report.get_module_case_note())
        if self.__case_num.is_failed():
            result = wbP.add_tag('Fail', wbP.Style.RED)
        elif self.__module_num.is_incomplete():
            result = wbP.add_tag('Incomplete', wbP.Style.YELLOW)
        else:
            result = wbP.add_tag('Pass', wbP.Style.GREEN)
        abstract_dict = {
            'Suite': self.__main_report.suite_name,
            'Suite / Build': self.__main_report.search_summary('Suite / Build'),
            'Pass': self.__case_num.of(CaseResult.PASSED),
            'Fail': self.__case_num.of(CaseResult.FAILED),
            'Daily Build/Num': '\n'.join(build_list),
            'Result': result,
            'Note': wbP.add_tag('\n'.join(note_list), wbP.Style.WW),
        }
        abstract_table = pd.DataFrame([list(abstract_dict.values())], columns=list(abstract_dict.keys()))
        return abstract_table

    @staticmethod
    def get_empty_abstract_table(suite_name: str):
        abstract_dict = {
            'Suite': suite_name,
            'Suite / Build': None,
            'Pass': None,
            'Fail': None,
            'Daily Build/Num': None,
            'Result': wbP.add_tag('NA', wbP.Style.GRAY),
            'Note': None,
        }
        abstract_table = pd.DataFrame([list(abstract_dict.values())], columns=list(abstract_dict.keys()))
        abstract_table.fillna('/', inplace=True)
        return abstract_table


class CaseRecord:
    class Record:
        def __init__(self, report: Report, case: Case):
            self.report = report
            self.case = case

    def __init__(self, case_name: str, module_name: str):
        self.__case_name = case_name
        self.__module_name = module_name
        self.__records: list[CaseRecord.Record] = []

    def add_records(self, report: Report):
        case = report.find_case_by_module_case_name(self.__module_name, self.__case_name)
        if case is None:
            raise ValueError("Case(module_name = \"%s\", case_name = \"%s\") can not be found in Report: %s."
                             % (self.__module_name, self.__case_name, report.report_path))
        self.__records.append(self.Record(report, case))

    def add_records_from_case_result_series(self, case_result_series: pd.Series, ref_reports: list[Report]):
        if case_result_series.shape[0] != len(ref_reports) + 1:
            raise ValueError("Length of case_result_series should equal to num of ref_reports.")
        if case_result_series.iloc[0] != self.__case_name:
            raise ValueError("Invalid case_result_series: Wrong case_name.")
        for i in range(1, case_result_series.shape[0]):
            if pd.isna(case_result_series.iloc[i]):
                continue
            self.add_records(ref_reports[i - 1])

    @property
    def from_case(self):
        return self.__case_name

    @property
    def from_module(self):
        return self.__module_name

    @property
    def merge_result(self):
        for record in self.__records:
            case = record.case
            if case.result_enum is not CaseResult.FAILED:
                return case.result_enum
        return CaseResult.FAILED

    def still_failed(self):
        if self.merge_result is CaseResult.FAILED:
            return True
        else:
            return False

    def get_record_detail(self):
        def report_id_result_type(record: CaseRecord.Record):
            return record.report.identify_name, record.case.result_enum.result_type

        details = ', '.join(map(lambda x: "%s(%s)" % report_id_result_type(x), self.__records))
        record_detail = pd.DataFrame([[self.__case_name, self.merge_result.result_type, details]],
                                     columns=['TestName', 'FinalResultOrFail', 'RecordDetails'])
        return record_detail

    def get_case_detail_of_report(self, ref_report: Report):
        for record in self.__records:
            report, case = record.report, record.case
            if report is ref_report:
                return case.get_case_detail_table()
        return None


class NoReportException(ValueError):
    def __init__(self):
        super().__init__("No valid Report.")
