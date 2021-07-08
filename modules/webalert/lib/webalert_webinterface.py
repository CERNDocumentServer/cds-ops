# This file is part of Invenio.
# Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011 CERN.
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

"""PERSONAL FEATURES - YOUR ALERTS"""

__revision__ = "$Id$"

__lastupdated__ = """$Date$"""

import re

from invenio.config import CFG_SITE_SECURE_URL, CFG_SITE_NAME, \
  CFG_ACCESS_CONTROL_LEVEL_SITE, CFG_SITE_NAME_INTL, CFG_SITE_LANG
from invenio.webpage import page
from invenio.webalert import perform_input_alert, \
                             perform_request_youralerts_display, \
                             perform_add_alert, \
                             perform_update_alert, \
                             perform_remove_alert, \
                             perform_pause_alert, \
                             perform_resume_alert, \
                             perform_request_youralerts_popular, \
                             AlertError, \
                             APD_alert

from invenio.webuser import getUid, page_not_authorized, isGuestUser
from invenio.webinterface_handler import wash_urlargd, WebInterfaceDirectory
from invenio.urlutils import redirect_to_url, make_canonical_urlargd
from invenio.webstat import register_customevent
from invenio.errorlib import register_exception
from invenio.webuser import collect_user_info
from invenio.search_engine import perform_request_search, \
                                  check_user_can_view_record

from invenio.messages import gettext_set_language
import invenio.template
webalert_templates = invenio.template.load('webalert')

