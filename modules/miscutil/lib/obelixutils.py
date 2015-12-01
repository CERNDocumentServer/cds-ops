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

"""Invenio to obelix-client connector."""

from invenio.bibfield import get_record
from invenio.bibrank_record_sorter import rank_records
from invenio.config import CFG_BASE_URL, \
    CFG_OBELIX_HOST, \
    CFG_OBELIX_PREFIX, \
    CFG_SITE_RECORD
from invenio.errorlib import register_exception
from invenio.intbitset import intbitset
from invenio.webuser import collect_user_info


_OBELIX = None


class ObelixNotExist(object):

    """Empty Object, that accept everything without error."""

    def __getattr__(self, name):
        """Return always None."""
        return lambda *args, **keyargs: None


def get_obelix():
    """Create or get a Obelix instance."""
    global _OBELIX

    recommendation_prefix = "recommendations::"

    if CFG_OBELIX_HOST == "":
        # Obelix is not used, so ignore all calls without error.
        return ObelixNotExist()
    if _OBELIX is None:
        try:
            import json
            import redis
            from obelix_client import Obelix
            from obelix_client.storage import RedisStorage
            from obelix_client.queue import RedisQueue

            obelix_redis = redis.StrictRedis(host=CFG_OBELIX_HOST,
                                             port=6379,
                                             db=0)

            obelix_cache = RedisStorage(obelix_redis, prefix=CFG_OBELIX_PREFIX,
                                        encoder=json)

            recommendation_storage = RedisStorage(obelix_redis,
                                                  prefix=CFG_OBELIX_PREFIX +
                                                  recommendation_prefix,
                                                  encoder=json)

            obelix_queue = RedisQueue(obelix_redis, prefix=CFG_OBELIX_PREFIX,
                                      encoder=json)

            _OBELIX = Obelix(obelix_cache, recommendation_storage,
                             obelix_queue)

        except Exception:
            register_exception(alert_admin=True)
            _OBELIX = None

    return _OBELIX

obelix = get_obelix()


def clean_user_info(user_info):
    """Remove all unwanted information."""
    return {'uid': user_info.get('uid'),
            'referer': user_info.get('referer'),
            'uri': user_info.get('uri'),
            'group': user_info.get('group'),
            '': user_info.get(''),
            }


def get_recommended_records(recid, user_id, collection="", threshold=70,
                            maximum=3):
    """
    Create record recommendations based on word similarity and Recommendations.

    @param collection: Collection to take the suggestions from
    @param threshold: Value between 0 and 100. Only records ranked higher
                      than the value are presented.
    @param maximum: Maximum suggestions to show
    @return: List of recommended records [{
                                          'number': ,
                                          'record_url': ,
                                          'record_title': ,
                                          'record_authors': ,
                                          }, ]
    """
    from invenio.webstat import get_url_customevent
    if CFG_OBELIX_HOST == "":
        # if not obelix:
        return []

    suggestions = []
    similar_records = _find_similar_records(recid, user_id, collection,
                                            threshold)
    rec_count = 1
    for sim_recid in similar_records:
        try:
            record = get_record(sim_recid)
            title = record['title']
            if title:
                title = title['title']
            else:
                continue

            rec_authors = record.get('authors.full_name')
            if rec_authors[0] is None and len(rec_authors) <= 1:
                authors = "; ".join(record.get('corporate_name.name', ""))
            else:
                authors = "; ".join(record['authors.full_name'])
        except (KeyError, TypeError, ValueError):
            continue

        record_url = "%s/%s/%s" % (CFG_BASE_URL, CFG_SITE_RECORD,
                                   str(sim_recid))
        url = get_url_customevent(record_url,
                                  "recommended_record",
                                  [str(recid), str(sim_recid),
                                   str(rec_count), str(user_id)])
        suggestions.append({
                           'number': rec_count,
                           'record_url': url,
                           'record_title': title.strip(),
                           'record_authors': authors.strip(),
                           })
        if rec_count >= maximum:
            break
        rec_count += 1

    return suggestions


def _find_similar_records(recid, user_id=0, collection="", threshold=55):
    """Return a list of similar records."""
    from invenio.search_engine import perform_request_search

    similar_records = []
    collection_recids = intbitset(perform_request_search(
                                  req=collect_user_info(user_id),
                                  cc=collection))
    # rank records by word similarity
    ranking = rank_records('wrd', 0,
                           collection_recids,
                           ['recid:' + str(recid)])
    # ([6, 7], [81, 100], '(', ')', '')

    if not ranking or ranking[1] is None:
        # No items found return nothing
        return []

    # only get the records with high scores
    for list_pos, rank in enumerate(ranking[1]):
        if int(ranking[0][list_pos]) == int(recid):
            continue

        if rank >= threshold:
            similar_records.append(ranking[0][list_pos])

    try:
        # rank records by Obelix
        solution_recs, solution_scores = obelix.rank_records(similar_records,
                                                             user_id,
                                                             rg=20)
    except Exception:
        register_exception(alert_admin=True)
        return []

    return solution_recs
