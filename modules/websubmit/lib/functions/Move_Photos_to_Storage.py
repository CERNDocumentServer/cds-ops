## This file is part of Invenio.
## Copyright (C) 2010, 2011, 2012, 2013, 2014 CERN.
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
"""WebSubmit function - Batch photo uploader

To be used with WebSubmit element 'Upload_Photos' or one of its
derivatives in order to create a batch photos uploader.

Requirements:
=============
 JQuery:
  - jquery.min.js

 Plupload 1.5.8 (jQuery plugin)

Note
----
Please download http://www.plupload.com/download
to your /js folder. The stracture should be
  - /js/plupload/plupload.full.js
  - /js/plupload/jquery.plupload.queue/jquery.plupload.queue.js
(or run $make install-plupload-plugin from the root folder of the Invenio sources)
"""

import os
import time
import re
from urllib import quote
from cgi import escape

from invenio.bibdocfile import BibRecDocs, InvenioBibDocFileError
from invenio.config import CFG_BINDIR, CFG_SITE_URL
from invenio.dbquery import run_sql
from invenio.websubmit_icon_creator import create_icon, \
                                           create_crop, \
                                           InvenioWebSubmitIconCreatorError, \
                                           InvenioWebSubmitCropCreatorError

from invenio.bibdocfile import decompose_file
from invenio.bibdocfile_config import CFG_BIBDOCFILE_DEFAULT_ICON_SUBFORMAT
from invenio.websubmit_config import CFG_WEBSUBMIT_CROP_PREVIEW_SIZE


