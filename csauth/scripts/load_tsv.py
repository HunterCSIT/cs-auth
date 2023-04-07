
""" Load interchange formatted data into LDAP database.
    This script accepts 2x .tsv files as inputs.
    These 2x input files are generated by the unix_to_tsv script.
"""

from collections import Counter
import csv
from logging import Logger
from typing import List

from common.constants import (
    SKIP_FLAG
)
from common import ldap_helpers as ldap
from common import security_helpers


def _deduplicate_list(l: List[str]) -> List[str]:
    return list(set(l))


def main(
        logger: Logger,
        posix_user_tsv_path: str,
        posix_group_tsv_path: str,
        given_password: str = None,
) -> None:
    logger.debug("load_tsv::main()")
    summary = Counter()


    # Read interchange formatted data from .tsv files into memory
    logger.debug('reading ' + posix_user_tsv_path)
    if posix_user_tsv_path != SKIP_FLAG:
        with open(posix_user_tsv_path) as f:
            user_tsv_rows = list(csv.reader(f, delimiter='\t'))
    else:
        user_tsv_rows = []
    logger.info(f"found {len(user_tsv_rows)} user rows to import")


    logger.debug('reading ' + posix_group_tsv_path)
    if posix_group_tsv_path != SKIP_FLAG:
        with open(posix_group_tsv_path) as f:
            group_tsv_rows = list(csv.reader(f, delimiter='\t'))
    else:
        group_tsv_rows = []
    logger.info(f"found {len(group_tsv_rows)} group rows to import")


    with ldap.new_connection() as conn:
        logger.debug("connected to ldap server @" + conn.server.host)

        if len(user_tsv_rows):
            logger.debug("adding users")
        for user in user_tsv_rows:
            (
                username,
                uidNumber,
                gidNumber,
                hashedPw,
                fullname,
                homeDirectory,
                loginShell,
            ) = user

            if ldap.posix_user_exists(conn, username):
                logger.info(
                    f"not adding user {username}({uidNumber}) cn already exists"
                )
                summary['skipped_user_add <already exists>'] += 1
                continue

            userPassword = (
                security_helpers.hash_password(given_password)
                if given_password
                else hashedPw
            )
            entry = ldap.create_posix_user_entry_dict(
                username,
                uidNumber,
                gidNumber,
                fullname,
                homeDirectory,
                userPassword.encode('utf-8'),
                loginShell,
            )
            response = ldap.add_posix_user(conn, username, entry)
            try:
                ldap.validate_response_is_success(response)
            except ldap.LDAPCRUDError:
                logger.error(f'failed to add user {username}')
                logger.error(f'{response}')
                summary['user_errors'] += 1

                should_continue = input("press y to continue importing: ")
                if should_continue.lower().strip() == 'y':
                    logger.debug("continuing...")
                    continue
                else:
                    logger.debug("exiting...")
                    break
            else:
                logger.info(f'{username}({uidNumber}) has been added')
                summary['users_added'] += 1


        if len(group_tsv_rows):
            logger.debug("adding groups")
        for group in group_tsv_rows:
            (
                name,
                gid,
                members,
            ) = group


            if ldap.posix_group_exists(conn, name):
                logger.info(
                    f"not adding group {name}({gid}) cn already exists."
                    + "Checking membership..."
                )
                summary['skipped_group_add <already exists>'] += 1

                existing_group = ldap.get_posix_group(conn, name)
                existing_members = set(existing_group.get('memberUid', []))
                target_members = set(members.split(','))
                changes_needed = len(
                    target_members.symmetric_difference(existing_members)
                ) > 0
                if changes_needed:
                    logger.info(
                        f"updating members of group {name}({existing_group['gidNumber']})"
                    )
                    response = ldap.set_posix_group_members(
                        conn, name, list(target_members),
                    )
                    try:
                        ldap.validate_response_is_success(response)
                    except ldap.LDAPCRUDError:
                        logger.error(f'failed to modify group {name}')
                        logger.error(f'{response}')
                        summary['group_errors'] += 1

                        should_continue = input("press y to continue importing: ")
                        if should_continue.lower().strip() == 'y':
                            logger.debug("continuing...")
                            continue
                        else:
                            logger.debug("exiting...")
                            break
                    else:
                        logger.info(f'{name}({gid}) has been added')
                        summary['group_modified'] += 1
                else:
                    summary['skipped_group_modify <already up to date>'] += 1
                    logger.debug("no membership changes needed")

                continue

            # create group if it doesn't exist
            logger.info(f"adding group {name}({gid}) with members {members}")
            entry = ldap.create_posix_group_entry_dict(
                name,
                int(gid),
                _deduplicate_list(members.split(',')),
            )
            response = ldap.add_posix_group(
                conn,
                name,
                entry,
            )
            try:
                ldap.validate_response_is_success(response)
            except ldap.LDAPCRUDError:
                logger.error(f'failed to add group {name}')
                logger.error(f'{response}')
                summary['group_errors'] += 1

                should_continue = input("press y to continue importing: ")
                if should_continue.lower().strip() == 'y':
                    logger.debug("continuing...")
                    continue
                else:
                    logger.debug("exiting...")
                    break
            else:
                logger.info(f'{name}({gid}) has been added')
                summary['groups_added'] += 1

    logger.info('\n* * * * Summary * * * *\n' + '\n'.join(f'{k}:  {summary[k]}' for k in summary))
    logger.debug("bye")
