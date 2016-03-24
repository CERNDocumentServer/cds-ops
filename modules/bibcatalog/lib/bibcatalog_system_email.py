# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2009, 2010, 2011, 2013 CERN.
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

"""
Provide a "ticket" interface with Email.
This is a subclass of BibCatalogSystem
"""


import datetime
from time import mktime
import invenio.webuser
from invenio.bibcatalog_system import BibCatalogSystem
from invenio.mailutils import send_email
from invenio.errorlib import register_exception

EMAIL_SUBMIT_CONFIGURED = False
import invenio.config
if hasattr(invenio.config, 'CFG_BIBCATALOG_SYSTEM') and invenio.config.CFG_BIBCATALOG_SYSTEM == "EMAIL":
    if hasattr(invenio.config, 'CFG_BIBCATALOG_SYSTEM_EMAIL_ADDRESS'):
        EMAIL_SUBMIT_CONFIGURED = True
        FROM_ADDRESS = invenio.config.CFG_SITE_SUPPORT_EMAIL
        TO_ADDRESS = invenio.config.CFG_BIBCATALOG_SYSTEM_EMAIL_ADDRESS


class BibCatalogSystemEmail(BibCatalogSystem):
    #BIBCATALOG_RT_SERVER = "" #construct this by http://user:password@RT_URL

    def check_system(self, uid=None):
        """return an error string if there are problems"""

        ret = ''
        if not EMAIL_SUBMIT_CONFIGURED:
            ret  = "Please configure bibcatalog email sending in CFG_BIBCATALOG_SYSTEM and CFG_BIBCATALOG_SYSTEM_EMAIL_ADDRESS"
        return ret

    def ticket_search(self, uid, recordid=-1, subject="", text="", creator="", owner="", \
                      date_from="", date_until="", status="", priority="", queue=""):
        """Not implemented."""

        raise NotImplementedError

    def ticket_submit(self, uid=None, **kwargs):
        """creates a ticket. Returns ticket_id on success, otherwise None"""

        if not EMAIL_SUBMIT_CONFIGURED:
            register_exception(stream='warning',
                               subject='bibcatalog email not configured',
                               prefix="please configure bibcatalog email sending in CFG_BIBCATALOG_SYSTEM and CFG_BIBCATALOG_SYSTEM_EMAIL_ADDRESS")

        ticket_id = self._get_ticket_id()
        textset = ''
        ownerset = ''
        priorityset = ' priority: {0}\n'.format(kwargs['priority']) if 'priority' in kwargs else ""
        queueset = ' queue: {0}\n'.format(kwargs['queue']) if 'queue' in kwargs else ""
        requestorset = ' requestor: {0}\n'.format(kwargs['requestor']) if 'requestor' in kwargs else ""
        recidset = ' cf-recordID: {0}\n'.format(kwargs.get('recordid', -1))
        subjectset = 'ticket #{0} - {1}'.format(ticket_id, kwargs['subject']) if 'subject' in kwargs else ''
        owner = kwargs.get('owner', '')
        if owner:
            ownerprefs = invenio.webuser.get_user_preferences(owner)
            if ownerprefs.has_key('bibcatalog_username'):
                owner = ownerprefs['bibcatalog_username']
            ownerset = ' owner: {0}\n'.format(owner)

        textset += ownerset + requestorset + recidset + queueset + priorityset + '\n'

        textset += kwargs.get('text', '') + '\n'

        ok = send_email(
            fromaddr=kwargs.get('from_address', FROM_ADDRESS),
            toaddr=kwargs.get('to_address', TO_ADDRESS),
            subject=subjectset,
            content=textset
        )
        if ok:
            return ticket_id
        return None

    def ticket_comment(self, uid, ticketid, comment):
        """ Comment on ticket with given ticketid"""

        subjectset = 'ticket #' + ticketid + ' - Comment ...'
        textset    = '...\n\n*Comment on ticket #' + ticketid + '\nComment:' + comment
        ok = send_email(fromaddr=FROM_ADDRESS, toaddr=TO_ADDRESS, subject=subjectset, header='Hello,\n\n', content=textset)
        if ok:
            return 1
        return 0


    def ticket_assign(self, uid, ticketid, to_user):
        """ Re-assign existing ticket with given ticketid to user to_user"""

        subjectset = 'ticket #' + ticketid + ' - Re-assign ...'
        textset    = '...\n\n*Please re-assigning ticket #' + ticketid + ' to ' + to_user
        ok = send_email(fromaddr=FROM_ADDRESS, toaddr=TO_ADDRESS, subject=subjectset, header='Hello,\n\n', content=textset)
        if ok:
            return 1
        return 0

    def ticket_set_attribute(self, uid, ticketid, attribute, new_value):
        """ Request to set attribute to new value on ticket with given ticketid"""

        subjectset = 'ticket #' + ticketid + ' - Attribute Update ...'
        textset    = '...\n\n*Please modify attribute:' + attribute + ' to:' + new_value + ' on ticket:' + ticketid
        ok = send_email(fromaddr=FROM_ADDRESS, toaddr=TO_ADDRESS, subject=subjectset, header='Hello,\n\n', content=textset)
        if ok:
            return 1
        return 0

    def ticket_get_attribute(self, uid, ticketid, attribute):
        """Not implemented."""

        raise NotImplementedError

    def ticket_get_info(self, uid, ticketid, attributes = None):
        """Not implemented."""

        raise NotImplementedError

    def _str_base(self, num, base, numerals = '0123456789abcdefghijklmnopqrstuvwxyz'):
        """ Convert number to base (2 to 36) """

        if base < 2 or base > len(numerals):
            raise ValueError("str_base: base must be between 2 and %i" % len(numerals))

        if num == 0:
            return '0'

        if num < 0:
            sign = '-'
            num = -num
        else:
            sign = ''

        result = ''
        while num:
            result = numerals[num % (base)] + result
            num //= base

        return sign + result


    def _get_ticket_id(self):
        """ Return timestamp in seconds since the Epoch converted to base36 """

        now =  datetime.datetime.now()
        t = mktime(now.timetuple())+1e-6*now.microsecond

        t_str = str("%.6f" % t)
        t1, t2 = t_str.split('.')
        t_str = t1 + t2

        #return base64.encodestring(t_str).strip()
        return self._str_base(int(t_str), 36)
