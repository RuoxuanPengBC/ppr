# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=too-few-public-methods

"""This module holds methods to support registration model updates - mostly account registration summary."""
from flask import current_app
from sqlalchemy.sql import text

from mhr_api.exceptions import DatabaseException
from mhr_api.models import utils as model_utils
from mhr_api.models.db import db
from mhr_api.models.type_tables import (
    MhrDocumentType,
    MhrDocumentTypes,
    MhrNoteStatusTypes,
    MhrRegistrationTypes,
    MhrRegistrationStatusTypes
)
from mhr_api.services.authz import MANUFACTURER_GROUP, QUALIFIED_USER_GROUP, GENERAL_USER_GROUP, BCOL_HELP
from mhr_api.services.authz import GOV_ACCOUNT_ROLE


# Account registration request parameters to support sorting and filtering.
CLIENT_REF_PARAM = 'clientReferenceId'
PAGE_NUM_PARAM = 'pageNumber'
SORT_DIRECTION_PARAM = 'sortDirection'
SORT_CRITERIA_PARAM = 'sortCriteriaName'
MHR_NUMBER_PARAM = 'mhrNumber'
DOC_REG_NUMBER_PARAM = 'documentRegistrationNumber'
REG_TYPE_PARAM = 'registrationType'
REG_TS_PARAM = 'createDateTime'
START_TS_PARAM = 'startDateTime'
END_TS_PARAM = 'endDateTime'
STATUS_PARAM = 'statusType'
SUBMITTING_NAME_PARAM = 'submittingName'
OWNER_NAME_PARAM = 'ownerName'
USER_NAME_PARAM = 'username'
EXPIRY_DAYS_PARAM = 'expiryDays'
SORT_ASCENDING = 'ascending'
SORT_DESCENDING = 'descending'

DOC_ID_COUNT_QUERY = """
SELECT COUNT(document_id)
  FROM mhr_documents
 WHERE document_id = :query_value
"""
QUERY_BATCH_MANUFACTURER_MHREG_DEFAULT = """
select r.id, r.account_id, r.registration_ts, rr.id, rr.report_data, rr.batch_storage_url
  from mhr_registrations r, mhr_manufacturers m, mhr_registration_reports rr
 where r.id = rr.registration_id
   and r.account_id = m.account_id
   and r.registration_type = 'MHREG'
   and r.registration_ts between (now() - interval '1 days') and now()
  order by r.account_id, r.mhr_number
 """
