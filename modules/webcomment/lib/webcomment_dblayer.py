from invenio.dbquery import run_sql
from invenio.bibdocfile import BibRecDocs
import json

def get_cmtrecordcomment_to_bibdocfile_association(recID):
    """
    Retrieves all the associations between the comments of a record
    and bibdocfiles they refer to.
    :param recID: Id of the record
    :return: correlations between comments and bibdocfiles
    """


    query = """SELECT id_record, id_bibdoc, id_comment, version
                   FROM cmtRECORDCOMMENT_bibdocfile
                   WHERE id_record = %s
                """
    comments_to_bibdoc = run_sql(query, (recID,),  with_dict=True)
    bibrecdocs = BibRecDocs(recID)
    files = bibrecdocs.list_bibdocs()
    res = []
    for file in files:
            for comments in comments_to_bibdoc:
                if comments['id_bibdoc'] == file.id:
                    res.append({
                        'version': comments['version'],
                        'id_bibdoc': file.id,
                        'docname': bibrecdocs.get_docname(file.id),
                        'id_comment': comments['id_comment']
                    })
    return res


def add_comment_to_file_association(redID, cmtID, bibdocfileID, version):
    """
    Adds an association of a comment to a bibdocfile
    :param redID: Id of the record
    :param cmtID: Id of the comment
    :param bibdocfileID: Id of the bibdocfile
    """

    query = """INSERT INTO cmtRECORDCOMMENT_bibdocfile
             (id_record, id_comment, id_bibdoc, version)
             VALUES (%s, %s, %s, %s)"""
    res = run_sql(query, (redID, cmtID, bibdocfileID, version))
    return res


def get_bibdocfiles_of_record(recID, only_used_p=False):
    """
    Retrieves all bibdocfiles associated with a record
    :param recID: Id of the record
    :return: array of dictionaries with each dictionary representing a bibdocfile
            dictionary keys are
            ['id_record',  'bibrec_bibdoc',  'id_bibdoc',  'version',  'docname',  'id_comment']
    """


    res = []
    bibrecdocs = BibRecDocs(recID)
    files = bibrecdocs.list_bibdocs()

    for file in files:
        for version in file.list_versions():
            res.append({
                        'version': version,
                        'id_bibdoc': file.id,
                        'docname': bibrecdocs.get_docname(file.id)
                    })

    return res
