import logging
from pythonjsonlogger import jsonlogger
import sys
from contextvars import ContextVar

# Context variable to store request ID for logging
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add basic fields
        if not log_record.get('timestamp'):
            log_record['timestamp'] = self.formatTime(record, self.datefmt)
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
            
        # Add correlation ID
        req_id = request_id_var.get()
        if req_id:
            log_record['request_id'] = req_id

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    # Prevent adding multiple handlers if logger is already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logHandler = logging.StreamHandler(sys.stdout)
        
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
        logHandler.setFormatter(formatter)
        logger.addHandler(logHandler)
        
        # Propagate to root logger
        logger.propagate = False
        
    return logger