QUERY_BATCH_MANUFACTURER_MHREG = """
select r.id, r.account_id, r.registration_ts, rr.id, rr.report_data, rr.batch_storage_url
  from mhr_registrations r, mhr_manufacturers m, mhr_registration_reports rr
 where r.id = rr.registration_id
   and r.account_id = m.account_id
   and r.registration_type = 'MHREG'
   and r.registration_ts between to_timestamp(:query_val1, 'YYYY-MM-DD HH24:MI:SS')
                             and to_timestamp(:query_val2, 'YYYY-MM-DD HH24:MI:SS')
  order by r.account_id, r.mhr_number
"""
UPDATE_BATCH_REG_REPORT = """
update mhr_registration_reports
   set batch_storage_url = '{batch_url}'
 where id in ({report_ids})
"""
QUERY_PPR_LIEN_COUNT = """
SELECT COUNT(base_registration_num)
  FROM mhr_lien_check_vw
 WHERE mhr_number = :query_value
"""
QUERY_PERMIT_COUNT = """
SELECT COUNT(r.id) AS permit_count
  FROM mhr_registrations r, mhr_parties p
 WHERE r.mhr_number = :query_value1
   AND r.registration_type = 'PERMIT'
   AND r.id = p.registration_id
   AND p.party_type = 'SUBMITTING'
   AND p.business_name = :query_value2
"""
QUERY_PKEYS = """
select nextval('mhr_registration_id_seq') AS reg_id,
       nextval('mhr_document_id_seq') AS doc_id,
       get_mhr_number() AS mhr_number,
       get_mhr_doc_reg_number() AS doc_reg_id,
       get_mhr_draft_number() AS draft_num,
       nextval('mhr_draft_id_seq') AS draft_id
"""
QUERY_PKEYS_NO_DRAFT = """
select nextval('mhr_registration_id_seq') AS reg_id,
       nextval('mhr_document_id_seq') AS doc_id,
       get_mhr_number() AS mhr_number,
       get_mhr_doc_reg_number() AS doc_reg_id
"""
CHANGE_QUERY_PKEYS = """
select nextval('mhr_registration_id_seq') AS reg_id,
       nextval('mhr_document_id_seq') AS doc_id,
       get_mhr_doc_reg_number() AS doc_reg_id,
       get_mhr_draft_number() AS draft_num,
       nextval('mhr_draft_id_seq') AS draft_id
"""
CHANGE_QUERY_PKEYS_NO_DRAFT = """
select nextval('mhr_registration_id_seq') AS reg_id,
       nextval('mhr_document_id_seq') AS doc_id,
       get_mhr_doc_reg_number() AS doc_reg_id
"""
QUERY_REG_ID_PKEY = """
select nextval('mhr_registration_id_seq') AS reg_id
"""
DOC_ID_QUALIFIED_CLAUSE = ',  get_mhr_doc_qualified_id() AS doc_id'
DOC_ID_MANUFACTURER_CLAUSE = ',  get_mhr_doc_manufacturer_id() AS doc_id'
DOC_ID_GOV_AGENT_CLAUSE = ',  get_mhr_doc_gov_agent_id() AS doc_id'
BATCH_DOC_NAME_MANUFACTURER_MHREG = 'batch-manufacturer-mhreg-report-{time}.pdf'


class AccountRegistrationParams():
    """Contains parameter values to use when sorting and filtering account summary registration information."""

    account_id: str
    collapse: bool = False
    sbc_staff: bool = False
    from_ui: bool = False
    sort_direction: str = SORT_DESCENDING
    page_number: int = 1
    sort_criteria: str = None
    filter_mhr_number: str = None
    filter_registration_type: str = None
    filter_registration_date: str = None
    filter_reg_start_date: str = None
    filter_reg_end_date: str = None
    filter_status_type: str = None
    filter_client_reference_id: str = None
    filter_submitting_name: str = None
    filter_username: str = None

    def __init__(self, account_id, collapse: bool = False, sbc_staff: bool = False):
        """Set common base initialization."""
        self.account_id = account_id
        self.collapse = collapse
        self.sbc_staff = sbc_staff

    def has_sort(self) -> bool:
        """Check if sort criteria provided."""
        if self.sort_criteria:
            if self.sort_criteria == MHR_NUMBER_PARAM or self.sort_criteria == REG_TYPE_PARAM or \
                    self.sort_criteria == REG_TS_PARAM or self.sort_criteria == CLIENT_REF_PARAM:
                return True
            if self.sort_criteria == SUBMITTING_NAME_PARAM or self.sort_criteria == OWNER_NAME_PARAM or \
                    self.sort_criteria == USER_NAME_PARAM or self.sort_criteria == STATUS_PARAM or \
                    self.sort_criteria == EXPIRY_DAYS_PARAM:
                return True
        return False

    def has_filter(self) -> bool:
        """Check if filter criteria provided."""
        return self.filter_client_reference_id or self.filter_mhr_number or self.filter_registration_type or \
            self.filter_reg_start_date or self.filter_status_type or self.filter_submitting_name or \
            self.filter_username

    def get_filter_values(self):  # pylint: disable=too-many-return-statements
        """Provide optional filter name and value if available."""
        if self.filter_mhr_number:
            return MHR_NUMBER_PARAM, self.filter_mhr_number
        if self.filter_registration_type:
            return REG_TYPE_PARAM, self.filter_registration_type
        if self.filter_reg_start_date:
            return START_TS_PARAM, self.filter_reg_start_date
        if self.filter_status_type:
            return STATUS_PARAM, self.filter_status_type
        if self.filter_client_reference_id:
            return CLIENT_REF_PARAM, self.filter_client_reference_id
        if self.filter_submitting_name:
            return SUBMITTING_NAME_PARAM, self.filter_submitting_name
        if self.filter_username:
            return USER_NAME_PARAM, self.filter_username
        return None, None

    def get_page_size(self) -> int:
        """Provide account registrations query page size."""
        if self.has_filter():
            return model_utils.MAX_ACCOUNT_REGISTRATIONS_DEFAULT
        return model_utils.get_max_registrations_size()

    def get_page_offset(self) -> int:
        """Provide account registrations query page offset."""
        page_offset: int = self.page_number
        if page_offset <= 1:
            return 0
        return (page_offset - 1) * self.get_page_size()


