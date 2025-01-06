import logging
from typing import Callable
from . import configLog


class Base:
    logger: logging.Logger = logging.getLogger()

    def __init__(self):
        self.config()

    @classmethod
    def config(cls, logger: logging.Logger = None):
        if logger is not None:
            cls.logger = logger
        name = cls.__name__
        if cls.logger.name != name:
            logger = configLog.to_std_and_file(name)
            logger.debug("[%s] start logging.", name)
            cls.logger = logger

    @classmethod
    def try_except(cls, func_assert: Callable, log=True):
        try:
            func_assert()
        except AssertionError:
            if log:
                cls.logger.exception("Assert Failed!")
            return False
        else:
            return True
