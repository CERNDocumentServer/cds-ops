# This file is part of Invenio.
# Copyright (C) 2009, 2010, 2011, 2014, 2015, 2016 CERN.
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

"""Invenio LDAP interface for CERN."""

from thread import get_ident

import ldap

from ldap.controls import SimplePagedResultsControl


CFG_CERN_LDAP_URI = "ldap://xldap.cern.ch:389"
CFG_CERN_LDAP_BASE = "OU=Users,OU=Organic Units,DC=cern,DC=ch"
CFG_CERN_LDAP_PAGESIZE = 250

_ldap_connection_pool = {}


class LDAPError(Exception):

    """Base class for exceptions in this module."""

    pass


def _cern_ldap_login():
    """Get a connection from _ldap_connection_pool or create a new one."""
    try:
        connection = _ldap_connection_pool[get_ident()]
    except KeyError:
        _ldap_connection_pool[get_ident()] = ldap.initialize(CFG_CERN_LDAP_URI)
        connection = _ldap_connection_pool[get_ident()]

    connection.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
    return connection


def _msgid(connection, request_control, query_filter, attr_list=None):
    """Run the search request using search_ext.

    :param string query_filter: filter to apply in the LDAP search
    :param list attr_list: retrieved LDAP attributes. If None, all attributes
        are returned
    :return: msgid
    """
    try:
        return connection.search_ext(
            CFG_CERN_LDAP_BASE,
            ldap.SCOPE_SUBTREE,
            query_filter,
            attr_list,
            attrsonly=0,
            serverctrls=[request_control])
    except ldap.SERVER_DOWN as e:
        raise LDAPError("Error: Connection to CERN LDAP failed. ({0})"
                        .format(e))


def _paged_search(connection, query_filter, attr_list=None):
    """Search the CERN LDAP server using pagination.

    :param string query_filter: filter to apply in the LDAP search
    :param list attr_list: retrieved LDAP attributes. If None, all attributes
        are returned
    :return: list of tuples (result-type, result-data) or empty list,
        where result-data contains the user dictionary
    """
    request_control = SimplePagedResultsControl(
        True, CFG_CERN_LDAP_PAGESIZE, "")
    msgid = _msgid(connection, request_control, query_filter, attr_list)
    result_pages = 0
    results = []

    while True:
        rtype, rdata, rmsgid, rcontrols = connection.result3(msgid)
        results.extend(rdata)
        result_pages += 1

        page_controls = [
            c
            for c in rcontrols
            if c.controlType == SimplePagedResultsControl.controlType
        ]
        if page_controls and page_controls[0].cookie:
            request_control.cookie = page_controls[0].cookie
            msgid = _msgid(
                connection, request_control, query_filter, attr_list)
        else:
            break

    return results


def get_users_records_data(query_filter, attr_list=None, decode_encoding=None):
    """Get result-data of records.

    :param string query_filter: filter to apply in the LDAP search
    :param list attr_list: retrieved LDAP attributes. If None, all attributes
        are returned
    :param string decode_encoding: decode the values of the LDAP records
    :return: list of LDAP records, but result-data only
    """
    connection = _cern_ldap_login()
    records = _paged_search(connection, query_filter, attr_list)

    records_data = []

    if decode_encoding:
        records_data = [
            {k: [v[0].decode(decode_encoding)] for k, v in x.iteritems()}
            for _, x in records]
    else:
        records_data = [x for _, x in records]

    return records_data
