import structlog

from config.logging.processors import add_app_name, add_tenant_schema

# prepare data to the log
shared_processors = [
    add_tenant_schema,
    structlog.contextvars.merge_contextvars,
    add_app_name,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
]

# Configure structlog to wrap standard python logging
structlog.configure(
    processors=shared_processors + [
        # Prepare event dict for `ProcessorFormatter` in LOGGING dict
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # OLD FORMATTER (Kept exactly as it is log.log)
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%d/%b/%Y %H:%M:%S",
        },
        # NEW FORMATTER (For .json)
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
            # allows logging calls (like logger.info("txt")) to be converted to JSON
            "foreign_pre_chain": shared_processors,
        },
    },
    "handlers": {
        # OLD HANDLER (using "verbose" text format)
        "default": {
            "level": "DEBUG",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": "logs/job-platform-api.log",
            "when": "midnight",
            "interval": 1,
            "backupCount": 10,
            "formatter": "verbose",
            "delay": True,
        },
        # NEW HANDLER (using JSON format)
        "json_file": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": "logs/job-platform-api.json",
            "when": "midnight",
            "interval": 1,
            "backupCount": 10,
            "formatter": "json_formatter",
            "delay": True,
        },
    },
    "loggers": {
        "": {
            "handlers": ["default", "json_file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
