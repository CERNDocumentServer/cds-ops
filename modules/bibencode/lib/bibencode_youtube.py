# -*- coding: utf-8 -*-
## This file is part of Invenio.
## Copyright (C) 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2015 CERN.
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
"""
Push to YouTube API
===================

Instructions
------------

1. Go to https://cloud.google.com/console
2. Create a new project
3. Navigate to APIs & auth -> APIs and enable
   Youtube Data Api v3 (if it's off)
4. Go to APIs & auth -> Credentials, crate new client id
   (application type web application) and on OAuth section
   download the client_secrets.json by clicking Download
   JSON and upload it to your invenio installation:
   modules/bibencode/etc/client_secrets.json
5. On Public API access create a new Browser key and update
   the value on YOUTUBE_API_KEY Important!
6. That's all, for more infos visit:
   https://developers.google.com/api-client-library/python/guide/aaa_oauth

========== * IMPORTANT NOTE * ==========
Make sure you have executed the command:

`make install-youtube`
========================================
"""
import httplib
import httplib2
import json
import os
import re
from urllib import urlopen, urlencode

from invenio.config import CFG_ETCDIR
from invenio.webuser import (
    collect_user_info, session_param_set, session_param_get
)
from invenio.webinterface_handler import (
   wash_urlargd, WebInterfaceDirectory
)
from invenio.config import CFG_SITE_URL, CFG_CERN_SITE
from invenio.bibencode_config import (
    CFG_BIBENCODE_YOUTUBE_VIDEO_SIZE, CFG_BIBENCODE_YOUTUBE_VIDEO_SIZE_SUBFIELD,
    CFG_BIBENCODE_YOUTUBE_CATEGORIES_API_KEY, CFG_BIBENCODE_YOUTUBE_MIME_TYPES
)
from invenio.search_engine import get_record
from invenio.bibrecord import record_get_field_value, record_get_field_instances
from invenio.bibdocfile import bibdocfile_url_to_fullpath
from invenio import webinterface_handler_config as apache

from oauth2client.client import AccessTokenCredentials
from apiclient.discovery import build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload

"""
Configuratable vars
===================
"""
# YouTube API key for categories
YOUTUBE_API_KEY = CFG_BIBENCODE_YOUTUBE_CATEGORIES_API_KEY

# The size of the video
VIDEO_SIZE = CFG_BIBENCODE_YOUTUBE_VIDEO_SIZE

# Explicitly tell the underlying HTTP transport library not to retry, since
# we are handling retry logic ourselves.
httplib2.RETRIES = 1

# Maximum number of times to retry before giving up.
MAX_RETRIES = 10

# Get the video subfield depending on the site
VIDEO_SUBFIELD = CFG_BIBENCODE_YOUTUBE_VIDEO_SIZE_SUBFIELD

# Always retry when these exceptions are raised.
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, httplib.NotConnected,
  httplib.IncompleteRead, httplib.ImproperConnectionState,
  httplib.CannotSendRequest, httplib.CannotSendHeader,
  httplib.ResponseNotReady, httplib.BadStatusLine)

# Always retry when an apiclient.errors.HttpError with one of these status
# codes is raised.
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
# Get the client secrets
def get_client_secrets():
    """
    A simple way to read parameters from client_secrets.json
    ========================================================
    """
    # build the path for secrets
    path = os.path.join(CFG_ETCDIR, 'bibencode', 'client_secrets.json')

    try:
        with open(path) as data:
            params = json.load(data)
    except IOError:
        raise Exception('There is no client_secrets.json file.')
    except Exception as e:
        raise Exception(str(e))
    else:
        return params

# Save secrets to SECRETS
SECRETS = get_client_secrets()

"""
The web API
===========
"""

class WebInterfaceYoutube(WebInterfaceDirectory):
    _exports = [('upload', 'uploadToYoutube')]

    def uploadToYoutube(self, req, form):
        argd = wash_urlargd(form, {
            'video'         : (str, ''),
            'title'         : (str, ''),
            'description'   : (str, ''),
            'category'      : (str, ''),
            'keywords'      : (str, ''),
            'privacyStatus' : (str, ''),
            'token'         : (str, ''),
        })
        return upload_video(argd)

