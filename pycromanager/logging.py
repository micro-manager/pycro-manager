import logging

logging.basicConfig(level=logging.DEBUG)
main_logger = _base_logger = logging.getLogger("pycromanager")

def set_logger_instance(logger_name: str) -> None:
    """ Replaces the default logger with a custom logger
    
    logger (str)
        name of new logger to use (i.e. logger.name)
    """
    global main_logger
    main_logger = logging.getLogger(logger_name)

def reset_logger_instance() -> None:
    """ Resets the logger to the default logger """
    set_logger_instance(_base_logger.name)