
""" Load interchange formatted data into LDAP database.
    This script accepts 2x .tsv files as inputs.
    These 2x input files are generated by the unix_to_tsv script.
"""

import csv
from logging import Logger

from applocals import LDAP_ADMIN_PASSWORD_BASE64
from common import security_helpers

def main(
        logger: Logger,
        posix_user_tsv_path: str,
        posix_group_tsv_path: str
) -> None:
    logger.debug("load_tsv::main()")

    # Read interchange formatted data from .tsv files into memory
    logger.debug('reading ' + posix_user_tsv_path)
    with open(posix_user_tsv_path) as f:
        user_tsv_rows = list(csv.reader(f, delimiter='\t'))
    logger.debug('reading ' + posix_group_tsv_path)
    with open(posix_group_tsv_path) as f:
        group_tsv_rows = list(csv.reader(f, delimiter='\t'))
    logger.info(f"found {len(user_tsv_rows)} user rows to import")
    logger.info(f"found {len(group_tsv_rows)} group rows to import")