def get_ppr_lien_count(mhr_number: str) -> int:
    """Execute a query to count existing PPR liens on the MH (must not exist check)."""
    try:
        query = text(QUERY_PPR_LIEN_COUNT)
        result = db.session.execute(query, {'query_value': mhr_number})
        row = result.first()
        lien_count = int(row[0])
        return lien_count
    except Exception as db_exception:   # noqa: B902; return nicer error
        current_app.logger.error('get_ppr_lien_count exception: ' + str(db_exception))
        raise DatabaseException(db_exception)


def get_owner_group_count(base_reg) -> int:
    """Derive the next owner group sequence number from the number of existing groups."""
    count: int = len(base_reg.owner_groups)
    for reg in base_reg.change_registrations:
        if reg.owner_groups:
            count += len(reg.owner_groups)
    return count


def is_transfer_due_to_death(reg_type: str) -> bool:
    """Return if the registration type is a type of Transfer Due to Death."""
    return reg_type and reg_type in (MhrRegistrationTypes.TRANS_ADMIN,
                                     MhrRegistrationTypes.TRANS_AFFIDAVIT,
                                     MhrRegistrationTypes.TRANS_WILL,
                                     MhrRegistrationTypes.TRAND)


def is_transfer_due_to_death_staff(reg_type: str) -> bool:
    """Return if the registration type is a type of Transfer Due to Death."""
    return reg_type and reg_type in (MhrRegistrationTypes.TRANS_ADMIN,
                                     MhrRegistrationTypes.TRANS_AFFIDAVIT,
                                     MhrRegistrationTypes.TRANS_WILL)


def get_generated_values(registration, draft, user_group: str = None):
    """Get db generated identifiers that are in more than one table.

    Get registration_id, mhr_number, and optionally draft_number.
    """
    # generate reg id, MHR number. If not existing draft also generate draft number
    query = QUERY_PKEYS
    gen_doc_id: bool = False
    if draft:
        query = QUERY_PKEYS_NO_DRAFT
    if user_group and user_group in (QUALIFIED_USER_GROUP, GENERAL_USER_GROUP, BCOL_HELP):
        query += DOC_ID_QUALIFIED_CLAUSE
        gen_doc_id = True
        current_app.logger.debug('Updating query to generate qualified user document id.')
    elif user_group and user_group == MANUFACTURER_GROUP:
        query += DOC_ID_MANUFACTURER_CLAUSE
        gen_doc_id = True
        current_app.logger.debug('Updating query to generate manufacturer document id.')
    elif user_group and user_group == GOV_ACCOUNT_ROLE:
        query += DOC_ID_GOV_AGENT_CLAUSE
        gen_doc_id = True
        current_app.logger.debug('Updating query to generate government agent document id.')
    result = db.session.execute(query)
    row = result.first()
    registration.id = int(row[0])
    registration.doc_pkey = int(row[1])
    registration.mhr_number = str(row[2])
    registration.doc_reg_number = str(row[3])
    if not draft:
        registration.draft_number = str(row[4])
        registration.draft_id = int(row[5])
    if gen_doc_id and not draft:
        registration.doc_id = str(row[6])
    elif gen_doc_id and draft:
        registration.doc_id = str(row[4])
    return registration


