# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2007, 2008, 2009, 2010, 2011, 2015 CERN.
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

"""BibFormat element - Handle youtube authrization"""

from invenio.bibencode_youtube import youtube_script
from invenio.access_control_admin import acc_is_user_in_role, acc_get_role_id
from invenio.bibencode_config import CFG_BIBENCODE_YOUTUBE_USER_ROLE

def format_element(bfo):
    """
    Handles youtube authorization
    =============================
    """
    if acc_is_user_in_role(bfo.user_info, acc_get_role_id(CFG_BIBENCODE_YOUTUBE_USER_ROLE)):
        return youtube_script(bfo.recID)

def escape_values(bfo):
    """
    Called by BibFormat in order to check if output of this element
    should be escaped.
    """
    return 0
