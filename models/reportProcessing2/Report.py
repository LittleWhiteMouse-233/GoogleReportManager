import os
import pandas as pd
import bs4
from bs4 import BeautifulSoup
import json
import fuzzywuzzy.process as fuzzysearch
import dateutil.parser as dateparser
import re
from .Base import Base
from .ModuleCase import Module, CaseResult, Case
from . import utils


class ReportLoader:
    @staticmethod
    def open_r_utf8(filepath: str):
        return open(filepath, 'r', encoding='UTF-8')

    @staticmethod
    def load_summary_from_xml(bs: bs4.BeautifulSoup):
        res = bs.find('Result')
        summ = bs.find('Summary')
        build = bs.find('Build')
        summary = {
            'Suite / Plan': ' / '.join([res['suite_name'], res['suite_plan']]),
            'Suite / Build': ' / '.join([res['suite_version'], res['suite_build_number']]),
            'Host Info': 'Result/@start %s (%s - %s)' % (res['host_name'], res['os_name'], res['os_version']),
            'Start time / End Time': ' / '.join([res['start_display'], res['end_display']]),
            'Tests Passed': summ['pass'],
            'Tests Failed': summ['failed'],
            'Modules Done': summ['modules_done'],
            'Modules Total': summ['modules_total'],
            'Fingerprint': build['build_fingerprint'],
            'Security Patch': build['build_version_security_patch'],
            'Release (SDK)': '%s (%s)' % (build['build_version_release'], build['build_version_sdk']),
            'ABIs': build['build_abis'],
        }
        summary: dict[str, str]
        return summary

    @staticmethod
    def load_result_from_xml(bs: bs4.BeautifulSoup):
        module_tag_list = bs.find_all('Module')
        module_list = list(map(lambda x: Module(x), module_tag_list))
        return module_list

    @classmethod
    def load_device_info(cls, filepath: str):
        if not os.path.exists(filepath):
            return None
        with cls.open_r_utf8(filepath) as js_f:
            js_str = ''.join(js_f.readlines())
        # 反转义反斜杠
        js_str = js_str.replace(r'\/', '\\\\/')
        js: dict = json.loads(js_str)
        total_prop = pd.DataFrame(js['ro_property'])
        target_prop = Report.filter_property(total_prop, on='name')
        return target_prop

    @staticmethod
    def __reverse_timezone(time_str: str):
        match_tz = re.search(r'[A-Z]*[+-][0-9]+', time_str)
        if match_tz is None:
            return time_str
        tz_str = match_tz.group()
        match_sign = re.search(r'[+-]', tz_str)
        # if tz_str[:match_sign.start()] not in pytz.all_timezones:
        #     return time_str
        if tz_str[:match_sign.start()] == '':
            return time_str
        sign = tz_str[match_sign.start()]
        if sign == '+':
            new_tz = tz_str.replace(sign, '-')
        elif sign == '-':
            new_tz = tz_str.replace(sign, '+')
        else:
            raise ValueError("Sign: [%s] should be \'+\' or \'-\'." % sign)
        return time_str[:match_tz.start()] + new_tz + time_str[match_tz.end():]

    @classmethod
    def __replace_month(cls, time_str: str):
        match_m = re.search(r'[0-9]{1,2}月', time_str)
        if match_m is None:
            return time_str
        cm = cls.AdditionParserInfo.CHINESE_MONTHS[int(match_m.group()[:-1]) - 1]
        return time_str[:match_m.start()] + cm + time_str[match_m.end():]

    class AdditionParserInfo(dateparser.parserinfo):
        CHINESE_MONTHS = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月',
                          '十二月']
        CHINESE_WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

        def __init__(self):
            months = self.MONTHS
            assert len(self.CHINESE_MONTHS) == len(months)
            for i in range(len(months)):
                months[i] = months[i] + (self.CHINESE_MONTHS[i],)
            self.MONTHS = months
            weekdays = self.WEEKDAYS
            assert len(self.CHINESE_WEEKDAYS) == len(weekdays)
            for i in range(len(weekdays)):
                weekdays[i] = weekdays[i] + (self.CHINESE_WEEKDAYS[i],)
            self.WEEKDAYS = weekdays
            super().__init__()

    @classmethod
    def parse_time_str(cls, time_str: str):
        tzinfo = {
            'CST': 'UTC+8',
            'HKT': 'UTC+8',
            'AST': 'UTC-4',
            'MYT': 'UTC+8',
        }
        time_str = cls.__replace_month(cls.__reverse_timezone(time_str))
        return dateparser.parse(time_str, tzinfos=tzinfo, parserinfo=cls.AdditionParserInfo())