"""
The templates
=============
"""
def youtube_script(recid):

    style  = """
        <link href="%(site_url)s/img/youtube.css" rel="stylesheet" type="text/css" />
        <style type="text/css">
            .post-auth{
                display: none;
            }
            .overlay-white{
                max-width: 960px;
                background: #fff;
                margin: 0 auto;
                padding: 20px;
                min-height: 100px;
                position: relative;
                }
                .overlay-white-500{
                width: 500px;
                min-height: 100px;
                }
                .overlay-white hr{
                border-color:#fff;
                background: #ddd;
            }
        </style>
    """ % {
        "site_url": CFG_SITE_URL
    }
    script = """
        <script type="text/javascript">
            var OAUTH2_CLIENT_ID = '%(client_id)s';
            var OAUTH2_SCOPES = [
              'https://www.googleapis.com/auth/youtube'
            ];
            googleApiClientReady = function() {};

            function getCategories(){
                var api_key = '%(api_key)s';
                var deff = $.Deferred();
                if(api_key){
                    $.ajax({
                        url : 'https://www.googleapis.com/youtube/v3/videoCategories',
                        data  : {
                            part : 'snippet',
                            regionCode : 'US',
                            key        : api_key
                        },
                        success : function(response){
                            var options = [];
                            for(var i = 0; i<response.items.length; i++){
                                if(response.items[i].snippet.assignable){
                                    var title = response.items[i].snippet.title;
                                    var id    = response.items[i].id;
                                    options.push("<option data-label='"+title+"' value='"+id+"'>"+title+"</option>");
                                }
                            }
                            $('#category').html(options.sort().join(''));
                            deff.resolve(options);
                        },
                        error : function(jqXHR, textStatus, error){
                            /* Youtube categories hard coded! */
                            defaultCategories();
                        }
                    })
                }else{
                    /* Youtube categories hard coded! */
                    defaultCategories();
                }
                deff.promise();
            }
            function defaultCategories(){
                var code = '<option value="2">Autos & Vehicles</option>';
                code += '<option value="23">Comedy</option>';
                code += '<option value="27">Education</option>';
                code += '<option value="24">Entertainment</option>';
                code += '<option value="1">Film & Animation</option>';
                code += '<option value="20">Gaming</option>';
                code += '<option value="26">Howto & Style</option>';
                code += '<option value="10">Music</option>';
                code += '<option value="25">News & Politics</option>';
                code += '<option value="29">Nonprofits & Activism</option>';
                code += '<option value="22">People & Blogs</option>';
                code += '<option value="15">Pets & Animals</option>';
                code += '<option value="28">Science & Technology</option>';
                code += '<option value="17">Sports</option>';
                code += '<option value="19">Travel & Events</option>';
                $('#category').html(code);
            }
            function makeLogin(){
              gapi.auth.init(function() {
                window.setTimeout(checkAuth, 1);
              });
            }
            function checkAuth() {
                gapi.auth.authorize({
                    client_id: OAUTH2_CLIENT_ID,
                    scope: OAUTH2_SCOPES,
                    immediate: true
                }, handleAuthResult);
            }
            function handleAuthResult(authResult) {
              if (authResult && !authResult.error) {
                $('.pre-auth').hide();
                loadAPIClientInterfaces();
                $('#youtube-profile').addClass('linkedProfile');
              } else {
                $('#login-link').click(function() {
                  gapi.auth.authorize({
                    client_id: OAUTH2_CLIENT_ID,
                    scope: OAUTH2_SCOPES,
                    immediate: false
                    }, handleAuthResult);
                });
                $('#youtube-profile').addClass('unlinkedProfile');
                $('.post-auth').hide();
              }
            }
            function loadAPIClientInterfaces() {
              gapi.client.load('youtube', 'v3', function() {
                handleAPILoaded();
              });
            }
            function handleAPILoaded() {
                $.when(getDisplayName()).then(function(){
                    $.when(getCategories()).then(function(){
                        $('.post-auth').show();
                    },function(){
                        $('.post-auth').show();
                    });
                }, function(message){
                    showMessage('error',message);
                    $('#youtube-profile').removeClass('linkedProfile');
                    $('#youtube-profile').addClass('unlinkedProfile');
                });
                $('[name=token]').val(gapi.auth.getToken().access_token)
            }
            function showMessage(type, message){
                $('#messages').fadeOut();
                var inside = $('<div/>',{
                                text:message,
                                class:type
                             })
                $('#messages').html(inside);
                $('#messages').fadeIn();
            }
            function getDisplayName() {
                var deff = $.Deferred();
                $.ajax({
                  dataType: 'json',
                  type: 'GET',
                  url: 'https://gdata.youtube.com/feeds/api/users/default',
                  data: {
                    alt          : 'json',
                    access_token : gapi.auth.getToken().access_token
                  },
                  success: function(responseJson) {
                    var displayName  = responseJson['entry']['title']['$t'];
                    var displayImage = responseJson['entry']['media$thumbnail']['url']
                    var channelURL   = responseJson['entry']['link'][0]['href']
                    // Create the photo
                    var youtubeLeft = '<a href="'+channelURL+'" target="_blank">' +
                                      '<img src="'+displayImage+'" />' +
                                      '</a>';
                    $('.youtube-profile-left').html(youtubeLeft);
                    var youtubeRight = '<a href="'+channelURL+'" target="_blank">' +
                                      '<h2>'+displayName+'</h2>' +
                                      '</a>';
                    $('.youtube-profile-right').html(youtubeRight);
                    deff.resolve();
                  },
                  error: function(jqXHR, textStatus, error) {
                    if(error == 'Unauthorized'){
                        deff.reject('Please make sure that you have linked channel to your account');
                    }else{
                        deff.reject(jqXHR.responseText)
                    }
                  }
                });
                return deff.promise();
            }
            $(document).ready(function(){
                $('.open-push-to-youtube').click(function(){
                    $.magnificPopup.open({
                      items: {
                        src: '#youtube-plugin',
                        type: 'inline'
                      },
                      closeOnBgClick:false,
                    });
                    makeLogin();
                })
                $('#push_to_youtube').submit(function(e){
                    $('#youtube-submit').attr('disabled', true);
                    $('#youtube-submit').text('Loading please wait...');
                    e.preventDefault();
                    var jqxhr = $.ajax({
                        data : $('#push_to_youtube').serialize(),
                        url  : "/youtube/upload"
                    })
                    jqxhr.done(function(response){
                        try{
                            var data = $.parseJSON(response);
                            if(data.success == 'true'){
                                var successMessage = 'The video succesfully uploaded with id:' +
                                                    '<a href="http://youtube.com/watch?v='+data.video+'">'+
                                                    data.video +
                                                    '</a>';
                                showMessage('success', 'The video succesfully uploaded with id: '+data.video);
                                $('#push_to_youtube').fadeOut();
                            }else{
                                showMessage('error', 'Sorry an error occured: ' + data.message)
                                $('#youtube-submit').attr('disabled', false);
                                $('#youtube-submit').text('Push to youtube');
                            }
                        }catch(exception){
                            showMessage('error', 'Sorry an error occured: ' + response)
                            $('#youtube-submit').attr('disabled', false);
                            $('#youtube-submit').text('Push to youtube');
                        }
                    });
                    jqxhr.fail(function(response){
                        try{
                            var data = $.parseJSON(response);
                            showMessage('Sorry an error occured: ' + response.responseText)
                            $('#youtube-submit').attr('disable', false);
                            $('#youtube-submit').text('Submit');
                        }catch(exception){
                            showMessage('Sorry an error occured: ' + response)
                            $('#youtube-submit').attr('disable', false);
                            $('#youtube-submit').text('Submit');
                        }
                    });
                });
            })
            </script>
            <script src="https://apis.google.com/js/client.js?onload=googleApiClientReady"></script>
          """ % {
                    'client_id' : SECRETS.get('web', {}).get('client_id'),
                    'api_key'   : YOUTUBE_API_KEY
                }
    body = """
            <div id="youtube-profile">
                <div class="youtube-profile-left">
                </div>
                <div class="youtube-profile-right">
                </div>
            </div>
            <div id="messages"></div>
            <div id="login-container" class="pre-auth">
                <a href="javascript:void(0)" id="login-link" title="Sign in with YouTube">
                    <img src="/img/sign_in_with_google.png" alt="Sign in with YouTube"/>
                </a>
                <p class='sign-info'>
                    Login with your google account in order to have access to your
                    YouTube account.
                </p>
            </div>
            <div class="post-auth">
                <div id="youtube-container">
                    %(form)s
                </div>
            </div>
            """ % {
                    'form' : create_form(recid)
                  }
    out = """
            <script type="text/javascript" src="%(site_url)s/static/magnific_popup/jquery.magnific-popup.min.js"></script>
            <link href="%(site_url)s/static/magnific_popup/magnific-popup.css" rel="stylesheet" type="text/css"/>
            %(style)s
            %(script)s
            <a href="javascript:void(0)" class="open-push-to-youtube video_button">
                <img src="/img/youtube-logo-icon-24px.png" alt="Upload video to youtube" />
                Upload video to youtube
            </a>
            <div id="youtube-plugin" class="overlay-white mfp-hide overlay-hide">
                <div id="youtube-plugin-container">
                    %(body)s
                </div>
            </div>
         """ % {
                'style'  : style,
                'script' : script,
                'body'   : body,
                'site_url': CFG_SITE_URL,
               }
    return out