def Move_Photos_to_Storage(parameters, curdir, form, user_info=None):
    """
    The function moves files received from the submission's form
    through the PHOTO_MANAGER element and its asynchronous uploads at
    CFG_SITE_URL/submit/uploadfile.

    Parameters:
        @iconsize - Seperate multiple sizes with commas. The ImageMagick geometry inputs are supported.
              Use type 'geometry' as defined in ImageMagick.
              (eg. 320 or 320x240 or 100> or 5%)
              Example: "180>,700>" will create two icons, one with maximum dimension 180px, one 700px
        @iconformat - Allowed extensions (as defined in websubmit_icon_creator.py) are:
                "pdf", "gif", "jpg",
                "jpeg", "ps", "png", "bmp"
                "eps", "epsi", "epsf"

    The PHOTO_MANAGER elements builds the following file organization
    in the directory curdir::

                                     curdir/
                                        |
         ______________________________________________________________________
        |                                   |                                  |
      files/                         PHOTO_MANAGER_ICONS                     icons/
        |                            PHOTO_MANAGER_ORDER                       |
     (user id)/                      PHOTO_MANAGER_DELETE                  (user id)/
        |                            PHOTO_MANAGER_NEW                         |
     NewFile/                        PHOTO_MANAGER_DESCRIPTION_X           NewFile/
        |                                                                      |
        _______________________                                      _____________________
       |            |          |                                    |          |          |
     photo1.jpg  myPhoto.gif   ...                             photo1.jpg  myPhoto.gif   ...


    where the files are:
      - PHOTO_MANAGER_ORDER: ordered list of file IDs. One per line.

      - PHOTO_MANAGER_ICONS: mappings from file IDs to URL of the icons.
                             One per line. Separator: /

      - PHOTO_MANAGER_NEW: mapping from file ID to filename on disk. Only
                           applicable to files that have just been
                           uploaded (i.e. not bibdocfiles). One per
                           line. Separator: /

      - PHOTO_MANAGER_DELETE: list of files IDs that must be deleted. One
                               per line

      - PHOTO_MANAGER_DESCRIPTION_X, where X is file ID: contains photos
                                     descriptions (one per file)

    """
    global sysno

    icon_sizes = parameters.get('iconsize').split(',')
    icon_format = parameters.get('iconformat')
    if not icon_format:
        icon_format = 'gif'

    PHOTO_MANAGER_ICONS = read_param_file(curdir, 'PHOTO_MANAGER_ICONS', split_lines=True)
    photo_manager_icons_dict = dict([value.split('/', 1) \
                                     for value in PHOTO_MANAGER_ICONS \
                                     if '/' in value])
    PHOTO_MANAGER_ORDER = read_param_file(curdir, 'PHOTO_MANAGER_ORDER', split_lines=True)
    photo_manager_order_list = [value for value in PHOTO_MANAGER_ORDER if value.strip()]
    PHOTO_MANAGER_DELETE = read_param_file(curdir, 'PHOTO_MANAGER_DELETE', split_lines=True)
    photo_manager_delete_list = [value for value in PHOTO_MANAGER_DELETE if value.strip()]
    PHOTO_MANAGER_NEW = read_param_file(curdir, 'PHOTO_MANAGER_NEW', split_lines=True)
    photo_manager_new_dict = dict([value.split('/', 1) \
                               for value in PHOTO_MANAGER_NEW \
                               if '/' in value])

    PHOTO_MANAGER_CROP = read_param_file(curdir,
                                         'PHOTO_MANAGER_CROPPING',
                                         split_lines=True)
    photo_manager_crop_dict = dict([value.split('/', 1)
                                   for value in PHOTO_MANAGER_CROP
                                   if '/' in value])

    # Create an instance of BibRecDocs for the current recid(sysno)
    bibrecdocs = BibRecDocs(sysno)
    for photo_id in photo_manager_order_list:
        photo_description = read_param_file(curdir, 'PHOTO_MANAGER_DESCRIPTION_' + photo_id)
        # We must take different actions depending if we deal with a
        # file that already exists, or if it is a new file
        if photo_id in photo_manager_new_dict.keys():
            # New file
            if photo_id not in photo_manager_delete_list:
                filename = photo_manager_new_dict[photo_id]
                filepath = os.path.join(curdir, 'files', str(user_info['uid']),
                                        'file', filename)
                icon_filename = os.path.splitext(filename)[0] + ".gif"
                fileiconpath = os.path.join(curdir, 'icons',
                                            str(user_info['uid']), 'file',
                                            icon_filename)

                # Add the file
                if os.path.exists(filepath):
                    _do_log(curdir, "Adding file %s" % filepath)
                    bibdoc = bibrecdocs.add_new_file(filepath,
                                                     doctype="picture",
                                                     never_fail=True)
                    has_added_default_icon_subformat_p = False
                    # check if there is cropversion for this image
                    has_crop = photo_id in photo_manager_crop_dict.keys()
                    if has_crop:
                        # ok was the vars
                        dimensions = dict(x.split('=')
                                          for x in
                                          photo_manager_crop_dict[photo_id].split('&'))
                        # perfect let's now create the cropped version
                        # in order to pass it to the icon_sized bellow
                        # and have the same sizes for the cropped version
                        try:
                            # OK lets create the crop DAH!
                            (crop_path, crop_name) = create_crop(
                                filepath,
                                dimensions['w'].split('.')[0],
                                dimensions['h'].split('.')[0],
                                dimensions['x'].split('.')[0],
                                dimensions['y'].split('.')[0]
                            )
                            _do_log(curdir,
                                    "Crop file and name %s: %s"
                                    % (crop_path, crop_name))
                            crop_file_path = os.path.join(crop_path, crop_name)
                            # Add a new file format
                            # Get first the enxtension
                            (dummy, dummy, ext) = decompose_file(crop_file_path)
                            bibdoc.add_file_new_format(crop_file_path,
                                                       docformat='%s;crop' % (ext),
                                                       )
                        except InvenioWebSubmitCropCreatorError, e:
                            _do_log(curdir,
                                    "Cropped couldn't be created to %s: %s"
                                    % (filepath, e))
                            pass

                    has_added_default_icon_subformat_p = False
                    for icon_size in icon_sizes:
                        # Create icon if needed
                        try:
                            (icon_path, icon_name) = create_icon(
                                {'input-file': filepath,
                                 'icon-name': icon_filename,
                                 'icon-file-format': icon_format,
                                 'multipage-icon': False,
                                 'multipage-icon-delay': 100,
                                 'icon-scale': icon_size,
                                 'verbosity': 0,
                                 })
                            fileiconpath = os.path.join(icon_path, icon_name)
                        except InvenioWebSubmitIconCreatorError, e:
                            _do_log(curdir,
                                    "Icon could not be created to %s: %s"
                                    % (filepath, e))
                        if os.path.exists(fileiconpath):
                            try:
                                if not has_added_default_icon_subformat_p:
                                    bibdoc.add_icon(fileiconpath)
                                    has_added_default_icon_subformat_p = True
                                    _do_log(curdir, "Added icon %s" % fileiconpath)
                                else:
                                    icon_suffix = icon_size.replace('>', '').replace('<', '').replace('^', '').replace('!', '')
                                    bibdoc.add_icon(fileiconpath, subformat=CFG_BIBDOCFILE_DEFAULT_ICON_SUBFORMAT + "-" + icon_suffix)
                                    _do_log(curdir, "Added icon %s" % fileiconpath)
                            except InvenioBibDocFileError, e:
                                # Most probably icon already existed.
                                pass

                    if photo_description and bibdoc:
                        for file_format in [bibdocfile.get_format() \
                                       for bibdocfile in bibdoc.list_latest_files()]:
                            bibdoc.set_comment(photo_description, file_format)
                            _do_log(curdir, "Added comment %s" % photo_description)
        else:
            # Existing file
            bibdocname = bibrecdocs.get_docname(int(photo_id))
            bibdoc = bibrecdocs.get_bibdoc(bibdocname)
            if photo_id in photo_manager_delete_list:
                # In principle we should not get here. but just in case...
                bibrecdocs.delete_bibdoc(bibdocname)
                _do_log(curdir, "Deleted  %s" % bibdocname)
            else:
                # Check if a new crop
                has_crop = photo_id in photo_manager_crop_dict.keys()
                _do_log(curdir, "I'm here on modification for photo_id %s" % photo_id)
                if has_crop:
                    # ok was the vars
                    dimensions = dict(x.split('=')
                                      for x in
                                      photo_manager_crop_dict[photo_id].split('&'))
                    # perfect let's now create the cropped version
                    # in order to pass it to the icon_sized bellow
                    # and have the same sizes for the cropped version
                    try:
                        filepath = [file.get_full_path() for file in bibdoc.list_all_files() if file.get_subformat() == ''][0]
                        # OK lets create the crop DAH!
                        (crop_path, crop_name) = create_crop(
                            filepath,
                            dimensions['w'].split('.')[0],
                            dimensions['h'].split('.')[0],
                            dimensions['x'].split('.')[0],
                            dimensions['y'].split('.')[0]
                        )

                        crop_file_path = os.path.join(crop_path, crop_name)

                        # Add a new file format
                        (dummy, dummy, ext) = decompose_file(crop_file_path)

                        # Get first the enxtension
                        format_name = '%s;crop' %(ext)

                        # Check if the format already exists
                        if bibdoc.format_already_exists_p(format_name):
                            match_crop_re = re.compile('crop')
                            bibdoc.delete_icon(match_crop_re)
                        # Add the crop
                        bibdoc.add_file_new_format(crop_file_path, docformat=format_name)
                    except InvenioWebSubmitCropCreatorError, e:
                        _do_log(curdir,
                                "Cropped couldn't be created to %s: %s"
                                % (filepath, e))
                        pass

                # Update the descriptions
                if bibdoc:
                    for file_format in [bibdocfile.get_format() \
                                   for bibdocfile in bibdoc.list_latest_files()]:
                        bibdoc.set_comment(photo_description, file_format)
                        _do_log(curdir, "Added comment %s" % photo_description)

    # Now delete requeted files
    for photo_id in photo_manager_delete_list:
        try:
            bibdocname = bibrecdocs.get_docname(int(photo_id))
            bibrecdocs.delete_bibdoc(bibdocname)
            _do_log(curdir, "Deleted  %s" % bibdocname)
        except:
            # we tried to delete a photo that does not exist (maybe already deleted)
            pass

    # Update the MARC
    _do_log(curdir, "Asking bibdocfile to fix marc")
    bibdocfile_bin = os.path.join(CFG_BINDIR, 'bibdocfile --yes-i-know')
    os.system(bibdocfile_bin + " --fix-marc --recid=" + str(sysno))

    # Delete the HB BibFormat cache in the DB, so that the fulltext
    # links do not point to possible dead files
    run_sql("DELETE LOW_PRIORITY from bibfmt WHERE format='HB' AND id_bibrec=%s", (sysno,))
    return ""


