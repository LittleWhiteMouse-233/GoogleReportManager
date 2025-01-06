import logging
import os

LOG_FORMAT = ">>> %(asctime)s [%(levelname)s] %(module)s:%(name)s.%(funcName)s >>>\n%(message)s"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
LOG_DIR = r".\runtime logs"


class Base:
    logger: logging.Logger = logging.getLogger()

    def __init__(self):
        self.config()

    @classmethod
    def config(cls, logger: logging.Logger = None):
        if logger is not None:
            cls.logger = logger
        else:
            name = cls.__name__
            if cls.logger.name != name:
                logger = cls.__init_logger(name)
                logger.debug("[%s] start logging.", name)
                cls.logger = logger

    @staticmethod
    def __init_logger(name: str):
        if not os.path.exists(LOG_DIR):
            os.mkdir(LOG_DIR)
        logger = logging.getLogger(name)
        # logger.setLevel(LOG_LEVEL)
        file_handler = logging.FileHandler(os.path.join(LOG_DIR, name + '.log'))
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        total_file = logging.FileHandler(os.path.join(LOG_DIR, 'total.log'))
        total_file.setLevel(logging.DEBUG)
        total_file.setFormatter(formatter)
        logger.addHandler(total_file)
        # handler_stdout = logging.StreamHandler()
        # handler_stdout.setFormatter(formatter)
        # logger.addHandler(handler_stdout)
        return logger