def get_change_generated_values(registration, draft, user_group: str = None):
    """Get db generated identifiers that are in more than one table.

    Get registration_id, mhr_number, and optionally draft_number.
    """
    # generate reg id, MHR number. If not existing draft also generate draft number
    query = CHANGE_QUERY_PKEYS
    if draft:
        query = CHANGE_QUERY_PKEYS_NO_DRAFT
    if user_group and user_group in (QUALIFIED_USER_GROUP, GENERAL_USER_GROUP, BCOL_HELP):
        query += DOC_ID_QUALIFIED_CLAUSE
    elif user_group and user_group == MANUFACTURER_GROUP:
        query += DOC_ID_MANUFACTURER_CLAUSE
    # elif user_group and user_group == GOV_ACCOUNT_ROLE:
    else:
        query += DOC_ID_GOV_AGENT_CLAUSE
    result = db.session.execute(query)
    row = result.first()
    registration.id = int(row[0])
    registration.doc_pkey = int(row[1])
    registration.doc_reg_number = str(row[2])
    if not draft:
        registration.draft_number = str(row[3])
        registration.draft_id = int(row[4])
    # if user_group and user_group in (QUALIFIED_USER_GROUP, MANUFACTURER_GROUP, GOV_ACCOUNT_ROLE,
    #                                 GENERAL_USER_GROUP, BCOL_HELP):
    if draft:
        registration.doc_id = str(row[3])
    else:
        registration.doc_id = str(row[5])
    return registration


def get_registration_id() -> int:
    """Get db generated registration id, initially for creating a manufacturer."""
    result = db.session.execute(QUERY_REG_ID_PKEY)
    row = result.first()
    return int(row[0])


def update_deceased(owners_json, owner):
    """Set deceased information for transfer due to death registrations."""
    existing_json = owner.json
    match_json = None
    for owner_json in owners_json:
        if owner_json.get('organizationName') and existing_json.get('organizationName') and \
                owner_json.get('organizationName') == existing_json.get('organizationName'):
            match_json = owner_json
            break
        elif owner_json.get('individualName') and existing_json.get('individualName') and \
                owner_json.get('individualName') == existing_json.get('individualName'):
            match_json = owner_json
            break
    if match_json:
        if match_json.get('deathCertificateNumber'):
            owner.death_cert_number = str(match_json.get('deathCertificateNumber')).strip()
        if match_json.get('deathDateTime'):
            owner.death_ts = model_utils.ts_from_iso_format(match_json.get('deathDateTime'))


def include_caution_note(notes, document_id: str) -> bool:
    """Include expired caution note if subsequent continue or extend caution has not expired."""
    latest_caution = None
    for note in notes:
        if not latest_caution and note.get('documentType', '') in ('CAUC', 'CAUE', 'CAU '):
            latest_caution = note
        if note.get('documentId') == document_id:
            break
        elif latest_caution and note.get('documentType', '') not in ('CAUC', 'CAUE', 'CAU '):
            return False
    return latest_caution and not model_utils.date_elapsed(latest_caution.get('expiryDate'))


def get_batch_manufacturer_reg_report_data(start_ts: str = None, end_ts: str = None) -> dict:
    """Get recent manufacturer MHREG registration report data for a batch report."""
    results_json = []
    query_s = QUERY_BATCH_MANUFACTURER_MHREG_DEFAULT
    if start_ts and end_ts:
        query_s = QUERY_BATCH_MANUFACTURER_MHREG
        current_app.logger.debug(f'Using timestamp range {start_ts} to {end_ts}.')
    else:
        current_app.logger.debug('Using a default timestamp range of within the previous day.')
    query = text(query_s)
    result = None
    if start_ts and end_ts:
        start: str = start_ts[:19].replace('T', ' ')
        end: str = end_ts[:19].replace('T', ' ')
        current_app.logger.debug(f'start={start} end={end}')
        result = db.session.execute(query, {'query_val1': start, 'query_val2': end})
    else:
        result = db.session.execute(query)
    rows = result.fetchall()
    if rows is not None:
        for row in rows:
            batch_url = str(row[5]) if row[5] else ''
            result_json = {
                'registrationId': int(row[0]),
                'accountId': str(row[1]),
                'reportId': int(row[3]),
                'reportData': row[4],
                'batchStorageUrl': batch_url
            }
            results_json.append(result_json)
    if results_json:
        current_app.logger.debug(f'Found {len(results_json)} manufacturer MHREG registrations.')
    else:
        current_app.logger.debug('No manufacturer MHREG registrations found within the timestamp range.')
    return results_json


