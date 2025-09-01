import logging


class CustomLogFormatter(logging.Formatter):
    """
    https://stackoverflow.com/a/56944256/435093
    """

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    # strformat = (
    #     "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    # )
    strformat = "%(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + strformat + reset,
        logging.INFO: grey + strformat + reset,
        logging.WARNING: yellow + strformat + reset,
        logging.ERROR: red + strformat + reset,
        logging.CRITICAL: bold_red + strformat + reset,
    }

    def format(self, record) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
