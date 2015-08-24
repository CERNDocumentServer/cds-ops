# -*- coding: utf-8 -*-
#
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

"""Add downloads and pageviews as custom events."""

from invenio.webstat import create_customevent

depends_on = ['invenio_release_1_3_0']


def info():
    """Return upgrade recipe information."""
    return "Adds downloads and pageviews as custom events."


def do_upgrade():
    """Carry out the upgrade."""
    # create the downloads
    create_customevent(
        event_id="downloads",
        name="downloads",
        cols=[
            "id_bibrec", "id_bibdoc", "file_version", "file_format",
            "id_user", "client_host", "user_agent", "bot"
        ]
    )
    # create the pageviews
    create_customevent(
        event_id="pageviews",
        name="pageviews",
        cols=[
            "id_bibrec", "id_user", "client_host", "user_agent", "bot"
        ]
    )
    return 1


def estimate():
    """Estimate running time of upgrade in seconds (optional)."""
    return 1


def pre_upgrade():
    """Pre-upgrade checks."""
    pass  # because slashes would still work


def post_upgrade():
    """Post-upgrade checks."""
    pass
