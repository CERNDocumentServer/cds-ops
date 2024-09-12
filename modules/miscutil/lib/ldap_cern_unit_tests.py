# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2008, 2009, 2010, 2011, 2013, 2014, 2015 CERN.
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

"""Unit tests for the solrutils library."""

from invenio.ldap_cern import get_users_records_data
from invenio.testutils import InvenioTestCase
from invenio.testutils import make_test_suite, run_test_suite


class TestLDAPGetUserInfo(InvenioTestCase):

    """Test for retrieving users information from LDAP at CERN."""

    def test_users_records_data(self):
        """Try to get a specific user data (requires a user from CERN)."""
        searchfilter = (r"(&(objectClass=*)(employeeType=Primary)"
                        "(mail=Tibor.Simko@cern.ch))")
        attrlist = ["mail", "displayName", "cernInstituteName"]
        expected_results = 1
        expected_displayName = "Tibor Simko"
        expected_email = "Tibor.Simko@cern.ch"
        expected_affiliation = "CERN"
        records = get_users_records_data(searchfilter, attrlist)
        self.assertEqual(len(records), expected_results)
        self.assertEqual(
            records[0].get("displayName", [])[0], expected_displayName)
        self.assertEqual(
            records[0].get("mail", [])[0], expected_email)
        self.assertEqual(
            records[0].get("cernInstituteName", [])[0], expected_affiliation)

TEST_SUITE = make_test_suite(TestLDAPGetUserInfo)

if __name__ == "__main__":
    run_test_suite(TEST_SUITE)