def create_form(recid):
    """
    Creates a form with meta prefilled
    ==================================
    """
    # read the access token
    try:
        record  = get_record_meta(recid)
    except:
        record = {}
    out = """
        <form id="push_to_youtube" method="GET" action='%(site_url)s/youtube/upload'>
            <fieldset>
                <label for="title">Title</label>
                <input type="text" name="title" value="%(title)s" /><br />
                <label for="deiscription">Description</label>
                <input type="text" name="description" value="%(description)s" /><br />
                <label for="keywords">Keywords</label>
                <textarea name="keywords">%(keywords)s</textarea>
                <span class="help-text">Comma separated words</span><br />
                <label for="privacyStatus">Privacy</label>
                <select name="privacyStatus">
                    <option value="public">Public</option>
                    <option value="private">Private</option>
                    <option value="unlisted">Unlisted</option>
                </select>
                <label for="category">Category (Youtube)</label>
                <select id="category" name="category">
                </select>
            </fieldset>
            <input type="hidden" name="video" value="%(file)s" />
            <input type="hidden" name="token" value="" />
            <button id="youtube-submit" type="submit">Push to youtube</button>
        </form>
        <p class='sign-info'>
            Please note that the upload proccess sometimes it can take up to several minutes.
        </p>
       """ % {
            'title'       : record.get('title', ''),
            'description' : record.get('description', ''),
            'keywords'    : record.get('keywords', ''),
            'file'        : record.get('file', ''),
            'site_url': CFG_SITE_URL,
            }
    return out


