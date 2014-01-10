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
from invenio.websubmit_icon_creator import create_icon, InvenioWebSubmitIconCreatorError
from invenio.bibdocfile_config import CFG_BIBDOCFILE_DEFAULT_ICON_SUBFORMAT

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

    ## Create an instance of BibRecDocs for the current recid(sysno)
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
                fileiconpath = os.path.join(curdir, 'icons', str(user_info['uid']),
                                            'file', icon_filename)

                # Add the file
                if os.path.exists(filepath):
                    _do_log(curdir, "Adding file %s" % filepath)
                    bibdoc = bibrecdocs.add_new_file(filepath, doctype="picture", never_fail=True)
                    has_added_default_icon_subformat_p = False
                    for icon_size in icon_sizes:
                        # Create icon if needed
                        try:
                            (icon_path, icon_name) = create_icon(
                                { 'input-file'           : filepath,
                                  'icon-name'            : icon_filename,
                                  'icon-file-format'     : icon_format,
                                  'multipage-icon'       : False,
                                  'multipage-icon-delay' : 100,
                                  'icon-scale'           : icon_size, # Resize only if width > 300
                                  'verbosity'            : 0,
                                  })
                            fileiconpath = os.path.join(icon_path, icon_name)
                        except InvenioWebSubmitIconCreatorError, e:
                            _do_log(curdir, "Icon could not be created to %s: %s" % (filepath, e))
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
            if photo_id in photo_manager_delete_list:
                # In principle we should not get here. but just in case...
                bibrecdocs.delete_bibdoc(bibdocname)
                _do_log(curdir, "Deleted  %s" % bibdocname)
            else:
                bibdoc = bibrecdocs.get_bibdoc(bibdocname)
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
    file_desc.write("%s --> %s\n" %(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    file_desc.close()

def get_session_id(req, uid, user_info):
    """
    Returns by all means the current session id of the user.

    Raises ValueError if cannot be found
    """
    # Get the session id
    ## This can be later simplified once user_info object contain 'sid' key
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
    # Compile a regular expression that can match the "default" icon,
    # and not larger version.
    CFG_BIBDOCFILE_ICON_SUBFORMAT_RE_DEFAULT = re.compile(CFG_BIBDOCFILE_DEFAULT_ICON_SUBFORMAT + '\Z')

    # Load the existing photos from the DB if we are displaying
    # this interface for the first time, and if a record exists
    if sysno and not PHOTO_MANAGER_ORDER:
        bibarchive = BibRecDocs(sysno)
        for doc in bibarchive.list_bibdocs():
            if doc.get_icon() is not None:
                doc_id = str(doc.get_id())
                icon_url = doc.get_icon(subformat_re=CFG_BIBDOCFILE_ICON_SUBFORMAT_RE_DEFAULT).get_url() # Get "default" icon
                description = ""
                bibdoc_file = None
                for bibdoc_file in doc.list_latest_files():
                    if bibdoc_file and bibdoc_file.get_comment() and not description:
                        description = escape(bibdoc_file.get_comment())
                photo_manager_descriptions_dict[doc_id] = description
                photo_manager_icons_dict[doc_id] = icon_url
                try:
                    photo_manager_photo_fullnames[doc_id] = bibdoc_file.fullname
                except:
                    photo_manager_photo_fullnames[doc_id] = ""
                photo_manager_order_list.append(doc_id) # FIXME: respect order

    # Prepare the list of photos to display.
    photos_img = []
    for doc_id in photo_manager_order_list:
        if not photo_manager_icons_dict.has_key(doc_id):
            continue

        icon_url = photo_manager_icons_dict[doc_id]
        fullname = photo_manager_photo_fullnames[doc_id]

        if PHOTO_MANAGER_ORDER:
            # Get description from disk only if some changes have been done
            description = escape(read_param_file(curdir,
                                 'PHOTO_MANAGER_DESCRIPTION_' + doc_id))
        else:
            description = escape(photo_manager_descriptions_dict[doc_id])

        photos_img.append('''
        <div class='previewer' id='%(doc_id)s'>
            <div data-id='%(doc_id)s' data-file_id='%(doc_id)s' data-order='%(doc_id)s' class='thumbnail'>
                <a href='javascript:void(0)'  class='remove_image' data-file='%(fullname)s' data-id='%(doc_id)s'>&cross;</a>
                <div class='thumbnail-wrapper'>
                <img class='imageIcon' src='%(icon_url)s' />
                </div>
                <div style='clear:both'></div>
                <span class='filename'>%(fullname)s</span>
                <textarea placeholder='Add a description' id='PHOTO_MANAGER_DESCRIPTION_%(doc_id)s' name='PHOTO_MANAGER_DESCRIPTION_%(doc_id)s'>%(description)s</textarea>
            </div>
        </div>''' % {
                  'fullname': fullname,
                  'doc_id': doc_id,
                  'icon_url': icon_url,
                  'description': description})

    out += '''
    <!-- Required scripts -->
    <script type="text/javascript" src="/js/plupload/plupload.full.js"></script>
    <script type="text/javascript" src="/js/plupload/jquery.plupload.queue/jquery.plupload.queue.js"></script>
    <!-- Required scripts -->
    <!-- Required CSS -->
    <link rel="stylesheet" href="/img/websubmit.css" type="text/css" />
    <!-- Required CSS -->

    <script type="text/javascript">

    $(document).ready(function() {
        var $images   = []
          , $ids      = []
          , $replaced = []
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
                                message = "There is one duplicate ["+files[duplicates[0]].name+"]. \\n Press ok to replace it otherwise cancel to ignore it.";
                            }else{
                                message = "There are " + duplicates.length + " duplicate files. \\n Press ok to replace it otherwise cancel to ignore it.";
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
                    format_picture(file.id, file);
                }
                $('#photo_manager_icons').val($("#photo_manager_icons").val() + '\\n' + file.id + '/' + icon_url);
                $('#photo_manager_new').val($("#photo_manager_new").val() + '\\n' + file.id + '/' + file.name);
            });
        }

        function build_icon_url(icon_name){
            return '%(CFG_SITE_URL)s/submit/getuploadedfile?indir=%(indir)s&doctype=%(doctype)s&access=%(access)s&key=file&icon=1&filename=' + icon_name
        }
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

        function format_picture(id, file){
            $('#'+id).html("<div data-id='"+file.id+"' data-file_id='"+file.id+"' data-order='"+file.id+"' class='thumbnail'>" +
                           "<a href='javascript:void(0)'  class='remove_image' data-file='"+file.name+"' data-id='"+file.id+"'><img src='/img/wb-delete-basket.png'/></a>"+
                           "<div class='thumbnail-wrapper'>"+
                           "<img class='imageIcon' src='"+icon_url+"' />"+
                           "</div>"+
                           "<div style='clear:both'></div>"+
                           "<span class='filename'>"+file.name+"</span>"+
                           "<textarea placeholder='Add a description' id='PHOTO_MANAGER_DESCRIPTION_"+ file.id +"' name='PHOTO_MANAGER_DESCRIPTION_"+ file.id +"'></textarea>" +
                           "</div>");
        }
        var onclick = $('[type=button]').attr('onclick');
        $('[type=button]').attr('onclick', '');
        $('[type=button]').click(function(e){
            var $that = $(this);
            $that.attr('disabled', true);
            $that.parent().append('<p class="loading">Submiting please wait...</p>');
            e.stopPropagation();
            var theids = [];
            $.when($.each($images, function(index, filename){
                theids.push($ids[filename]);
            })).done(function(){
                $('#photo_manager_order').val(theids.join('\\n'));
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
           'can_upload_photos': can_upload_photos and 'true' or 'false',
           }

    return out