def update_reg_report_batch_url(json_data: dict, batch_url: str) -> int:
    """Set the mhr registration reports batch storage url for the recent registrations in json_data."""
    update_count: int = 0
    if not json_data:
        return update_count
    query_s = UPDATE_BATCH_REG_REPORT
    report_ids: str = ''
    for report in json_data:
        update_count += 1
        if report_ids != '':
            report_ids += ','
        report_ids += str(report.get('reportId'))
    query_s = query_s.format(batch_url=batch_url, report_ids=report_ids)
    current_app.logger.debug(f'Executing update query {query_s}')
    query = text(query_s)
    result = db.session.execute(query)
    db.session.commit()
    if result:
        current_app.logger.debug(f'Updated {update_count} manufacturer report registrations batch url to {batch_url}.')
    return update_count


def get_batch_storage_name_manufacturer_mhreg():
    """Get a search document storage name in the format YYYY/MM/DD/batch-manufacturer-mhreg-report-time.pdf."""
    now_ts = model_utils.now_ts()
    name = now_ts.isoformat()[:10]
    time = str(now_ts.hour) + '_' + str(now_ts.minute)
    name = name.replace('-', '/') + '/' + BATCH_DOC_NAME_MANUFACTURER_MHREG.format(time=time)
    return name


def find_cancelled_note(registration, reg_id: int):
    """Try and find the cancelled note matching the cancel registration document id."""
    if not registration.change_registrations:
        return None
    for reg in registration.change_registrations:
        if reg.notes and reg.notes[0].change_registration_id == reg_id:
            return reg.notes[0]
    return None


def update_notes_search_json(notes_json: dict, staff: bool) -> dict:
    """Build the search version of the registration as a json object."""
    if not notes_json:
        return notes_json
    updated_notes = []
    for note in notes_json:
        include: bool = True
        doc_type = note.get('documentType', '')
        if doc_type in ('REG_103', 'REG_103E', 'STAT', 'EXRE'):  # Always exclude
            include = False
        elif not staff and doc_type in ('REG_102', 'NCON'):  # Always exclude for non-staff
            include = False
        elif not staff and doc_type == 'FZE':  # Only staff can see remarks.
            note['remarks'] = ''
        elif not staff and doc_type == 'REGC' and note.get('remarks') and \
                note['remarks'] != 'MANUFACTURED HOME REGISTRATION CANCELLED':
            # Only staff can see remarks if not default.
            note['remarks'] = 'MANUFACTURED HOME REGISTRATION CANCELLED'
        elif doc_type in ('TAXN', 'EXNR', 'EXRS', 'NPUB', 'REST', 'CAU', 'CAUC', 'CAUE') and \
                note.get('status') != MhrNoteStatusTypes.ACTIVE:  # Exclude if not active.
            include = False
        elif doc_type in ('CAU', 'CAUC', 'CAUE') and note.get('expiryDateTime') and \
                model_utils.date_elapsed(note.get('expiryDateTime')):  # Exclude if expiry elapsed.
            include = include_caution_note(notes_json, note.get('documentId'))
        if doc_type == 'FZE':  # Do not display contact info.
            if note.get('givingNoticeParty'):
                del note['givingNoticeParty']
        if include:
            updated_notes.append(note)
    return updated_notes


