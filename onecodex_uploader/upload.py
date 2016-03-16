"""
Functions for connecting to the One Codex server; these should be rolled out
into the onecodex python library at some point for use across CLI and GUI clients
"""
import os
from math import floor
import re

import requests
import boto3
from boto3.s3.transfer import S3Transfer
from boto3.exceptions import S3UploadFailedError


class UploadException(Exception):
    """
    A exception for when things go wrong with uploading
    """
    pass


def get_apikey(username, password, server_url):
    """
    Retrieves an API key from the One Codex webpage given the username and password
    """
    with requests.Session() as session:
        text = session.get(server_url + 'login').text
        csrf = re.search('type="hidden" value="([^"]+)"', text).group(1)
        login_data = {'email': username, 'password': password,
                      'csrf_token': csrf, 'next': '/api/get_token'}
        page = session.post(server_url + 'login', data=login_data)
        try:
            key = page.json()['key']
        except (ValueError, KeyError):  # ValueError includes simplejson.decoder.JSONDecodeError
            key = None
    return key


def check_version(version, server_url, client='cli'):
    """
    Check if the current version of the client software is supported by the One Codex
    backend. Returns a tuple with two values:
        - True if the user *must* upgrade their software, otherwise False
        - An error message if the user should upgrade, otherwise None.
    """
    def version_inadequate(client_version, server_version):
        """
        Simple, fast check for version inequality.

        Could use python package `semver` if we need more precise checks in
        edge cases, but this generally works for now.
        """
        return tuple(client_version.split('.')) < tuple(server_version.split('.'))

    if client == 'cli':
        data = requests.post(server_url + 'api/v0/check_for_cli_update', data={'version': version})
    elif client == 'gui':
        data = requests.post(server_url + 'api/v0/check_upload_app_version',
                             data={'version': version})
    else:
        raise Exception('Not a valid client descriptor')

    if data.status_code != 200:
        return False, 'Error connecting to server'
    data = data.json()
    latest_version = data['latest_version']

    if client == 'cli':
        uploader_text = ' from http://www.onecodex.com/uploader.html'
    else:
        uploader_text = (' from the '
                         '<a href="http://www.onecodex.com/uploader.html">One Codex website</a>')

    # TODO: once the cli route returns this, remove this outer check
    if 'min_supported_version' in data:
        min_version = data['min_supported_version']
        if version_inadequate(version, min_version):
            return True, ('Please upgrade your client to the latest version ' +
                          '(v{}){}; '.format(latest_version, uploader_text) +
                          'this version (v{}) is no longer supported.'.format(version))

    if version_inadequate(version, latest_version):
        return False, ('Please upgrade your client to the latest version ' +
                       '(v{}){}'.format(latest_version, uploader_text))

    return False, None


def upload_file(filename, apikey, server_url, progress_callback=None, n_callbacks=400):
    """
    Uploads a file to the One Codex server (and handles files >5Gb)

    Takes an optional callback that it calls with a number from 0 to 1 as the
    upload progresses.
    """
    # first check with the one codex server to get upload parameters
    req = requests.get(server_url + 'api/v0/init_multipart_upload', auth=(apikey, ''))
    if req.status_code != 200:
        raise UploadException('Could not initiate upload with One Codex server')

    upload_params = req.json()

    access_key = upload_params['upload_aws_access_key_id']
    secret_key = upload_params['upload_aws_secret_access_key']

    # set up a progress tracker to simplify the callback
    if progress_callback is not None:
        class Progress(object):
            """
            Wrapper for progress callbacks
            """
            def __init__(self, callback, file_size):
                self.file_size = float(file_size)
                self.transferred = 0
                self.callback = callback
                self.step_size = n_callbacks  # e.g. call callback in 1000 or less intervals

            def __call__(self, bytes_seen):
                per_prev_done = self.transferred / self.file_size
                self.transferred += bytes_seen
                per_done = self.transferred / self.file_size
                if floor(self.step_size * per_prev_done) != floor(self.step_size * per_done):
                    self.callback(filename, per_done)
        progress_tracker = Progress(progress_callback, os.path.getsize(filename))
    else:
        progress_tracker = None

    # actually do the upload
    client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    transfer = S3Transfer(client)
    try:
        transfer.upload_file(filename, upload_params['s3_bucket'], upload_params['file_id'],
                             extra_args={'ServerSideEncryption': 'AES256'},
                             callback=progress_tracker)
    except S3UploadFailedError:
        raise UploadException('Upload has failed. Please contact help@onecodex.com '
                              'if you experience further issues')

    # return completed status to the one codex server
    s3_path = 's3://{}/{}'.format(upload_params['s3_bucket'], upload_params['file_id'])
    callback_url = server_url.rstrip('/') + upload_params['callback_url']
    req = requests.post(callback_url, auth=(apikey, ''),
                        json={'s3_path': s3_path, 'filename': os.path.basename(filename)})

    if req.status_code != 200:
        raise UploadException('Upload confirmation has failed. Please contact help@onecodex.com '
                              'if you experience further issues')