def read_param_file(curdir, param, split_lines=False):
    "Helper function to access files in submission dir"
    param_value = ""
    path = os.path.join(curdir, param)
    try:
        if os.path.abspath(path).startswith(curdir):
            fd = file(path)
            if split_lines:
                param_value = [line.strip() for line in fd.readlines()]
            else:
                param_value = fd.read()
            fd.close()
    except Exception, e:
        _do_log(curdir, 'Could not read %s: %s' % (param, e))
    return param_value


def _do_log(log_dir, msg):
    """
    Log what we have done, in case something went wrong.
    Nice to compare with bibdocactions.log

    Should be removed when the development is over.
    """
    log_file = os.path.join(log_dir, 'performed_actions.log')
    file_desc = open(log_file, "a+")
    file_desc.write("%s --> %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    file_desc.close()


def get_session_id(req, uid, user_info):
    """
    Returns by all means the current session id of the user.

    Raises ValueError if cannot be found
    """
    # Get the session id
    # This can be later simplified once user_info object contain 'sid' key
    session_id = None
    try:
        try:
            session_id = req._session.sid()
        except AttributeError, e:
            # req was maybe not available (for eg. when this is run
            # through Create_Modify_Interface.py)
            session_id = user_info['session']
    except Exception, e:
        raise ValueError("Cannot retrieve user session")

    return session_id


def create_photos_manager_interface(sysno, session_id, uid,
                                    doctype, indir, curdir, access,
                                    can_delete_photos=True,
                                    can_reorder_photos=True,
                                    can_upload_photos=True,
                                    editor_width=None,
                                    editor_height=None,
                                    initial_slider_value=100,
                                    max_slider_value=200,
                                    min_slider_value=80):
    """
    Creates and returns the HTML of the photos manager interface for
    submissions.
    Some of the parameters have been deprecated, and are not used, but
    were kept for maintaining backwards compatibility.

    @param sysno: current record id
    @param session_id: user session_id (as retrieved by get_session_id(...) )
    @param uid: user id
    @param doctype: doctype of the submission
    @param indir: submission "indir"
    @param curdir: submission "curdir"
    @param access: submission "access"
    @param can_delete_photos (deprecated, not used): if users can delete photos
    @param can_reorder_photos (deprecated, not used): if users can reorder photos
    @param can_upload_photos: if users can upload photos
    @param editor_width (deprecated, not used): width (in pixels) of the editor
    @param editor_height (deprecated, not used): height (in pixels) of the editor
    @param initial_slider_value (deprecated, not used): initial value of the photo size slider
    @param max_slider_value (deprecated, not used): max value of the photo size slider
    @param min_slider_value (deprecated, not used): min value of the photo size slider
    """

    out = ''
    PHOTO_MANAGER_CROP = read_param_file(curdir, 'PHOTO_MANAGER_CROP', split_lines=True)
    photo_manager_crop_dict = dict([value.split('/', 1) for value in PHOTO_MANAGER_CROP if '/' in value])

    PHOTO_MANAGER_ICONS = read_param_file(curdir, 'PHOTO_MANAGER_ICONS', split_lines=True)
    photo_manager_icons_dict = dict([value.split('/', 1) for value in PHOTO_MANAGER_ICONS if '/' in value])
    PHOTO_MANAGER_ORDER = read_param_file(curdir, 'PHOTO_MANAGER_ORDER', split_lines=True)
    photo_manager_order_list = [value for value in PHOTO_MANAGER_ORDER if value.strip()]
    PHOTO_MANAGER_DELETE = read_param_file(curdir, 'PHOTO_MANAGER_DELETE', split_lines=True)
    photo_manager_delete_list = [value for value in PHOTO_MANAGER_DELETE if value.strip()]
    PHOTO_MANAGER_NEW = read_param_file(curdir, 'PHOTO_MANAGER_NEW', split_lines=True)
    photo_manager_new_dict = dict([value.split('/', 1) for value in PHOTO_MANAGER_NEW if '/' in value])
    photo_manager_descriptions_dict = {}
    photo_manager_photo_fullnames = {}
    photo_manager_meta = {}
    # Compile a regular expression that can match the "default" icon,
    # and not larger version.
    CFG_BIBDOCFILE_ICON_SUBFORMAT_RE_DEFAULT = re.compile(CFG_BIBDOCFILE_DEFAULT_ICON_SUBFORMAT + '\Z')

    crop_link = """<a rel='crop' href='javascript:void(0)' data-type="modify"
                      data-icon-1440='%(icon_1440)s' data-path='%(fullpath)s'
                      data-id='%(doc_id)s' data-name='%(fullname)s'
                      data-thumb='%(icon_url)s'>
                   %(crop_text)s
                  </a> """

    # Load the existing photos from the DB if we are displaying
    # this interface for the first time, and if a record exists
    if sysno and not PHOTO_MANAGER_ORDER:
        bibarchive = BibRecDocs(sysno)
        for doc in bibarchive.list_bibdocs():
            if doc.get_icon() is not None:
                doc_id = str(doc.get_id())
                photo_manager_meta[doc_id] = {}
                icon_url = doc.get_icon(subformat_re=CFG_BIBDOCFILE_ICON_SUBFORMAT_RE_DEFAULT).get_url()
                description = ""

                sizes = dict([(x.get_subformat() if x.get_subformat() != '' else 'master',
                          (x.get_url(), x.get_full_path())) for x in doc.list_all_files()])

                # Check if image is cropped
                is_cropped = True if 'crop' in sizes.keys() else False
                photo_manager_meta[doc_id].update({'is_cropped': is_cropped})

                # if the master format is missing the image cannot be cropped
                image_can_be_cropped = True if 'master' in sizes.keys() and sizes['master'][1] else False
                photo_manager_meta[doc_id].update({'can_cropped': image_can_be_cropped})

                if image_can_be_cropped:
                    try:
                        image_preview_size = sizes[CFG_WEBSUBMIT_CROP_PREVIEW_SIZE][0]
                    except:
                        image_preview_size = sizes['master'][0]

                    photo_manager_meta[doc_id].update({'preview_image': image_preview_size})
                    photo_manager_meta[doc_id].update({'fullpath': sizes['master'][1]})

                for bibdoc_file in doc.list_latest_files():
                    # format = bibdoc_file.get_format().lstrip('.').upper()
                    # url = bibdoc_file.get_url()
                    # photo_files.append((format, url))
                    if not description and bibdoc_file.get_comment():
                        description = escape(bibdoc_file.get_comment())
                photo_manager_descriptions_dict[doc_id] = description
                photo_manager_icons_dict[doc_id] = icon_url
                try:
                    photo_manager_photo_fullnames[doc_id] = bibdoc_file.fullname
                except:
                    photo_manager_photo_fullnames[doc_id] = ""
                photo_manager_order_list.append(doc_id)

    # Prepare the list of photos to display.
    photos_img = []
    for doc_id in photo_manager_order_list:

        if doc_id not in photo_manager_icons_dict.keys():
            continue

        icon_url = photo_manager_icons_dict[doc_id]
        fullname = photo_manager_photo_fullnames[doc_id]

        if PHOTO_MANAGER_ORDER:
            # Get description from disk only if some changes have been done
            description = escape(read_param_file(curdir,
                                 'PHOTO_MANAGER_DESCRIPTION_' + doc_id))
        else:
            description = escape(photo_manager_descriptions_dict[doc_id])

        link_to_crop = ''
        if photo_manager_meta[doc_id]['can_cropped']:
            link_to_crop = crop_link % {'crop_text': 'Cropped (change)' if photo_manager_meta[doc_id]['is_cropped'] else 'Crop',
                                        'icon_1440': photo_manager_meta[doc_id]['preview_image'],
                                        'fullpath': photo_manager_meta[doc_id]['fullpath'],
                                        'fullname': fullname,
                                        'doc_id': doc_id,
                                        'icon_url': icon_url}
        photos_img.append('''
        <div class='previewer' id='%(doc_id)s'>
            <div data-id='%(doc_id)s' class='thumbnail'>
                <a href='javascript:void(0)'  class='remove_image' data-file='%(fullname)s' data-id='%(doc_id)s'><img src='%(CFG_SITE_URL)s/img/wb-delete-basket.png'/></a>
                <div class='thumbnail-wrapper'>
                <img class='imageIcon' src='%(icon_url)s' />
                </div>
                <div style='clear:both'></div>
                %(crop_link)s
                <span class='filename'>%(fullname)s</span>
                <textarea placeholder='Add an english description' id='PHOTO_MANAGER_DESCRIPTION_%(doc_id)s' name='PHOTO_MANAGER_DESCRIPTION_%(doc_id)s'>%(description)s</textarea>
                <div class='clear:both'></div>
            </div>
        </div>''' % {'fullname': fullname,
                     'doc_id': doc_id,
                     'CFG_SITE_URL': CFG_SITE_URL,
                     'crop_link': link_to_crop,
                     'icon_url': icon_url,
                     'description': description})

    out += '''
    <!-- Required scripts -->
    <script type="text/javascript" src="%(CFG_SITE_URL)s/js/json2.js"></script>
    <script type="text/javascript" src="%(CFG_SITE_URL)s/static/magnific_popup/jquery.magnific-popup.min.js"></script>
    <script type="text/javascript" src="%(CFG_SITE_URL)s/js/crop.js"></script>
    <script type="text/javascript" src="%(CFG_SITE_URL)s/static/crop/jquery.Jcrop.min.js"></script>

    <script type="text/javascript" src="%(CFG_SITE_URL)s/js/plupload/plupload.full.js"></script>
    <script type="text/javascript" src="%(CFG_SITE_URL)s/js/plupload/jquery.plupload.queue/jquery.plupload.queue.js"></script>
    <!-- Required scripts -->
    <!-- Required CSS -->
    <link rel="stylesheet" href="%(CFG_SITE_URL)s/img/websubmit.css" type="text/css" />
    <link rel="stylesheet" href="%(CFG_SITE_URL)s/static/magnific_popup/magnific-popup.css" type="text/css" />
    <link rel="stylesheet" href="%(CFG_SITE_URL)s/static/crop/jquery.Jcrop.min.css" type="text/css" />
    <!-- Required CSS -->
    <style type="text/css">
        .button-wrapper{
            background: #fff;
            padding: 10px;
        }
        .jcrop-holder{
            margin: 0 auto;
        }
        .button-wrapper a{
            padding: 5px 15px ;
        }
        .white-popup-big{
            background: #222;
        }
        .white-popup-content{
            padding:10px;
        }
        .empty-state{
            margin: 0 auto;
            padding: 20px;
            display: block;
        }
        #target{
            max-width:960px;
        }
        .button-wrapper-close{
            text-align:right;
         }
    </style>
    <script type="text/javascript">

    $(document).ready(function() {
        var $images   = []
          , $ids      = []
          , $replaced = []
          , deferred  = $.Deferred()
          , $message = $('.uploader-alert');

        /* Uploading */
        if (%(can_upload_photos)s) {
            var uploader = new  plupload.Uploader({
                runtimes      : 'html5,html4',
                drop_element  : 'drop-zone-label',
                browse_button : 'drop-zone-label',
                url           : '/submit/uploadfile',
                filters :[
                    {title : "Image files", extensions : "jpg,gif,png,jpeg,tiff,tif,eps"},
                    {title : "Document files", extensions: "pdf,lpdf"}
                ],
                multipart_params : {
                    'session_id' : '%(session_id)s',
                    'indir'      : '%(indir)s',
                    'doctype'    : '%(doctype)s',
                    'access'     : '%(access)s',
                    'replace'    : 'false'
                }
            });

            /* Uploader Init */
            uploader.bind('Init', function(up, params){
                // If browser supports drag&drop
                if(uploader.features.dragdrop){
                    var target = document.getElementById('drop-zone-label');
                    target.ondragover = function(event) {
                        this.className = "dragover";
                        event.dataTransfer.dropEffect = "copy";
                    };
                    target.ondragleave = function() {
                        this.className = "dragleave";
                    };
                    target.ondrop = function() {
                        var that = this;
                        this.className = "dragdrop";
                        setTimeout(function(){
                            that.className = "";
                        }, 1000)
                    };
                    target.ondragend = function(){
                        this.className = "dragleave";
                    };
                }
            });
            uploader.init();
            /* Files Added */
            uploader.bind('FilesAdded', function(up, files){
                var add = true;
                var duplicates = [];
                $.when($.each(files, function(i, file){
                        add = ($.inArray(file.name, $images) == -1) ? true : false;
                        if(add){
                            $('#filelist').append('<div class="previewer" id="' + file.id + '"><div class="thumbnail">'+
                                                  '<div class="progress"><img src="/img/ajax-loader.gif" /></div>'+
                                                  '</div></div>');
                        }else{
                            // Remove it from queue
                            duplicates.push(i);
                        }
                    })).done(function(){

                        if(duplicates.length > 0){
                            var message;
                            if(duplicates.length == 1){
                                message = 'There is one duplicate ' +
                                          '["+files[duplicates[0]].name+"].' +
                                          '\\n Press ok to replace it' +
                                          'otherwise ancel to ignore it.';
                            }else{
                                message ='There are "+ duplicates.length+"' +
                                          'duplicate files. \\n Press ok ' +
                                          'to replace it otherwise cancel ' +
                                          'to ignore it.';
                            }
                            if(confirm(message)){
                                for(var i=0; i<duplicates.length; i++){
                                    $replaced[files[i].name] = {
                                        'oldID' : $ids[files[i].name],
                                        'newID' : ''
                                    }
                                    delete_image(files[i].name);
                                }
                            }else{
                                for(var i=0; i<duplicates.length; i++){
                                    uploader.removeFile(files[i]);
                                }
                            }
                        }
                        uploader.refresh();
                        uploader.start();
                        uploader.refresh();
                    });
            });
            /* Upload Progress */
            /*uploader.bind('UploadProgress', function(up, file){
            });
            */
            /* Before the upload starts */
            uploader.bind('BeforeUpload', function(up, file){
            });
            /* Error handler */
            uploader.bind('Error', function(up, error){
                var $div = $('<span/>', {
                        class : 'uploader-alert-message',
                        text  : error.file.name + ': ' + error.message,
                    });
                $message.append($div);
                setTimeout(function(){
                    $div.fadeOut().remove();
                }, 5000);
                // Just to make sure that elements are on dom
                setTimeout(function(){
                    uploader.removeFile(error.file.id);
                    $('#'+error.file.id).remove();
                }, 0);
            });
            /* On complete */
            uploader.bind('FileUploaded', function(up, file, response){
                var uploadedImage = $.parseJSON(response.response);
                // build the icon_url
                if(uploadedImage.file.iconName !== undefined){
                    icon_name =  uploadedImage.file.iconName;
                    icon_url  = build_icon_url(icon_name);
                }else{
                    icon_url = '%(CFG_SITE_URL)s/img/file-icon-blank-96x128.gif'
                }
                $images.push(file.name);
                $ids[file.name] = file.id;
                if ($replaced[file.name] !== undefined){
                    $replaced[file.name].newID = file.id;
                    format_picture($replaced[file.name].oldID, file);
                }else{
                    format_picture(file.id, file, uploadedImage.file);
                }
                $('#photo_manager_icons').val($("#photo_manager_icons").val() + '\\n' + file.id + '/' + icon_url);
                $('#photo_manager_new').val($("#photo_manager_new").val() + '\\n' + file.id + '/' + file.name);
            });
        }

        function get_original_image_dimensions(name, fullpath){
            /* It returns the dimensions fo the requested image
             * ====================================================
             * @name (str) : The filename (including the extension)
            */
            var getDef = $.Deferred()
              , fullpath = (fullpath === undefined) ? '' : fullpath;

            $.get(build_icon_url(name, 'files', 'yes', fullpath))
             .done(function(response){getDef.resolve(response);})
             .fail(function(jqxhr, err){getDef.reject();});
             return getDef.promise();
        }

        function build_icon_url(name, type, onlysize, filepath){
            /* It creates the url for the desired size/type image
             * ==================================================
             * @name (str) : The filename (including the extension)
             * @type (str) : In which folder of running directory
             *               you want to search for. Possible values
             *               icon | crop | files (Default: icon)
             * Note
             * ----
             * The icon should be
             * '%(CFG_SITE_URL)s/submit/getuploadedfile?indir=%(indir)s&doctype=%(doctype)s
             * &access=%(access)s&key=file&icon=1&filename=' + icon_name
            */

            // If type is unsigned add the default icon value
            type     = (type     === undefined) ? 'icon' : type;
            onlysize = (onlysize === undefined) ? ''     : onlysize;
            filepath = (filepath === undefined) ? ''     : filepath;

            // Build the data parameters
            var data = $.param({
                'indir'    : '%(indir)s',
                'doctype'  : '%(doctype)s',
                'access'   : '%(access)s',
                'filename' :  name,
                'key'      : 'file',
                'type'     : type,
                'onlysize' : onlysize,
                'filepath' : filepath
            });
            // Return the url
            return '%(CFG_SITE_URL)s/submit/getuploadedfile?'+data
        }

        function create_thumbnail_for_cropping(name){
            /* It creates a 1440 wide image for the cropping interface
             * =======================================================
             * @name   (str) : The filename (including the extension)
             *
             * @return (str) : Image filename
             *
             * Note
             * ----
             * We don't check if already exists beacuse maybe it has
             * been replaced.
            */
            if(deferred.state() == 'pending'){
                deferred.reject('abort');
            }
            deferred = $.Deferred();
            var data     = {
                    'indir'    : '%(indir)s',
                    'doctype'  : '%(doctype)s',
                    'access'   : '%(access)s',
                    'key'      : 'file',
                    'action'   : 'create_ready_to_crop',
                    'filename' : name
                }

            // Make the request
            $.ajax({
                url : '%(CFG_SITE_URL)s/submit/crop_image',
                data : data
            })
            .done(function(response){
                deferred.resolve(build_icon_url(response));
            })
            .fail(function(jqXHR, textStatus, errorThrown){
                deferred.reject(textStatus);
            })
            // return the promise
            return deferred.promise();
        }

        function create_cropped_image(name, crop){
            /* It creates a cropped version of the image
             * =========================================
             * @name   (str) : The filename (including the extension)
             *
             * @return (str) : Image filename
             *
             * Note
             * ----
             * We don't check if already exists beacuse maybe it has
             * been replaced.
            */
            if(deferred.state() == 'pending'){
                deferred.reject('abort');
            }
            deferred = $.Deferred();
            var data     = {
                    'indir'    : '%(indir)s',
                    'doctype'  : '%(doctype)s',
                    'access'   : '%(access)s',
                    'key'      : 'file',
                    'action'   : 'create_the_cropped_version',
                    'filename' : name,
                    'width'    : crop.w,
                    'height'   : crop.h,
                    'pos_x'    : crop.x,
                    'pos_y'    : crop.y,
                }

            // Make the request
            $.ajax({
                url : '%(CFG_SITE_URL)s/submit/crop_image',
                data : data
            })
            .done(function(response){
                deferred.resolve(build_icon_url(response));
            })
            .fail(function(jqXHR, textStatus, errorThrown){
                deferred.reject(textStatus);
            })

            // return the promise
            return deferred.promise();
        }
        /* On crop.click */
        $('body').on('crop.click', function(event, object, current){
            var $data = $(object)
              , $type = $data.data('type');

            /* If type is modify */
            if($type == 'modify'){
                var fullpath  = $data.data('path')
                  , icon_1440 = $data.data('icon-1440');

                $.when(
                    get_original_image_dimensions('', fullpath)
                )
                .done(function(dimensions){
                    $('body')
                    .trigger('overlay.ready', [current, icon_1440, dimensions]);
                })
                .fail(function(error){
                    if(error == 'abort'){
                        // do nothing
                    }else{
                        show_overlay('Sorry, something wrong happend \\n');
                    }
                });
            }else{
                $.when(
                    create_thumbnail_for_cropping($data.data('name')),
                    get_original_image_dimensions($data.data('name'))
                )
                .done(function(response, dimensions){
                    $('body')
                    .trigger('overlay.ready', [current, response, dimensions]);
                })
                .fail(function(error){
                    if(error == 'abort'){
                        // do nothing
                    }else{
                        show_overlay('Sorry, something wrong happend \\n');
                    }
                });
            }
        });
        function show_overlay(message){
            $.magnificPopup.close();
            setTimeout(function(){
                $.magnificPopup.open({
                    modal: true,
                    key: 'crop-popup',
                    midClick: true,
                    type: 'inline',
                    items:{
                        src: '<div class="white-popup">'+
                             '<div class="white-popup-content">'+
                             message +
                             '</div>'+
                             '<div class="button-wrapper button-wrapper-close">'+
                             '<a href="javascript:void(0)" rel="close">Close</a>'+
                             '</div>'+
                             '</div>',
                    }
                });
            }, 0);
        }
        /* On crop.save */
        $('body').on('crop.save', function(event, object, current){
            $('#'+current.id).find('[rel=crop]').html('<span class="mute">Cropped</span> (Change)');
            if($('#photo_manager_cropping').val() == ''){
                $('#photo_manager_cropping').val(current.id + '/' + $.param(current.crop));
            }else{
                $('#photo_manager_cropping').val($("#photo_manager_cropping").val() + '\\n' + current.id + '/' + $.param(current.crop));
            }
            console.log('Manager', $('#photo_manager_cropping').val());
        });

        function delete_image(filename, docid){
            var index = $.inArray(filename, $images);
            if(index > -1){
                var id = $ids[filename];
                delete $images[index];
                delete $ids[filename];
                $("#photo_manager_delete").val($("#photo_manager_delete").val() + '\\n' + id);
            }else if(docid){
                $("#photo_manager_delete").val($("#photo_manager_delete").val() + '\\n' + docid);
            }
        }

        function format_picture(id, file, response){
            // Get urls for cropped preview and thumbnail
            var crop_thumb    = build_icon_url(response.name, 'files')
              , image_thumb   = build_icon_url(response.iconName)
              , image_absPath = response.absPath;

            $('#'+id).html("<div data-id='"+file.id+"' class='thumbnail'>" +
                           "<a href='javascript:void(0)'  class='remove_image' data-file='"+file.name+"' data-id='"+file.id+"'><img src='%(CFG_SITE_URL)s/img/wb-delete-basket.png'/></a>"+
                           "<div class='thumbnail-wrapper'>"+
                           "<img class='imageIcon' src='"+image_thumb+"' />"+
                           "</div>"+
                           "<div style='clear:both'></div>"+
                           "<a rel='crop' href='javascript:void(0)' data-id='"+file.id+"' data-name='"+file.name+"' data-original='"+response.absPath+"' data-thumb='"+crop_thumb+"'>Crop</a>"+
                           "<span class='filename'>"+file.name+"</span>"+
                           "<textarea placeholder='Add an english description' id='PHOTO_MANAGER_DESCRIPTION_"+ file.id +"' name='PHOTO_MANAGER_DESCRIPTION_"+ file.id +"'></textarea>" +
                           "<div class='clear:both'></div>"+
                           "<div class='language_control' data-id='"+file.id+"'> " +
                           "</div>"+
                           "</div>");
        }
        var onclick = $('[type=button]').attr('onclick');
        $('[type=button]').attr('onclick', '');
        $('[type=button]').click(function(e){
            var $that = $(this);
            $that.prop('disabled', true);
            $that.parent().append('<p class="loading">Submiting please wait...</p>');
            e.stopPropagation();
            var theids = [];
            $.when($.each($images, function(index, filename){
                theids.push($ids[filename]);
            })).done(function(){
                // Get also the previous
                current = $('#photo_manager_order').val().split('\\n');
                current = current.concat(theids);
                $('#photo_manager_order').val(current.join('\\n'));
                // Really dirty
                // FIXME: Remove this ungly eval
               var re =  eval(onclick);
               if(re !== undefined){
                $that.attr('disabled', false);
                $that.parent().find('.loading').remove();
               }
            })
        });
        // Bind click for deletion
        $(document).on('click','.remove_image',function(){
            var docid = $(this).data('id');
            var filename = $(this).data('file');
            if (confirm("Are you sure you want to delete the photo? (The file will be deleted after you apply all the modifications)")) {
                delete_image(filename, docid);
                $("[data-id="+docid+"]").parent().remove();
            }
        });
    });
    </script>
    <div class="uploader-alert uploader-alert-hidden"></div>
    <div id="calluploader" class="uploadedImages">
        <div id="dropzone">
            <div id="dropzone-container">
                <div id="drop-zone-label">
                    <h2>Drop your images or click to select.</h2>
                </div>
                <div id="filelist">%(photos_img)s</div>
            </div>
        </div>
    </div>

    <textarea id="photo_manager_icons" style="display:none" name="PHOTO_MANAGER_ICONS">%(PHOTO_MANAGER_ICONS)s</textarea>
    <textarea id="photo_manager_order" style="display:none" name="PHOTO_MANAGER_ORDER">%(PHOTO_MANAGER_ORDER)s</textarea>
    <textarea id="photo_manager_new" style="display:none" name="PHOTO_MANAGER_NEW">%(PHOTO_MANAGER_NEW)s</textarea>
    <textarea id="photo_manager_delete" style="display:none" name="PHOTO_MANAGER_DELETE">%(PHOTO_MANAGER_DELETE)s</textarea>
    <textarea id="photo_manager_cropping" style="display:none" name="PHOTO_MANAGER_CROPPING"></textarea>
    <div style="clear:both;"></div>
    ''' % {'CFG_SITE_URL': CFG_SITE_URL,
           'access': quote(access, safe=""),
           'doctype': quote(doctype, safe=""),
           'indir': quote(indir, safe=""),
           'session_id': quote(session_id, safe=""),
           'PHOTO_MANAGER_ICONS': '\n'.join([key + '/' + value for key, value in photo_manager_icons_dict.iteritems()]),
           'PHOTO_MANAGER_ORDER': '\n'.join(photo_manager_order_list),
           'PHOTO_MANAGER_DELETE': '\n'.join(photo_manager_delete_list),
           'PHOTO_MANAGER_NEW': '\n'.join([key + '/' + value for key, value in photo_manager_new_dict.iteritems()]),
           'photos_img': '\n'.join(photos_img),
           'hide_photo_viewer': (len(photos_img) == 0 and len(photo_manager_new_dict.keys()) == 0) and 'display:none;' or '',
           'delete_hover_class': can_delete_photos and "#sortable li div.imgBlock:hover .hidden {display:inline;}" or '',
           'can_upload_photos': can_upload_photos and 'true' or 'false',
           'upload_display': not can_upload_photos and 'display: none' or '',
           }

    return out