"""
Video upload related functions
====================
"""

def upload_video(options):
    """
    It hanldes the upload of a video
    ================================
    """
    credentials = AccessTokenCredentials(options.get('token'), '')
    if credentials.invalid:
        return "Your token is not valid"
    else:
        youtube = build('youtube', 'v3', http=credentials.authorize(httplib2.Http()))
        body=dict(
        snippet=dict(
          title=options.get('title'),
          description=options.get('description'),
          tags=options.get('keywords','').split(','),
          categoryId= options.get('category')
          ),
        status=dict(
          privacyStatus=options.get('privacyStatus')
        )
        )
        insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.get('video'), \
                   mimetype=guess_mime_type(options.get('video')), \
                   chunksize=-1, \
                   resumable=True)
        )
        return resumable_video(insert_request)

def resumable_video(insert_request):
    """
    Make video resumable if fails
    =============================
    """
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if 'id' in response:
                json_response = {
                    'success' : 'true',
                    'video'   : response['id']
                }
                return json.dumps(json_response)
            else:
                json_response = {
                    'success' : 'false',
                    'message' : "The upload failed with an unexpected response: %s" % response
                }
                return json.dumps(json_response)
        except HttpError, e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = "A retriable HTTP error %d occurred:\n%s" % (e.resp.status,
                                                                 e.content)
            else:
                json_response = {
                    'success' : 'false',
                    'message' : "An error occured %s - %s" % (e.resp.status, e.content)
                }
                return json_response
        except RETRIABLE_EXCEPTIONS, e:
            error = "A retriable error occurred: %s" % e

        if error is not None:
            return error
            retry += 1
            if retry > MAX_RETRIES:
                json_response = {
                    'success' : 'false',
                    'message' : 'No longer attempting to upload the video'
                }
                return json_response
            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            time.sleep(sleep_seconds)

"""
Helper Functions
================
"""
def _convert_url_to_dfs_path(path):
    """
    Translate url to dfs path
    =========================
    """
    return re.sub(r'https?://mediaarchive.cern.ch/', '/dfs/Services/', path)

def get_record_meta(recid):
    """
    Gets the meta of requested record
    =================================
    """

    record = get_record(recid)
    # lets take title and description
    response = {
            'title' : record_get_field_value(record, '245', ' ', ' ', 'a'),
            'description': record_get_field_value(record, '520', ' ', ' ', 'a'),
    }
    # lets take the keywords
    instances = record_get_field_instances(record, '653', '1', ' ')
    # extract keyword values
    keywords = [dict(x[0]).get('a') for x in instances]
    # append to resonse
    response['keywords'] = ','.join(keywords)

    videos = record_get_field_instances(record, '856', VIDEO_SUBFIELD, ' ')
    video  = [dict(x[0]).get('u') for x in videos if dict(x[0]).get('x') in VIDEO_SIZE]
    response['file'] = bibdocfile_url_to_fullpath(video[0].split('?')[0]) \
                       if not CFG_CERN_SITE else _convert_url_to_dfs_path(video[0])

    # finaly return reponse
    return response

def guess_mime_type(filepath):
    """
    Returns the mime type based on file extension
    =============================================
    """
    return CFG_BIBENCODE_YOUTUBE_MIME_TYPES.get(filepath.split('.')[1].split(';')[0])
