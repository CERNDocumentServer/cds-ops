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

""""BibAuthority CERN people collection mapper.

Map CERN LDAP records to MARC 21 authority records, create and
write XML objects based on the MARC 21 XML Schema (MARCXML).
"""

from collections import OrderedDict
from datetime import date
from os import makedirs
from os.path import dirname, exists, splitext

from invenio.bibauthority_people_config import (
    CFG_BIBAUTHORITY_AUTHOR_CERN, CFG_BIBAUTHORITY_AUTHOR_INSPIRE)
from invenio.bibauthority_people_utils import get_inspire_id

from lxml import etree


class MapperError(Exception):

    """Base class for exceptions in this module."""

    pass


class Mapper:

    """Map CERN LDAP records to MARC 21 authority records (MARCXML).

    MARC 21 authority reference: http://www.loc.gov/marc/authority/
    """

    def __init__(self, mapping_inspire_ids=None):
        """Initialize the mapper properties."""
        self.roots = []  # Contain all root elements
        self.records = []  # Contain all (mapped) MARC records
        # Mapping rules: LDAP attributes to MARC 21 authority
        # LDAP attributes used in config.CFG_LDAP_ATTRLIST
        self.mapper_dict = {
            "employeeID": "035__a",
            "givenName": "1000_a",
            "sn": "1001_a",
            "displayName": "100__a",
            "facsimileTelephoneNumber": "371__f",
            "telephoneNumber": "371__k",
            "mobile": "371__l",
            "mail": "371__m",
            "department": "371__d",
            "cernGroup": "371__g",
            "description": "371__h",
            "division": "371__i",
            "cernInstituteName": "371__0",
            "extensionAttribute11": "371__1"
        }
        self.mapping_inspire_ids = mapping_inspire_ids

    def _split_marc_id(self, marc_id):
        """Split MARC 21 identifier which is defined in the mapper_dict.

        :param string marc_id: format: fffiis,
            f = Field Code (code);
            i = First Indicator (ind1), Second Indicator (ind2);
            s = Subfield Codes (subfield_code, optional)
        :return: code, ind1, ind2, and subfield_code
        """
        try:
            subfield_code = marc_id[5]
        except IndexError:
            subfield_code = None

        return marc_id[:3], marc_id[3], marc_id[4], subfield_code

    def _create_root(self):
        """Create root element 'collection' with the attribute 'xmlns'.

        :return: root element
        """
        return etree.Element(
            "collection", {"xmlns": "http://www.loc.gov/MARC21/slim"})

    def _create_record(self, parent=None):
        """Create record element.

        :param elem parent: parent of record element (optional)
        :return: record element
        """
        if parent:
            elem_record = etree.SubElement(parent, "record")
        else:
            elem_record = etree.Element("record")
        return elem_record

    def _create_controlfield(self, parent, attr_code, inner_text=None):
        """Create child element 'controlfield' of parent.

        :param elem parent: parent element, usually 'collection'
        :param string attr_code: value for attribute 'code'
        :param string inner_text: inner text of element
        :return: controlfield element, child of parent
        """
        controlfield = etree.SubElement(parent, "controlfield", {
            "tag": attr_code})
        if inner_text:
            controlfield.text = inner_text
        return controlfield

    def _create_datafield(self, parent, marc_id, value, repeatable=False):
        """Create child element 'datafield' (including 'subfield') of parent.

        :param elem parent: parent element, usually 'record'
        :param string marc_id: full MARC-id, example: 035__a
        :param string value: value stored in subfield
        :param bool repeatable: allows multiple datafields with same codes
        :return: either new or existing datafield element (depending on
            repeatable), child of parent
        """
        marc_code, marc_ind1, marc_ind2, marc_subfield_code = (
            self._split_marc_id(marc_id))

        # Modify indicators
        if marc_ind1 == "_":
            marc_ind1 = " "
        elif marc_ind1.isalpha():
            marc_ind1 = marc_ind1.upper()
        if marc_ind2 == "_":
            marc_ind2 = " "
        elif marc_ind2.isalpha():
            marc_ind2 = marc_ind2.upper()

        find = parent.xpath(
            "datafield[@tag={0} and @ind1='{1}' and @ind2='{2}']".format(
                marc_code, marc_ind1, marc_ind2))
        if not find or repeatable:
            elem_datafield = etree.SubElement(
                parent,
                "datafield",
                OrderedDict({
                    "tag": marc_code, "ind1": marc_ind1, "ind2": marc_ind2}))
        else:
            elem_datafield = find[0]

        # Create subfield with value and append to datafield
        subfield = etree.SubElement(
            elem_datafield, "subfield", {"code": marc_subfield_code})
        subfield.text = value

        return elem_datafield

    def _attach_records(self, record_size=500):
        """Attach record elements to root element(s).

        :param int record_size: record child elements in a root node,
            if <= 0: append all records to one root node
        :return : list of root elements
        """
        # Append all record elements to one root element
        if record_size <= 0:
            record_size = -1

        # Append records to root element(s) depending on record_size
        if self.records:
            current_root = self._create_root()
            self.roots.append(current_root)
            record_size_counter = 0

        for record in self.records:
            if record_size_counter == record_size:
                current_root = self._create_root()
                self.roots.append(current_root)
                record_size_counter = 0  # reset counter
            record_size_counter += 1
            current_root.append(record)

        return self.roots

    def map_ldap_record(self, record):
        """Map LDAP record to MARC 21 authority record (XML).

        :param dictionary record: LDAP record (result-data)
        :param filepath file: look up Inspire-ID at
            ATLAS GLANCE (False) or local directory (True)
        :return: record element
        """
        elem_record = self._create_record()

        # Map each LDAP attribute for one record to a datafield
        for attr_key in self.mapper_dict.keys():
            marc_id = self.mapper_dict.get(attr_key)

            value = record.get(attr_key)
            if value:
                value = value[0]

                # Modify employeeID to valid system control number
                if attr_key == "employeeID":
                    value = "{0}{1}".format(
                        CFG_BIBAUTHORITY_AUTHOR_CERN, value)

                self._create_datafield(elem_record, marc_id, value)

        # Additional repeatable datafields for collections
        self._create_datafield(elem_record, "371__v", "CERN LDAP")
        self._create_datafield(elem_record, "690C_a", "CERN")
        self._create_datafield(elem_record, "980__a", "PEOPLE", True)
        self._create_datafield(elem_record, "980__a", "AUTHORITY", True)

        # Add Inspire-ID (if exists for employeeID) to record
        employee_id = record.get('employeeID')
        if employee_id:
            if self.mapping_inspire_ids:
                inspire_id = get_inspire_id(
                    employee_id[0], self.mapping_inspire_ids)
            else:
                inspire_id = get_inspire_id(employee_id[0])
            if inspire_id:
                # Modify inspire_id to valid system control number
                inspire_id = "{0}{1}".format(
                    CFG_BIBAUTHORITY_AUTHOR_INSPIRE, inspire_id)
                self._create_datafield(elem_record, "035__a", inspire_id, True)

        return elem_record

    def map_ldap_records(self, records):
        """Map LDAP records.

        :param list records: list of LDAP records (result-data)
        :return: list of record elements
        """
        for record in records:
            self.records.append(self.map_ldap_record(record))

        return self.records

    def update_ldap_records(self, records):
        """Map updated LDAP records.

        :param list records: list of tuples (status, record), where status is
            'add', 'remove', or 'change'
        :return: list of record XML elements
        """
        for record in records:
            elem_record = self.map_ldap_record(record[1])

            # Add datafields for removed records
            if record[0] == "remove":
                self._create_datafield(
                    elem_record, "595__a", "REMOVED FROM SOURCE")
                self._create_datafield(
                    elem_record, "595__c", date.today().strftime("%Y-%m-%d"))

            self.records.append(elem_record)

        return self.records

    def _write_xml(self, tree, xml_file):
        """Write tree to XML file.

        :param etree tree: XML tree to write
        :param filepath xml_file: XML file to write to
        """
        try:
            with open(xml_file, "w") as f:
                f.write(tree)
        except EnvironmentError as e:
            raise MapperError("Error: failed writing file. ({0})".format(e))

    def write_marcxml(self, xml_file, record_size=500):
        """Prepare to write self.roots to a single file or multiple files.

        :param int record_size: record elements in a root node [default: 500],
            if <= 0: append all records to one root node
        :param filepath xml_file: save to file,
            suffix ('_0', '_1', ...) will be added to file name
        """
        directory = dirname(xml_file)
        if directory is not "" and not exists(directory):
            makedirs(directory)

        self._attach_records(record_size)

        try:
            # Write single file
            if record_size <= 0:
                self._write_xml(
                    etree.tostring(
                        self.roots[0], encoding='utf-8', pretty_print=True),
                    xml_file)
            # Write multiple files
            else:
                filename, ext = splitext(xml_file)
                for i, root in enumerate(self.roots):
                    f = "{0}_{1}{2}".format(filename, i, ext)
                    self._write_xml(
                        etree.tostring(
                            root, encoding='utf-8', pretty_print=True),
                        f)
        except MapperError:
            raise