def get_notes_json(registration, search: bool, staff: bool = False):
    """Fetch all the unit notes for the manufactured home. Search has special conditions on what is included."""
    notes = []
    if not registration.change_registrations:
        return notes
    cancel_notes = []
    for reg in registration.change_registrations:
        if reg.notes and (not search or reg.notes[0].status_type == MhrNoteStatusTypes.ACTIVE):
            note = reg.notes[0]
            if note.document_type in (MhrDocumentTypes.NCAN, MhrDocumentTypes.NRED, MhrDocumentTypes.EXRE):
                cnote = find_cancelled_note(registration, note.registration_id)
                if cnote:
                    cancel_note = cnote.json
                    cancel_note['ncan'] = note.json
                    cancel_notes.append(cancel_note)
            notes.append(note)
    if not notes:
        return notes
    notes_json = []
    for note in reversed(notes):
        note_json = note.json
        if note_json.get('documentType') in (MhrDocumentTypes.NCAN, MhrDocumentTypes.NRED, MhrDocumentTypes.EXRE) and \
                cancel_notes:
            for cnote in cancel_notes:
                if cnote['ncan'].get('documentId') == note_json.get('documentId'):
                    note_json['cancelledDocumentType'] = cnote.get('documentType')
                    note_json['cancelledDocumentDescription'] = cnote.get('documentDescription')
                    note_json['cancelledDocumentRegistrationNumber'] = cnote.get('documentRegistrationNumber')
        notes_json.append(note_json)
    if search:
        return update_notes_search_json(notes_json, staff)
    return notes_json


def get_non_staff_notes_json(registration, search: bool):
    """Build the non-BC Registries staff version of the active unit notes as JSON."""
    if search:
        return get_notes_json(registration, search)
    notes = get_notes_json(registration, search)
    if not notes:
        return notes
    updated_notes = []
    for note in notes:
        include: bool = True
        doc_type = note.get('documentType', '')
        if doc_type in ('STAT', '102'):  # Always exclude for non-staff
            include = False
        elif doc_type in ('TAXN', 'EXNR', 'EXRS', 'NPUB', 'REST', 'CAU', 'CAUC', 'CAUE', 'NCON') and \
                note.get('status') != MhrNoteStatusTypes.ACTIVE:  # Exclude if not active.
            include = False
        elif doc_type in ('CAU', 'CAUC', 'CAUE') and note.get('expiryDateTime') and \
                model_utils.date_elapsed(note.get('expiryDateTime')):  # Exclude if expiry elapsed.
            include = include_caution_note(notes, note.get('documentId'))
        elif doc_type in ('REG_103', 'REG_103E') and note.get('expiryDateTime') and \
                model_utils.date_elapsed(note.get('expiryDateTime')):  # Exclude if expiry elapsed.
            include = False
        if include:
            minimal_note = {
                'createDateTime': note.get('createDateTime'),
                'documentType': doc_type,
                'documentDescription':  note.get('documentDescription')
            }
            if doc_type in ('REG_103', 'REG_103E') and note.get('expiryDateTime'):
                minimal_note['expiryDateTime'] = note.get('expiryDateTime')
            updated_notes.append(minimal_note)
    return updated_notes


def get_document_description(doc_type: str) -> str:
    """Try to find the document description by document type."""
    if doc_type:
        doc_type_info: MhrDocumentType = MhrDocumentType.find_by_doc_type(doc_type)
        if doc_type_info:
            return doc_type_info.document_type_desc
    return ''