class ReportVerifier:
    def __init__(self, html_file: str):
        self.__html = html_file
        with ReportLoader.open_r_utf8(self.__html) as html_f:
            self.__html_bs = BeautifulSoup(html_f, 'lxml')

    @staticmethod
    def __clean_string(string: str):
        # string = re.sub(r'[\n\r]+', r'<br/>', string)
        # string = re.sub(r'[ \f\t\v]+', ' ', string)
        string = re.sub(r'\s+', ' ', string)
        string = re.sub(r'\s+$', '', string)
        string = re.sub(r'^\s+', '', string)
        string = re.sub(r'&amp;', '&', string)
        string = re.sub(r'<br/>', '\n', string)
        string = re.sub(r'<.*?>', '', string)
        return string

    def verify_summary(self, summary: dict[str, str]):
        items = self.__html_bs.find('table', attrs={'class': 'summary'}).find_all('td', attrs={'class': 'rowtitle'})
        for row_title in items:
            key = row_title.text
            if key not in summary.keys():
                raise KeyError("Summary miss key: %s." % key)
            value = self.__clean_string(row_title.find_next_sibling().text)
            if summary[key] != value:
                raise ValueError("Summary value of %s verify failed: %s != %s." % (key, summary[key], value))

    @staticmethod
    def __list_module_name(module_list: list[Module]):
        return list(map(lambda x: x.module_name, module_list))

    def verify_module_result(self, module_list: list[Module]):
        items = self.__html_bs.find('table', attrs={'class': 'testsummary'}).find_all('td')
        module_name_list = self.__list_module_name(module_list)
        index = None
        for i, cell in enumerate(items):
            content: str = self.__clean_string(cell.text)
            col = i % 7 + 1
            match col:
                case 1:
                    if content not in module_name_list:
                        raise ValueError("Miss module: %s." % content)
                    index = module_name_list.index(content)
                case 2:
                    assert module_list[index].case_passed_num == int(content)
                case 3:
                    assert module_list[index].case_failed_num == int(content)
                case 4:
                    assert module_list[index].case_assumption_failure_num == int(content)
                case 5:
                    assert module_list[index].case_ignored_num == int(content)
                case 6:
                    assert module_list[index].case_total_num == int(content)
                case 7:
                    assert str(module_list[index].done_bool).upper() == content.upper()
                case _:
                    raise ValueError("Unexpected match: %s." % col)

    def verify_failed(self, module_list: list[Module]):
        failed_dict = {}
        items = self.__html_bs.find_all('table', attrs={'class': 'testdetails'})
        if not items:
            return
        module_name_list = self.__list_module_name(module_list)
        for table in items:
            module_name = self.__clean_string(table.find('td', attrs={'class': 'module'}).text)
            failed_dict[module_name] = []
            if module_name not in module_name_list:
                raise ValueError("Miss module: %s." % module_name)
            test_name_list = table.find_all('td', attrs={'class': 'testname'})
            for test_name in test_name_list:
                case_name = self.__clean_string(test_name.text)
                failed_dict[module_name].append(case_name)
                case = module_list[module_name_list.index(module_name)].find_case_by_name(case_name)
                if case is None:
                    raise ValueError("Miss case: %s in module %s." % (case_name, module_name))
                case: Case
                case_result = case.result_enum
                if case_result is not CaseResult.FAILED:
                    raise AssertionError("Case %s in module %s should be FAILED, but get CaseResult: %s."
                                         % (case_name, module_name, case_result))
        return failed_dict

    def verify_incomplete(self, module_list: list[Module]):
        items = self.__html_bs.find('table', attrs={'class': 'incompletemodules'})
        if not items:
            return
        module_name_list = self.__list_module_name(module_list)
        for name in items.find_all('td'):
            module_name = self.__clean_string(name.text)
            if module_name not in module_name_list:
                raise ValueError("Miss module: %s." % module_name)
            module_result = module_list[module_name_list.index(module_name)].done_bool
            if module_result:
                raise AssertionError("Module %s should be incomplete, but get done_bool: %s."
                                     % (module_name, module_result))


