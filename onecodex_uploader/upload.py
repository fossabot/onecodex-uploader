import os
import re

import requests
import boto3
from boto3.s3.transfer import S3Transfer


class UploadException(Exception):
    pass


def get_apikey(username, password, server_url):
    """
    Retrieves an API key from the One Codex webpage given the username and password
    """
    with requests.Session() as session:
        text = session.get(server_url + 'login').text
        csrf = re.search('type="hidden" value="([^"]+)"', text).group(1)
        login_data = {'email': username, 'password': password,
                      'csrf_token': csrf, 'next': '/api/get_user_api_key'}
        page = session.post(server_url + 'login', data=login_data)
        try:
            key = page.json()['key']
        except:
            key = None
    return key


def upload_file(filename, apikey, server_url, progress_callback=None):
    # first check with the one codex server to get upload parameters
    r = requests.get(server_url + 'api/v0/init_multipart_upload', auth=(apikey, ''))
    if r.status_code != 200:
        raise UploadException('Could not initiate upload with One Codex server')

    upload_params = r.json()

    access_key = upload_params['upload_aws_access_key_id']
    secret_key = upload_params['upload_aws_secret_access_key']

    # set up a progress tracker to simplify the callback
    if progress_callback is not None:
        class Progress(object):
            def __init__(self, callback, file_size):
                self.file_size = file_size
                self.transferred = 0
                self.callback = callback

            def __call__(self, bytes_seen):
                self.transferred += bytes_seen
                self.callback(self.transferred / self.file_size)
        file_size = float(os.path.getsize(filename))
        progress_tracker = Progress(progress_callback, file_size)
    else:
        progress_tracker = None

    # actually do the upload
    client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    transfer = S3Transfer(client)
    transfer.upload_file(filename, upload_params['s3_bucket'], upload_params['file_id'],
                         extra_args={'ServerSideEncryption': 'AES256'}, callback=progress_tracker)

    # return completed status to the one codex server
    s3_path = 's3://{}/{}'.format(upload_params['s3_bucket'], upload_params['file_id'])
    callback_url = server_url.rstrip('/') + upload_params['callback_url']
    r = requests.post(callback_url, auth=(apikey, ''),
                      json={'s3_path': s3_path, 'filename': os.path.basename(filename)})

    if r.status_code != 200:
        raise UploadException('Upload has failed. Please contact help@onecodex.com if you '
                              'experience further issues')