def save_cancel_note(registration, json_data, new_reg_id):  # pylint: disable=too-many-branches; only 1 more.
    """Update the original note status and change registration id."""
    cancel_doc_id: str = json_data.get('cancelDocumentId', '')
    if not cancel_doc_id:
        cancel_doc_id: str = json_data.get('updateDocumentId', '')
    cancel_note = get_cancel_note(registration, cancel_doc_id)
    if cancel_note:  # pylint: disable=too-many-nested-blocks; only 1 more.
        cancel_note.status_type = MhrNoteStatusTypes.CANCELLED
        cancel_note.change_registration_id = new_reg_id
        current_app.logger.debug(f'updating note status, change reg id for reg id {cancel_note.registration_id}')
        # Cancelling one active caution registration cancels all active caution registrations
        if cancel_note.document_type in (MhrDocumentTypes.CAU, MhrDocumentTypes.CAUC, MhrDocumentTypes.CAUE):
            for reg in registration.change_registrations:
                if reg.notes:
                    doc = reg.documents[0]
                    if doc.document_id != cancel_doc_id and \
                            doc.document_type in (MhrDocumentTypes.CAU,
                                                  MhrDocumentTypes.CAUC,
                                                  MhrDocumentTypes.CAUE):
                        note = reg.notes[0]
                        if note.status_type == MhrNoteStatusTypes.ACTIVE:
                            note.status_type = MhrNoteStatusTypes.CANCELLED
                            note.change_registration_id = new_reg_id
        elif cancel_note.document_type in (MhrDocumentTypes.EXNR, MhrDocumentTypes.EXRS, MhrDocumentTypes.EXMN):
            for reg in registration.change_registrations:
                if reg.notes:
                    doc = reg.documents[0]
                    if doc.document_id != cancel_doc_id and \
                            doc.document_type in (MhrDocumentTypes.EXNR,
                                                  MhrDocumentTypes.EXRS,
                                                  MhrDocumentTypes.EXMN):
                        note = reg.notes[0]
                        if note.status_type == MhrNoteStatusTypes.ACTIVE:
                            note.status_type = MhrNoteStatusTypes.CANCELLED
                            note.change_registration_id = new_reg_id
        db.session.commit()
    else:
        current_app.logger.debug(f'No modernized note found to cancel for reg id= {registration.id}')


def save_active(registration):
    """Set the state of the original MH registration to active."""
    if registration.status_type:
        current_app.logger.info(f'Setting MH state to ACTIVE for registration id={registration.id}')
        registration.status_type = MhrRegistrationStatusTypes.ACTIVE
        db.session.commit()
    else:
        current_app.logger.info('No modernized registration to set to active status.')


def get_cancel_note(registration, cancel_document_id: str):
    """Try and find the note matching the cancel document id."""
    cancel_note = None
    current_app.logger.info(f'Looking up note to cancel with doc id={cancel_document_id}')
    if not registration.change_registrations:
        current_app.logger.info('No change registrations so no notes to cancel.')
        return cancel_note
    for reg in registration.change_registrations:
        if reg.notes:
            doc = reg.documents[0]
            if doc.document_id == cancel_document_id:
                return reg.notes[0]
    return cancel_note


def set_declared_value_json(registration, json_data):
    """Set the most recent declared value and registration timestamp if they exist."""
    if not registration or not registration.change_registrations or not json_data:
        return json_data
    for reg in registration.change_registrations:
        if reg.documents and reg.documents[0].declared_value and reg.documents[0].declared_value > 0:
            json_data['declaredValue'] = reg.documents[0].declared_value
            json_data['declaredDateTime'] = model_utils.format_ts(reg.registration_ts)
    return json_data


def get_doc_id_count(doc_id: str) -> int:
    """Execute a query to count existing document id (must not exist check)."""
    try:
        query = text(DOC_ID_COUNT_QUERY)
        result = db.session.execute(query, {'query_value': doc_id})
        row = result.first()
        exist_count = int(row[0])
        current_app.logger.debug(f'Existing doc id count={exist_count}.')
        return exist_count
    except Exception as db_exception:   # noqa: B902; return nicer error
        current_app.logger.error('get_doc_id_count exception: ' + str(db_exception))
        raise DatabaseException(db_exception)


def get_permit_count(mhr_number: str, name: str) -> int:
    """Execute a query to count existing transport permit registrations on a home."""
    try:
        query = text(QUERY_PERMIT_COUNT)
        query_name = name[0:40]
        result = db.session.execute(query, {'query_value1': mhr_number, 'query_value2': query_name})
        row = result.first()
        exist_count = int(row[0])
        current_app.logger.debug(f'Existing transport permit count={exist_count}.')
        return exist_count
    except Exception as db_exception:   # noqa: B902; return nicer error
        current_app.logger.error('get_permit_count exception: ' + str(db_exception))
        raise DatabaseException(db_exception)