class WebInterfaceYourAlertsPages(WebInterfaceDirectory):
    """Defines the set of /youralerts pages."""

    _exports = ['',
                'display',
                'input',
                'modify',
                'list',
                'add',
                'update',
                'remove',
                'pause',
                'resume',
                'popular',
                'APD']

    def index(self, req, dummy):
        """Index page."""

        redirect_to_url(req, '%s/youralerts/display' % CFG_SITE_SECURE_URL)

    def list(self, req, dummy):
        """
        Legacy youralerts list page.
        Now redirects to the youralerts display page.
        """

        redirect_to_url(req, '%s/youralerts/display' % (CFG_SITE_SECURE_URL,))

    def input(self, req, form):

        argd = wash_urlargd(form, {'idq': (int, None),
                                   'name': (str, ""),
                                   'freq': (str, "week"),
                                   'notif': (str, "y"),
                                   'idb': (int, 0),
                                   'error_msg': (str, ""),
                                   })

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/input" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/input%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        try:
            html = perform_input_alert("add",
                                       argd['idq'],
                                       argd['name'],
                                       argd['freq'],
                                       argd['notif'],
                                       argd['idb'],
                                       uid,
                                       is_active = 1,
                                       ln = argd['ln'])
        except AlertError, msg:
            return page(title=_("Error"),
                        body=webalert_templates.tmpl_errorMsg(ln=argd['ln'], error_msg=msg),
                        navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                     'sitesecureurl' : CFG_SITE_SECURE_URL,
                                     'ln': argd['ln'],
                                     'account' : _("Your Account"),
                                  },
                        description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        uid=uid,
                        language=argd['ln'],
                        req=req,
                        lastupdated=__lastupdated__,
                        navmenuid='youralerts')

        if argd['error_msg'] != "":
            html = webalert_templates.tmpl_errorMsg(
                     ln = argd['ln'],
                     error_msg = argd['error_msg'],
                     rest = html,
                   )

        # register event in webstat
        alert_str = "%s (%d)" % (argd['name'], argd['idq'])
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["input", alert_str, user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        return page(title=_("Set a new alert"),
                    body=html,
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                 'sitesecureurl' : CFG_SITE_SECURE_URL,
                                 'ln': argd['ln'],
                                 'account' : _("Your Account"),
                              },
                    description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def modify(self, req, form):

        argd = wash_urlargd(form, {'idq': (int, None),
                                   'old_idb': (int, None),
                                   'name': (str, ""),
                                   'freq': (str, "week"),
                                   'notif': (str, "y"),
                                   'idb': (int, 0),
                                   'is_active': (int, 0),
                                   'error_msg': (str, ""),
                                   })

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/modify" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/modify%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        try:
            html = perform_input_alert("update", argd['idq'],
                                                 argd['name'],
                                                 argd['freq'],
                                                 argd['notif'],
                                                 argd['idb'],
                                                 uid,
                                                 argd['is_active'],
                                                 argd['old_idb'],
                                                 ln=argd['ln'])
        except AlertError, msg:
            return page(title=_("Error"),
                        body=webalert_templates.tmpl_errorMsg(ln=argd['ln'], error_msg=msg),
                        navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                     'sitesecureurl' : CFG_SITE_SECURE_URL,
                                     'ln': argd['ln'],
                                     'account' : _("Your Account"),
                                  },
                        description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        uid=uid,
                        language=argd['ln'],
                        req=req,
                        lastupdated=__lastupdated__,
                        navmenuid='youralerts')

        if argd['error_msg'] != "":
            html = webalert_templates.tmpl_errorMsg(
                     ln = argd['ln'],
                     error_msg = argd['error_msg'],
                     rest = html,
                   )

        # register event in webstat
        alert_str = "%s (%d)" % (argd['name'], argd['idq'])
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["modify", alert_str, user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        return page(title=_("Modify alert settings"),
                    body=html,
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                 'sitesecureurl' : CFG_SITE_SECURE_URL,
                                 'ln': argd['ln'],
                                 'account' : _("Your Account"),
                              },
                    description=_("%s Personalize, Modify alert settings") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def display(self, req, form):

        argd = wash_urlargd(form, {'idq':   (int, 0),
                                   'page':  (int, 1),
                                   'step':  (int, 20),
                                   'p':     (str, ''),
                                   'ln':    (str, '')})

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/display" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/display%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        # register event in webstat
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["display", "", user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        return page(title=_("Your Alerts"),
                    body=perform_request_youralerts_display(uid,
                                                            idq=argd['idq'],
                                                            page=argd['page'],
                                                            step=argd['step'],
                                                            p=argd['p'],
                                                            ln=argd['ln']),
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % \
                              {'sitesecureurl' : CFG_SITE_SECURE_URL,
                               'ln': argd['ln'],
                               'account' : _("Your Account")},
                    description=_("%s Personalize, Display alerts") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def add(self, req, form):

        argd = wash_urlargd(form, {'idq': (int, None),
                                   'name': (str, None),
                                   'freq': (str, None),
                                   'notif': (str, None),
                                   'idb': (int, None),
                                   })

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/add" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/add%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        try:
            html = perform_add_alert(argd['name'], argd['freq'], argd['notif'],
                                              argd['idb'], argd['idq'], uid, ln=argd['ln'])
        except AlertError, msg:
            return page(title=_("Error"),
                        body=webalert_templates.tmpl_errorMsg(ln=argd['ln'], error_msg=msg),
                        navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                     'sitesecureurl' : CFG_SITE_SECURE_URL,
                                     'ln': argd['ln'],
                                     'account' : _("Your Account"),
                                  },
                        description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        uid=uid,
                        language=argd['ln'],
                        req=req,
                        lastupdated=__lastupdated__,
                        navmenuid='youralerts')

        # register event in webstat
        alert_str = "%s (%d)" % (argd['name'], argd['idq'])
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["add", alert_str, user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        return page(title=_("Display alerts"),
                    body=html,
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                 'sitesecureurl' : CFG_SITE_SECURE_URL,
                                 'ln': argd['ln'],
                                 'account' : _("Your Account"),
                              },
                    description=_("%s Personalize, Display alerts") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def update(self, req, form):

        argd = wash_urlargd(form, {'name': (str, None),
                                   'freq': (str, None),
                                   'notif': (str, None),
                                   'idb': (int, None),
                                   'idq': (int, None),
                                   'is_active': (int, 0),
                                   'old_idb': (int, None),
                                   })

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/update" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/update%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        try:
            html = perform_update_alert(argd['name'],
                                        argd['freq'],
                                        argd['notif'],
                                        argd['idb'],
                                        argd['idq'],
                                        argd['old_idb'],
                                        uid,
                                        argd['is_active'],
                                        ln=argd['ln'])
        except AlertError, msg:
            return page(title=_("Error"),
                        body=webalert_templates.tmpl_errorMsg(ln=argd['ln'], error_msg=msg),
                        navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                     'sitesecureurl' : CFG_SITE_SECURE_URL,
                                     'ln': argd['ln'],
                                     'account' : _("Your Account"),
                                  },
                        description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        uid=uid,
                        language=argd['ln'],
                        req=req,
                        lastupdated=__lastupdated__,
                        navmenuid='youralerts')

        # register event in webstat
        alert_str = "%s (%d)" % (argd['name'], argd['idq'])
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["update", alert_str, user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        return page(title=_("Display alerts"),
                    body=html,
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                 'sitesecureurl' : CFG_SITE_SECURE_URL,
                                 'ln': argd['ln'],
                                 'account' : _("Your Account"),
                              },
                    description=_("%s Personalize, Display alerts") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def remove(self, req, form):
        """
        Remove an alert from the DB.
        """

        argd = wash_urlargd(form, {'name': (str, None),
                                   'idq': (int, None),
                                   'idb': (int, None),
                                   })

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/remove" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/remove%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        try:
            html = perform_remove_alert(argd['name'], argd['idq'],
                                                 argd['idb'], uid, ln=argd['ln'])
        except AlertError, msg:
            return page(title=_("Error"),
                        body=webalert_templates.tmpl_errorMsg(ln=argd['ln'], error_msg=msg),
                        navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                     'sitesecureurl' : CFG_SITE_SECURE_URL,
                                     'ln': argd['ln'],
                                     'account' : _("Your Account"),
                                  },
                        description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        uid=uid,
                        language=argd['ln'],
                        req=req,
                        lastupdated=__lastupdated__,
                        navmenuid='youralerts')


        # register event in webstat
        alert_str = "%s (%d)" % (argd['name'], argd['idq'])
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["remove", alert_str, user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        # display success
        return page(title=_("Display alerts"),
                    body=html,
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                 'sitesecureurl' : CFG_SITE_SECURE_URL,
                                 'ln': argd['ln'],
                                 'account' : _("Your Account"),
                              },
                    description=_("%s Personalize, Display alerts") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def pause(self, req, form):
        """
        Pause an alert.
        """

        argd = wash_urlargd(form, {'name' : (str, None),
                                   'idq'  : (int, None),
                                   'idb'  : (int, None),
                                   'ln'   : (str, CFG_SITE_LANG),
                                  })

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/pause" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/pause%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        try:
            html = perform_pause_alert(argd['name'],
                                       argd['idq'],
                                       argd['idb'],
                                       uid,
                                       ln=argd['ln'])
        except AlertError, msg:
            return page(title=_("Error"),
                        body=webalert_templates.tmpl_errorMsg(ln=argd['ln'], error_msg=msg),
                        navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                     'sitesecureurl' : CFG_SITE_SECURE_URL,
                                     'ln': argd['ln'],
                                     'account' : _("Your Account"),
                                  },
                        description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        uid=uid,
                        language=argd['ln'],
                        req=req,
                        lastupdated=__lastupdated__,
                        navmenuid='youralerts')

        # register event in webstat
        alert_str = "%s (%d)" % (argd['name'], argd['idq'])
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["pause", alert_str, user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        # display success
        return page(title=_("Display alerts"),
                    body=html,
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                 'sitesecureurl' : CFG_SITE_SECURE_URL,
                                 'ln': argd['ln'],
                                 'account' : _("Your Account"),
                              },
                    description=_("%s Personalize, Display alerts") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def resume(self, req, form):
        """
        Resume an alert.
        """

        argd = wash_urlargd(form, {'name' : (str, None),
                                   'idq'  : (int, None),
                                   'idb'  : (int, None),
                                   'ln'   : (str, CFG_SITE_LANG),
                                  })

        uid = getUid(req)

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/resume" % \
                                             (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % (
                CFG_SITE_SECURE_URL,
                make_canonical_urlargd({
                    'referer' : "%s/youralerts/resume%s" % (
                        CFG_SITE_SECURE_URL,
                        make_canonical_urlargd(argd, {})),
                    "ln" : argd['ln']}, {})))

        # load the right language
        _ = gettext_set_language(argd['ln'])
        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        try:
            html = perform_resume_alert(argd['name'],
                                          argd['idq'],
                                          argd['idb'],
                                          uid,
                                          ln=argd['ln'])
        except AlertError, msg:
            return page(title=_("Error"),
                        body=webalert_templates.tmpl_errorMsg(ln=argd['ln'], error_msg=msg),
                        navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                     'sitesecureurl' : CFG_SITE_SECURE_URL,
                                     'ln': argd['ln'],
                                     'account' : _("Your Account"),
                                  },
                        description=_("%s Personalize, Set a new alert") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                        uid=uid,
                        language=argd['ln'],
                        req=req,
                        lastupdated=__lastupdated__,
                        navmenuid='youralerts')

        # register event in webstat
        alert_str = "%s (%d)" % (argd['name'], argd['idq'])
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["resume", alert_str, user_str])
        except:
            register_exception(suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        # display success
        return page(title=_("Display alerts"),
                    body=html,
                    navtrail= """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                 'sitesecureurl' : CFG_SITE_SECURE_URL,
                                 'ln': argd['ln'],
                                 'account' : _("Your Account"),
                              },
                    description=_("%s Personalize, Display alerts") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts')

    def popular(self, req, form):
        """
        Display a list of popular alerts.
        """

        argd = wash_urlargd(form, {'ln': (str, "en")})

        uid = getUid(req)

        # load the right language
        _ = gettext_set_language(argd['ln'])

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/popular" % \
                                            (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")
        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" % \
                                        (CFG_SITE_SECURE_URL,
                                         make_canonical_urlargd(
                                            {'referer' : "%s/youralerts/popular%s" % (
                                                CFG_SITE_SECURE_URL,
                                                make_canonical_urlargd(argd, {})),
                                             'ln' : argd['ln']},
                                            {})
                                         )
            )

        user_info = collect_user_info(req)
        if not user_info['precached_usealerts']:
            return page_not_authorized(req, "../", \
                                       text = _("You are not authorized to use alerts."))

        # register event in webstat
        if user_info['email']:
            user_str = "%s (%d)" % (user_info['email'], user_info['uid'])
        else:
            user_str = ""
        try:
            register_customevent("alerts", ["popular", "", user_str])
        except:
            register_exception(
                suffix="Do the webstat tables exists? Try with 'webstatadmin --load-config'")

        return page(title=_("Popular Alerts"),
                    body = perform_request_youralerts_popular(ln=argd['ln']),
                    navtrail = """<a class="navtrail" href="%(sitesecureurl)s/youraccount/display?ln=%(ln)s">%(account)s</a>""" % {
                                  'sitesecureurl' : CFG_SITE_SECURE_URL,
                                  'ln': argd['ln'],
                                  'account' : _("Your Account"),
                                  },
                    description=_("%s Personalize, Popular Alerts") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    keywords=_("%s, personalize") % CFG_SITE_NAME_INTL.get(argd['ln'], CFG_SITE_NAME),
                    uid=uid,
                    language=argd['ln'],
                    req=req,
                    lastupdated=__lastupdated__,
                    navmenuid='youralerts',
                    secure_page_p=1)

    def APD(self, req, form):
        """
        Handler for subscribing/unsubscribing from ATLAS Publication Drafts
        alerts.
        """

        argd = wash_urlargd(form, {'RN': (str, None),
                                   'subscribe': (int, 1),
                                   'ln': (str, CFG_SITE_LANG),
                                   }
                            )

        uid = getUid(req)
        RN = argd['RN']
        subscribe = argd['subscribe']

        if CFG_ACCESS_CONTROL_LEVEL_SITE >= 1:
            return page_not_authorized(req, "%s/youralerts/APD" %
                                            (CFG_SITE_SECURE_URL,),
                                       navmenuid="youralerts")

        elif uid == -1 or isGuestUser(uid):
            return redirect_to_url(req, "%s/youraccount/login%s" %
                                        (CFG_SITE_SECURE_URL,
                                         make_canonical_urlargd(
                                          {'referer': "%s/youralerts/APD%s" % (
                                             CFG_SITE_SECURE_URL,
                                             make_canonical_urlargd(argd, {})),
                                           'ln': argd['ln']},
                                           {})
                                         )
                                   )

        user_info = collect_user_info(req)

        # check that the report number followes a specific pattern
        # (that we are dealing with an ATLAS Publication Draft)
        ATLASPublDraft_pattern = re.compile(r'^ATLAS-[A-Z]+-\d{4}-\d+-\d{3}$')
        if not ATLASPublDraft_pattern.match(RN):
            return page_not_authorized(req, "../",
                                       text="You are not authorized to set up alerts for this report number.")

        # find the recid associated
        try:
            recid = perform_request_search(p='"{0}"'.format(RN), f='reportnumber', c=['ATLAS Publication Drafts'])[0]
        except IndexError:
            return page_not_authorized(req, "../",
                                       text="You are not authorized to set up alerts for this report number.")

        # check that user can access the record
        (auth_code, dummy) = check_user_can_view_record(user_info, recid)
        if auth_code != 0:
            return page_not_authorized(req, "../",
                                       text="You are not authorized to set up alerts for this record.")

        success = False

        if user_info['email']:
            if subscribe:
                success = APD_alert(RN, user_info['email'], True)
            else:
                success = APD_alert(RN, user_info['email'], False)

        if not success:
            return page_not_authorized(req, "../",
                                       text="You are not authorized to subscribe or unsubscribe for alerts for this record.")

        return redirect_to_url(req, "{0}/record/{1}".format(CFG_SITE_SECURE_URL, recid))
