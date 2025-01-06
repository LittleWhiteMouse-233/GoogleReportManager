import bs4
from enum import Enum
import pandas as pd


class CaseResult(Enum):
    PASSED = 0, 'pass'
    FAILED = 1, 'fail'
    ASSUMPTION_FAILURE = 2, 'ASSUMPTION_FAILURE'
    IGNORED = 3, 'IGNORED'

    def __init__(self, result_id: int, result_type: str):
        self.result_id = result_id
        self.result_type = result_type


class Case:
    def __init__(self, test_tag: bs4.Tag, no_details=False):
        test_name = test_tag['name']
        testcase_name = test_tag.find_parent('TestCase')['name']
        self.__name = '#'.join([testcase_name, test_name])
        test_result = test_tag['result']
        self.__result = None
        for cr in CaseResult:
            if test_result == cr.result_type:
                self.__result = cr
        self.__details = None
        if self.__result is CaseResult.FAILED:
            failure = test_tag.find('Failure')
            if failure is not None:
                self.__details = failure['message']
            elif no_details:
                self.__details = ''
        self.__verify(test_tag)

    def __verify(self, test_tag: bs4.Tag):
        if self.__result is None:
            raise ValueError('Unexpected case result: %s, expected: %s.'
                             % (test_tag['result'], list(map(lambda x: x.result_type, CaseResult))))
        if self.__result is CaseResult.FAILED and self.__details is None:
            raise ValueError("Test result is %s, but failure details not found.", CaseResult.FAILED.result_type)

    @property
    def case_name(self):
        return self.__name

    @property
    def result_enum(self):
        return self.__result

    def get_case_detail_table(self):
        case_detail = pd.DataFrame([[self.__name, self.__result.result_type, self.__details]],
                                   columns=['TestFailed', 'Result', 'Details'])
        return case_detail.fillna('/')


class Module:
    __exemption = {
        'cts_verifier': ' '.join(["noabi", "CtsVerifier"]),
    }

    def __init__(self, module_tag: bs4.Tag):
        module_name = module_tag['name']
        module_abi = module_tag['abi']
        self.__name = ' '.join([module_abi, module_name])
        self.__done = module_tag['done']
        test_tag_list = module_tag.find_all('Test')
        if self.__name == self.__exemption['cts_verifier']:
            no_details = True
        else:
            no_details = False
        self.__case_list = list(map(lambda x: Case(x, no_details=no_details), test_tag_list))
        self.__verify(module_tag)

    def __verify(self, module_tag: bs4.Tag):
        if self.__name != self.__exemption['cts_verifier']:
            assert int(module_tag['total_tests']) == len(self.__case_list)
        assert len(set(map(lambda x: x.case_name, self.__case_list))) == len(self.__case_list)
        assert int(module_tag['pass']) == self.case_passed_num
        assert self.case_total_num == sum(list(map(lambda x: self.__count_case_result(x), CaseResult)))

    @property
    def module_name(self):
        return self.__name

    @property
    def done_bool(self):
        return self.__done == 'true'

    @property
    def case_total_num(self):
        return len(self.__case_list)

    def __count_case_result(self, case_result: CaseResult):
        return list(map(lambda x: x.result_enum, self.__case_list)).count(case_result)

    @property
    def case_passed_num(self):
        return self.__count_case_result(CaseResult.PASSED)

    @property
    def case_failed_num(self):
        return self.__count_case_result(CaseResult.FAILED)

    @property
    def case_assumption_failure_num(self):
        return self.__count_case_result(CaseResult.ASSUMPTION_FAILURE)

    @property
    def case_ignored_num(self):
        return self.__count_case_result(CaseResult.IGNORED)

    def find_case_by_name(self, case_name: str):
        case_name_list = list(map(lambda x: x.case_name, self.__case_list))
        if case_name in case_name_list:
            return self.__case_list[case_name_list.index(case_name)]
        else:
            return None

    def generate_case_result_map(self):
        if self.case_total_num == 0:
            return None

        def name_result(case: Case):
            return case.case_name, case.result_enum.result_id

        case_result_map = pd.DataFrame(list(map(lambda x: name_result(x), self.__case_list)))
        return case_result_map

    def get_cases_note(self):
        return '\n'.join(map(lambda x: x.case_name, self.__case_list))


class CaseNum:
    def __init__(self):
        self.total = 0
        for cr in CaseResult:
            if cr.result_type in self.__dict__.keys():
                raise KeyError("Key already existed, this may be because different CaseResult have same result_type.")
            self.__dict__[cr.result_type] = 0

    def update_by_case_result_map(self, case_result_map: pd.DataFrame):
        self.total += case_result_map.shape[0]
        result_map = case_result_map.iloc[:, 1:].copy()
        for cr in [CaseResult.PASSED, CaseResult.ASSUMPTION_FAILURE, CaseResult.IGNORED]:
            row_index = result_map.eq(cr.result_id).any(axis=1)
            cr_row = result_map[row_index]
            self.add_of(cr, cr_row.shape[0])
            result_map.drop(cr_row.index, inplace=True)
        failed_id = CaseResult.FAILED.result_id
        if not result_map.fillna(failed_id).eq(failed_id).all(axis=1).all():
            raise ValueError("There are still non-failed results that have not been judged.")
        self.add_of(CaseResult.FAILED, result_map.shape[0])
        self.verify()
        return result_map

    def add_of(self, case_result: CaseResult, num: int):
        self.__dict__[case_result.result_type] += num

    def of(self, case_result: CaseResult):
        return self.__dict__[case_result.result_type]

    def verify(self):
        assert self.total == sum(list(self.__dict__.values())[1:])

    def is_failed(self):
        return self.__dict__[CaseResult.FAILED.result_type] != 0


class ModuleNum:
    def __init__(self):
        self.total = 0
        self.done = 0
        self.incomplete = 0

    def update(self, total: int = None, done: int = None, incomplete: int = None):
        type_list = list(map(lambda x: type(x) is int, [total, done, incomplete]))
        if type_list.count(True) < 2:
            raise ValueError("At least two int arguments should be provided.")
        if type_list.count(True) == 3:
            if total != done + incomplete:
                raise ValueError("Total should be equal to done plus incomplete.")
        if total is None:
            total = done + incomplete
        if done is None:
            done = total - incomplete
        if incomplete is None:
            incomplete = total - done
        self.total += total
        self.done += done
        self.incomplete += incomplete
        self.verify()

    def verify(self):
        assert self.total == self.done + self.incomplete

    def is_incomplete(self):
        return self.incomplete != 0
