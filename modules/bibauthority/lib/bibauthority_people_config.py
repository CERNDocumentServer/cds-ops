# This file is part of Invenio.
# Copyright (C) 2015 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""BibAuthority CERN people collection configuration file."""

from os.path import join

from invenio.config import CFG_CACHEDIR, CFG_TMPSHAREDDIR
from invenio.containerutils import LazyDict
from invenio.websubmit_author_sources.atlas_glance import query_author_source


def _atlas_glance_to_inspire_id():
    return dict(
        (author["cernccid"], author["inspireid"]) for
        author in query_author_source("") if
        author.get("cernccid") and author.get("inspireid"))


# LDAP search filter
CFG_BIBAUTHORITY_LDAP_SEARCHFILTER = \
    r"(&(objectClass=*)(employeeType=Primary))"

# LDAP attribute list
# bibauthority_people_mapper contains the same attributes
CFG_BIBAUTHORITY_LDAP_ATTRLIST = [
    "employeeID",
    "givenName",
    "sn",
    "displayName",
    "facsimileTelephoneNumber",
    "telephoneNumber",
    "mobile",
    "mail",
    "department",
    "cernGroup",
    "description",
    "division",
    "cernInstituteName",
    "extensionAttribute11"]

# Stores CERN LDAP records
CFG_BIBAUTHORITY_RECORDS_JSON_FILE = join(CFG_CACHEDIR, "records.json")

# Stores updated MARC 21 authority records
CFG_BIBAUTHORITY_RECORDS_UPDATES_FILE = join(
    CFG_TMPSHAREDDIR, "records_updates.xml")

# Prefix
CFG_BIBAUTHORITY_AUTHOR_CDS = "AUTHOR|(CDS)"

# Prefix used in MARC field 035__a
CFG_BIBAUTHORITY_AUTHOR_CERN = "AUTHOR|(SzGeCERN)"

# Prefix used in MARC field 035__a
CFG_BIBAUTHORITY_AUTHOR_INSPIRE = "AUTHOR|(INSPIRE)"

# Dictionary containing the mapping CERN-ID: Inspire-ID
CFG_BIBAUTHORITY_ATLAS_GLANCE_CERN_ID_TO_INSPIRE_ID_MAPPING = LazyDict(
    _atlas_glance_to_inspire_id)

# Send email if duplicate Inspire-IDs found
CFG_BIBAUTHORITY_ATLAS_GLANCE_EMAIL_FROM = "noreply@cern.ch"

# Send email if duplicate Inspire-IDs found
CFG_BIBAUTHORITY_ATLAS_GLANCE_EMAIL_TO = "cds-monitoring@cern.ch"
