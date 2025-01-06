import logging

LOG_FORMAT = ">>> %(asctime)s [%(levelname)s] %(module)s:%(name)s.%(funcName)s >>>\n%(message)s"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)


def to_std_and_file(name: str):
    logger = logging.getLogger(name)
    # logger.setLevel(LOG_LEVEL)
    handler_file1 = logging.FileHandler(name + '.log')
    handler_file1.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    handler_file1.setFormatter(formatter)
    logger.addHandler(handler_file1)
    handler_file2 = logging.FileHandler('total.log')
    handler_file2.setLevel(logging.DEBUG)
    formatter = logging.Formatter(LOG_FORMAT)
    handler_file2.setFormatter(formatter)
    logger.addHandler(handler_file2)
    # handler_stdout = logging.StreamHandler()
    # handler_stdout.setFormatter(formatter)
    # logger.addHandler(handler_stdout)
    return logger
