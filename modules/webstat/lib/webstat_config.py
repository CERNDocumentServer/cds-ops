# -*- coding: utf-8 -*-
##
## This file is part of Invenio.
## Copyright (C) 2008, 2010, 2011 CERN.
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

"""Invenio WebStat Configuration."""

__revision__ = "$Id$"

from invenio.config import CFG_ETCDIR, CFG_ELASTICSEARCH_LOGGING, CFG_CERN_SITE

CFG_WEBSTAT_CONFIG_PATH = CFG_ETCDIR + "/webstat/webstat.cfg"

if CFG_CERN_SITE:
    CFG_ELASTICSEARCH_EVENTS_MAP = {
        "events.loanrequest": {
            "_source": {
                "enabled": True
            },
            "properties": {
                "request_id": {
                    "type": "integer"
                },
                "load_id": {
                    "type": "integer"
                }
            }
        }
    }
else:
    CFG_ELASTICSEARCH_EVENTS_MAP = {}

if CFG_ELASTICSEARCH_LOGGING:
    from invenio.elasticsearch_logging import register_schema
    for name, arguments in CFG_ELASTICSEARCH_EVENTS_MAP.items():
        register_schema(name, arguments)
