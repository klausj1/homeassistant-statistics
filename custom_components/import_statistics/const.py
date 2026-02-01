"""Consts for import_statistics integration."""

DOMAIN = "import_statistics"

ATTR_FILENAME = "filename"
ATTR_TIMEZONE_IDENTIFIER = "timezone_identifier"
ATTR_DELIMITER = "delimiter"
ATTR_DECIMAL = "decimal"
ATTR_DATETIME_FORMAT = "datetime_format"
ATTR_UNIT_FROM_ENTITY = "unit_from_entity"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_ENTITIES = "entities"
ATTR_DELTA = "delta"
ATTR_SPLIT_BY = "split_by"

TESTFILEPATHS = "tests/testfiles/"

DATETIME_DEFAULT_FORMAT = "%d.%m.%Y %H:%M"
DATETIME_INPUT_FORMAT = "%Y-%m-%d %H:%M:%S"

# Upload-related constants
UPLOAD_MAX_SIZE = 50 * 1024 * 1024  # 50 MB in bytes
UPLOAD_ALLOWED_EXTENSIONS = [".csv", ".tsv", ".json"]
UPLOAD_URL_PATH = "/api/import_statistics/upload"
