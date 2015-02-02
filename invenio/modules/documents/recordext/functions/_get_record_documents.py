# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2014 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.


def _get_record_documents(record):
    """Return list of tuples `('doc_name', 'doc_uuid')`.

    If the records doesn't have any document attached to it, i.e. it was
    uploaded using `bibupload`, looks for any existing BibDocFile and creates
    a document with the basic information pointing to it.

    If `get_record(recid, reset_cache=True)` was called it will regenerate the
    `_documents` field out of either document or bibdocs.

    :record: Record instance
    :returns: list of tuples
    """
    from invenio.modules.documents import api
    from invenio.legacy.bibdocfile.api import BibRecDocs, \
        InvenioBibDocFileError

    documents_json = api.Document.storage_engine.search(
        {'recids': record.get('recid', -1)})
    if documents_json.count():
        return [(d['title'], d['uuid']) for d in documents_json]

    # There are no Documents attached to the record, try BibDocFiles
    _documents = []
    try:
        bibrecdocs = BibRecDocs(record.get('recid', -1))
    except InvenioBibDocFileError:
        return []
    latest_files = bibrecdocs.list_latest_files()
    for afile in latest_files:
        document = api.Document.create(
            dict(
                title=afile.get_name(),
                source=afile.get_url(),
                uri=afile.get_full_path(),
                description=afile.get_description(),
                recids=[record.get('recid'), ],
                linked=True
            ),
            model='record_document_base'
        )
        _documents.append((document['title'], document['uuid']))

    return _documents