class Report(Base):
    __ro_property = [
        "ro.software.version_id",
        "ro.build.fingerprint",
        "ro.oem.key1",
        "ro.build.representative.fingerprint",
        "ro.com.google.clientidbase",
        "ro.vendor.build.fingerprint",
        "ro.build.date",
        "ro.build.version.security_patch",
        "ro.build.version.incremental",
    ]
    __key_RP = {
        'html_result': 'test_result_failures_suite.html',
        'all_result': 'test_result.html',
        'xml_result': 'test_result.xml',
        'device_info': os.path.join('device-info-files', 'PropertyDeviceInfo.deviceinfo.json'),
    }

    __exemption = {
        'no_variant': ["CTS_VERIFIER"],
        'only_xml': ["CTS_VERIFIER"],
        'no_device_info': ["CTS_VERIFIER", 'STS'],
    }

    def __init__(self, report_dir: str, identify_name: str = None, show_log=True):
        super().__init__()
        self.identify_name = str(identify_name)
        self.__report_path = utils.absolute_path(report_dir)
        with ReportLoader.open_r_utf8(self.__key_ap('xml_result')) as xml_f:
            xml_bs = BeautifulSoup(xml_f, 'xml')
        try:
            suite_name = xml_bs.find('Result')['suite_variant']
        except KeyError as ke:
            suite_name = xml_bs.find('Result')['suite_name']
            if suite_name not in self.__exemption['no_variant']:
                raise ke
        self.__suite_name: str = suite_name
        if show_log:
            self.logger.info("Loading Report from: %s as [%s]" % (self.__report_path, self.__suite_name))
        self.check_path(show_log)
        self.__start_display = ReportLoader.parse_time_str(xml_bs.find('Result')['start_display'])
        self.__start_timestamp = int(xml_bs.find('Result')['start']) / 1000
        self.__summary = ReportLoader.load_summary_from_xml(xml_bs)
        self.__module_list = ReportLoader.load_result_from_xml(xml_bs)
        self.__device_info = ReportLoader.load_device_info(self.__key_ap('device_info'))
        self.__verify(xml_bs)

    def __key_ap(self, rp_key: str):
        return str(os.path.join(self.__report_path, self.__key_RP[rp_key]))

    def check_path(self, show_log=True):
        miss_rp = []
        for key, value in self.__key_RP.items():
            if self.__suite_name in self.__exemption['only_xml']:
                if key != 'xml_result':
                    continue
            if self.__suite_name in self.__exemption['no_device_info']:
                if key == 'device_info':
                    continue
            key_ap = self.__key_ap(key)
            if not os.path.exists(key_ap):
                if key == 'xml_result':
                    raise ValueError("Invalid Report path: [%s] does not exists." % value)
                miss_rp.append(value)
        if show_log and len(miss_rp) > 0:
            self.logger.warning("Report of [%s] in %s\n\tMiss key_rp:\n\t\t%s",
                                self.__suite_name,
                                self.__report_path,
                                '\n\t\t'.join(miss_rp))
        return miss_rp

    @classmethod
    def is_report(cls, report_dir: str):
        report_path = utils.absolute_path(report_dir)
        return os.path.exists(os.path.join(report_path, cls.__key_RP['xml_result']))

    def __verify(self, xml_bs: bs4.BeautifulSoup):
        # assert self.__start_time.timestamp() == int(xml_bs.find('Result')['start'][:-3])
        assert len(set(self.module_name_list)) == len(self.__module_list)
        summ = xml_bs.find('Summary')
        assert int(summ['pass']) == sum(map(lambda x: x.case_passed_num, self.__module_list))
        assert int(summ['failed']) == sum(map(lambda x: x.case_failed_num, self.__module_list))
        assert int(summ['modules_done']) == self.module_done_num
        assert int(summ['modules_total']) == self.module_total_num
        html_file = self.__key_ap('html_result')
        if os.path.exists(html_file):
            report_verifier = ReportVerifier(html_file)
            report_verifier.verify_summary(self.__summary)
            report_verifier.verify_module_result(self.__module_list)
            report_verifier.verify_failed(self.__module_list)
            report_verifier.verify_incomplete(self.__module_list)

    @classmethod
    def filter_property(cls, prop_table: pd.DataFrame, on: str):
        target_prop = pd.merge(pd.Series(cls.__ro_property, name=on), prop_table, how='left', on=on)
        target_prop.fillna('/', inplace=True)
        return target_prop

    def search_summary(self, keyword: str):
        key, score = fuzzysearch.extractOne(keyword, self.__summary.keys())
        if score > 90:
            return self.__summary[key]
        else:
            return None

    def search_device_info(self, ro_property: str):
        if self.__device_info is None:
            return None
        _, score, index = fuzzysearch.extractOne(ro_property, self.__device_info.iloc[:, 0])
        if score > 90:
            return str(self.__device_info.iloc[index, 1])
        else:
            return None

    @property
    def suite_name(self):
        return self.__suite_name

    @property
    def report_dir(self):
        return utils.path_basename(self.__report_path)

    @property
    def report_path(self):
        return self.__report_path

    @property
    def start_datetime(self):
        return self.__start_display

    @property
    def start_timestamp(self):
        return self.__start_timestamp

    @property
    def module_name_list(self):
        return list(map(lambda x: x.module_name, self.__module_list))

    @property
    def module_total_num(self):
        return len(self.__module_list)

    def __count_module_result(self, module_result: bool):
        return list(map(lambda x: x.done_bool, self.__module_list)).count(module_result)

    @property
    def module_done_num(self):
        return self.__count_module_result(True)

    @property
    def module_incomplete_num(self):
        return self.__count_module_result(False)

    @property
    def module_total_case_num(self):
        return sum(map(lambda x: x.case_total_num, self.__module_list))

    def find_module_by_name(self, module_name: str):
        if module_name in self.module_name_list:
            return self.__module_list[self.module_name_list.index(module_name)]
        else:
            return None

    def find_case_by_module_case_name(self, module_name: str, case_name: str):
        module = self.find_module_by_name(module_name)
        if module is None:
            return None
        case = module.find_case_by_name(case_name)
        if case is None:
            return None
        return case

    def generate_module_done_map(self):
        def name_done(module: Module):
            return module.module_name, module.done_bool

        module_done_map = pd.DataFrame(list(map(lambda x: name_done(x), self.__module_list)))
        return module_done_map

    def get_summary_table(self):
        summary_table = utils.dict2map(self.__summary)
        return summary_table

    def get_device_info_table(self):
        if self.__device_info is None:
            return None
        device_info_table = self.__device_info.copy()
        device_info_table.columns = ['ro_property', self.__suite_name]
        return device_info_table

    def get_module_case_note(self):
        suite_build = self.search_summary('Suite / Build')

        def module_name_cases_note(module: Module):
            return module.module_name, module.get_cases_note()

        models_case = list(map(lambda x: "[%s]\n%s" % module_name_cases_note(x), self.__module_list))
        return '\n'.join(["{%s}" % suite_build] + models_case)
