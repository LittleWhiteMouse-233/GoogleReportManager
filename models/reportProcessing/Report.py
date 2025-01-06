import os
import pandas as pd
import bs4
from bs4 import BeautifulSoup
import json
from fuzzywuzzy import process
from .Base import Base
from . import utils


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
        'dir': '',
        'result': 'test_result_failures_suite.html',
        'all_result': 'test_result.html',
        'device_info': os.path.join('device-info-files', 'PropertyDeviceInfo.deviceinfo.json'),
    }

    def __init__(self, report_dir: str):
        super().__init__()
        self.logger.info("Report loading start.")
        report_path = utils.absolute_path(report_dir)
        self.__AP = self.__key_path(report_path)
        for path in self.__AP.values():
            if not os.path.exists(path):
                self.logger.warning("Key path: [%s] does not exists.", path)
        self.__summary, self.__failed, self.__incomplete = self.__load_report_result(self.__AP['result'])
        self.__device_info = self.__load_device_info(self.__AP['device_info'])
        self.__suite_name = self.__determine_suite(self.search_summary('Suite / Plan'))
        self.__case_result = self.__analyse_case_result()
        self.__module_result = self.__analyse_module_result()
        self.__verify_data()
        self.logger.info("Report loading completed.(suite: [%s], result: [%s])",
                         self.__suite_name, self.__case_result[0])

    @classmethod
    def __key_path(cls, report_path: str):
        absolute_path = {}
        list(map(lambda x: absolute_path.update({x[0]: os.path.join(report_path, x[1])}), cls.__key_RP.items()))
        return absolute_path

    @classmethod
    def is_report(cls, report_path: str):
        key_path = cls.__key_path(report_path)

        def func_assert():
            assert os.path.exists(key_path['result'])
            assert os.path.exists(key_path['all_result'])

        return cls.try_except(func_assert, log=False)

    def __verify_data(self):
        def func_assert():
            assert self.__summary is not None
            if self.__failed is not None:
                assert sum(map(lambda x: x.shape[0], self.__failed.values())) == self.__case_result[2]
            if self.__incomplete is not None:
                assert self.__incomplete.shape[0] == self.__module_result[2]

        return self.try_except(func_assert)

    @staticmethod
    def __parse_summary(bs: bs4.BeautifulSoup):
        items = bs.find(attrs={'class': 'summary'}).find_all(attrs={'class': 'rowtitle'})
        keys = list(map(lambda x: x.text, items))
        values = list(map(lambda x: utils.clean_string(x.find_next_sibling().text), items))
        summary_table = pd.concat([pd.Series(keys), pd.Series(values)], axis=1)
        return summary_table

    @staticmethod
    def __parse_failed(bs: bs4.BeautifulSoup):
        failed_dict = dict()

        def load_module(tag: bs4.Tag):
            module = tag.find(attrs={'class': 'module'})
            module_name = module.text
            table_head = module.find_parent().find_next_sibling()
            case_table = pd.DataFrame(map(lambda x: load_case(x), table_head.find_next_siblings()))
            case_table.columns = list(table_head.stripped_strings)
            return {module_name: case_table}

        def load_case(tag: bs4.Tag):
            return list(tag.stripped_strings)

        if bs.find(attrs={'class': 'testdetails'}):
            list(map(lambda x: failed_dict.update(load_module(x)), bs.find_all(attrs={'class': 'testdetails'})))
        else:
            return None
        return failed_dict

    @staticmethod
    def __parse_incomplete(bs: bs4.BeautifulSoup):
        incomplete = bs.find(attrs={'class': 'incompletemodules'})
        if not incomplete:
            return None
        module_list = list(incomplete.stripped_strings)
        incomplete_series = pd.Series(module_list[1:], name=module_list[0])
        return incomplete_series

    @classmethod
    def __load_report_result(cls, filepath: str):
        cls.logger.info("Loading report result from: %s.", filepath)
        if not os.path.exists(filepath):
            cls.logger.error("Path does not exists!")
            raise FileExistsError
        with cls.__open_r_utf8(filepath) as f:
            bs = BeautifulSoup(f, 'lxml')
        summary = cls.__parse_summary(bs)
        if summary is None:
            cls.logger.warning("Unable to load summary.")
        else:
            cls.logger.info("Loaded summary.")
        failed = cls.__parse_failed(bs)
        if failed is None:
            cls.logger.info("No failed.")
        else:
            cls.logger.info("Loaded failed: [%d] module(s) with [%d] case(s).",
                            len(failed), sum(map(lambda x: x.shape[0], failed.values())))
        incomplete = cls.__parse_incomplete(bs)
        if incomplete is None:
            cls.logger.info("No Incomplete.")
        else:
            cls.logger.info("Loaded incomplete: [%d] module(s).", incomplete.size)
        cls.logger.info("Loading report result completed.")
        return summary, failed, incomplete

    @classmethod
    def __load_device_info(cls, filepath: str):
        cls.logger.info("Loading device info from: %s.", filepath)
        if not os.path.exists(filepath):
            cls.logger.info("There is no device info dir.")
            return None
        with cls.__open_r_utf8(filepath) as f:
            js: dict = json.load(f)
        prop_table = pd.DataFrame(js['ro_property'])
        exist_prop = prop_table[prop_table['name'].isin(cls.__ro_property)].reset_index(drop=True)
        target_prop = pd.merge(exist_prop, pd.Series(cls.__ro_property, name='name'), how='right', on='name')
        target_prop.fillna('/', inplace=True)
        cls.logger.info("Loading device info completed.(total [%d] prop, found [%d] prop)",
                        len(cls.__ro_property), exist_prop.shape[0])
        return target_prop

    @classmethod
    def look_over_suite_name(cls, filepath: str):
        with cls.__open_r_utf8(filepath) as f:
            bs = BeautifulSoup(f, 'lxml')
        summary = cls.__parse_summary(bs)
        suite_plan = ''
        if summary is not None:
            value, result, _ = cls.__search_map_table(summary, 'Suite / Plan')
            if result:
                suite_plan = value
        return cls.__determine_suite(suite_plan)

    @staticmethod
    def __open_r_utf8(filepath: str):
        return open(filepath, 'r', encoding='UTF-8')

    @staticmethod
    def __search_map_table(map_table: pd.DataFrame, keyword: str):
        if type(map_table) is not pd.DataFrame:
            map_table = pd.DataFrame(map_table)
        best_match = process.extract(keyword, map_table.iloc[:, 0], limit=1)
        key, score, index = best_match[0]
        if score > 80:
            value = map_table.iloc[index, 1]
            return value, True, key
        else:
            return '', False, ''

    def search_summary(self, keyword: str):
        if self.__summary is None:
            self.logger.error("Unable to search because summary is None.")
            raise ValueError
        value, result, key = self.__search_map_table(self.__summary, keyword)
        if result:
            self.logger.debug("Found summary value[%s] of key[%s] by keyword[%s].", value, key, keyword)
            return value
        else:
            self.logger.warning("No key matching keyword[%s] in summary.", keyword)
            return ''

    @staticmethod
    def __determine_suite(suite_plan: str):
        if not (type(suite_plan) is str and '/' in suite_plan):
            return 'Unknown'
        suite, plan, *_ = list(map(lambda x: x.strip().upper(), suite_plan.split('/')))
        if suite in plan:
            return suite
        else:
            return plan

    @staticmethod
    def __try_str2num(num_str: str, invalid: int = None):
        try:
            num = int(num_str.strip())
        except ValueError:
            if type(invalid) is int:
                return invalid
            else:
                return num_str
        else:
            return num

    def __analyse_case_result(self):
        passed_num: int = self.__try_str2num(self.search_summary('Tests Passed'), invalid=-1)
        failed_num: int = self.__try_str2num(self.search_summary('Tests Failed'), invalid=-1)
        if failed_num > 0:
            result = 'Fail'
        elif failed_num == 0:
            result = 'Pass'
        else:
            result = 'Uncertain'
        return result, passed_num, failed_num

    def __analyse_module_result(self):
        total: int = self.__try_str2num(self.search_summary('Modules Total'), invalid=-1)
        done: int = self.__try_str2num(self.search_summary('Modules Done'), invalid=-1)
        if total > done > 0:
            incomplete = total - done
        else:
            incomplete = -1
        return total, done, incomplete

    def judge_case_pass(self, failed_dict: dict[str, pd.DataFrame]):
        with self.__open_r_utf8(self.__AP['all_result']) as f:
            bs = BeautifulSoup(f, 'lxml')
        module_table = bs.find(name='table', attrs={'class': 'testsummary'}).find_all('tr')

        def load_href(a: bs4.Tag):
            try:
                return a['href']
            except KeyError:
                return ''

        module_href = dict()
        module_href.update(
            map(lambda x: (utils.clean_string(x.find('a').text), load_href(x.find('a'))), module_table[1:]))
        drop_dict = dict()
        for origin_module_name, failed_cases in failed_dict.items():
            module_name = utils.clean_string(origin_module_name)
            if module_name not in module_href.keys():
                continue
            href = module_href[module_name]
            if href[0] == '#':
                module_case = bs.find(attrs={'name': href[1:]}).find_parent(attrs={'class': 'testdetails'})
            else:
                mbs = BeautifulSoup(self.__open_r_utf8(os.path.join(self.__AP['dir'], str(href))), 'lxml')
                module_case = mbs.find('table', attrs={'class': 'testdetails'})
            case_row = module_case.find_all(attrs={'class': 'testname'})
            case_result = dict()
            case_result.update(map(lambda x: (utils.clean_string(x.text), *x.find_next_sibling()['class']), case_row))
            drop_list = []
            for i, origin_case_name in enumerate(failed_cases.iloc[:, 0]):
                case_name = utils.clean_string(origin_case_name)
                if case_name not in case_result.keys():
                    continue
                if case_result[case_name] == 'pass':
                    drop_list.append(i)
            if len(drop_list) != 0:
                drop_dict[origin_module_name] = drop_list
        return drop_dict

    # deprecation
    def __judge_case_pass(self, module_name: str, case_name: str):
        module_name = utils.clean_string(module_name)
        case_name = utils.clean_string(case_name)
        with self.__open_r_utf8(self.__AP['all_result']) as f:
            bs = BeautifulSoup(f, 'lxml')
        module_table = bs.find(name='table', attrs={'class': 'testsummary'}).find_all('tr')

        def load_href(a: bs4.Tag):
            try:
                return a['href']
            except KeyError:
                return ''

        module_href = dict()
        module_href.update(
            map(lambda x: (utils.clean_string(x.find('a').text), load_href(x.find('a'))), module_table[1:]))
        if module_name not in module_href.keys():
            return False
        href = module_href[module_name]
        if href[0] == '#':
            module_case = bs.find(attrs={'name': href[1:]}).find_parent(attrs={'class': 'testdetails'})
        else:
            mbs = BeautifulSoup(self.__open_r_utf8(os.path.join(self.__AP['dir'], str(href))), 'lxml')
            module_case = mbs.find('table', attrs={'class': 'testdetails'})
        case_row = module_case.find_all(attrs={'class': 'testname'})
        case_result = dict()
        case_result.update(map(lambda x: (utils.clean_string(x.text), *x.find_next_sibling()['class']), case_row))
        if case_name not in case_result.keys():
            return False
        if case_result[case_name] == 'pass':
            return True
        else:
            return False

    def judge_module_done(self, incomplete_module: pd.DataFrame):
        with self.__open_r_utf8(self.__AP['result']) as f:
            bs = BeautifulSoup(f, 'lxml')
        done_modules = bs.find(name='table', attrs={'class': 'testsummary'}).find_all(string='true')
        done_module_names = list(
            map(lambda x: utils.clean_string(x.find_parent().find_parent().find().string), done_modules))
        drop_list = []
        for i, origin_module_name in enumerate(incomplete_module.iloc[:, 0]):
            module_name = utils.clean_string(origin_module_name)
            if module_name in done_module_names:
                drop_list.append(i)
        return drop_list

    # deprecation
    def __judge_module_done(self, module_name: str):
        with self.__open_r_utf8(self.__AP['result']) as f:
            bs = BeautifulSoup(f, 'lxml')
        done_modules = bs.find(name='table', attrs={'class': 'testsummary'}).find_all(string='true')
        done_module_names = list(
            map(lambda x: utils.clean_string(x.find_parent().find_parent().find().string), done_modules))
        if utils.clean_string(module_name) in done_module_names:
            return True
        else:
            return False

    def get_dir_name(self):
        return self.__AP['dir']

    def get_suite_name(self):
        return self.__suite_name

    def get_case_result(self):
        return self.__case_result

    def get_module_result(self):
        return self.__module_result

    def get_summary(self):
        self.logger.debug("Getting summary table from [%s].", self.__AP['dir'])
        if self.__summary is None:
            self.logger.error("Unable to get summary because data is None.")
            raise ValueError
        summary_table: pd.DataFrame = self.__summary.copy()
        return summary_table

    def get_failed(self):
        self.logger.debug("Getting failed table from [%s].", self.__AP['dir'])
        if self.__failed is None:
            self.logger.debug("There is no failed data.")
            return None
        failed_dict = dict()
        for key, value in self.__failed.items():
            failed_dict[key] = value.copy()
        return failed_dict

    def get_incomplete_table(self):
        self.logger.debug("Getting incomplete table from [%s].", self.__AP['dir'])
        if self.__incomplete is None:
            self.logger.debug("There is no incomplete data.")
            return None
        incomplete_table = pd.DataFrame(self.__incomplete.copy())
        return incomplete_table

    def get_device_info_table(self):
        self.logger.debug("Getting device info table from [%s].", self.__AP['dir'])
        if self.__device_info is None:
            self.logger.debug("There is no device info data.")
            return None
        device_info_table = self.__device_info.copy()
        device_info_table.columns = ['ro_property', self.__suite_name]
        return device_info_table
