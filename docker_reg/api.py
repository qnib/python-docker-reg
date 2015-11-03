#! /usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import os
import envoy
from dateutil.parser import parser
from pprint import pprint


class DockerRegAPI(object):
    """ Class that interacts with RESTful API of Docker-registries
    """
    def __init__(self, url="localhost:5000"):
        """ initialise instance with user/password or AUTH-tokens

        :param url:         Url to API (w/o protocol)
        """
        self._url = url
        self._server = "http://%s/v2" % url
        self.images = {}

    def list_images(self):
        """ return list of images
        """
        url = "%s/_catalog" % self._server
        res = self._get(url)
        return res['repositories']

    def _get(self, url, form="json"):
        """ fetch url """
        try:
            req = requests.get(url)
        except requests.exceptions.ConnectionError:
            print "Fail to fetch '%s'" % url
            raise
        if req.status_code != 200:
            msg = "something went wrong... :( [%s/_catalog] ec:%s" % (self._server, req.status_code)
            print msg
            raise IOError(msg)
        if form == "json":
            return req.json()

    def get_tags(self, name, tag="latest"):
        """ fetch details of given image """
        res = self._get("%s/%s/tags/list" % (self._server, name))
        return res['tags']

    def get_detail(self, name, tag="latest"):
        """ fetch details of given image """
        res = self._get("%s/%s/manifests/%s" % (self._server, name, tag))
        return res

    def get_tarsum_list(self, name, tag="latest"):
        """ extract tarsum list from manifest """
        res = self.get_detail(name, tag)
        return [item['blobSum'].split(":") for item in res['fsLayers']]

    def extract_fingerprint(self, name, tag="latest"):
        """ extract information from get_detail to figure out if there is a newer version """
        detail = self.get_detail(name, tag)
        if len(detail) >= 1:
            datep = parser()
            dic = json.loads(detail['history'][0]['v1Compatibility'])
            return dic['id'], int(datep.parse(dic["created"]).strftime('%s'))
        else:
            return None, None

    def populate_image_details(self):
        """ populates list of images with id and created time """
        for name in self.list_images():
            if name not in self.images:
                self.images[name] = {}
            tags = self.get_tags(name)
            for tag in tags:
                if tag not in self.images[name]:
                    self.images[name][tag] = {}
                self.images[name][tag] = self.extract_fingerprint(name, tag)

    def get_image_details(self):
        """ returns image list"""
        return self.images

    def diff_image_list(self, other):
        """ diffs local image list against external one """
        we_win = {}
        we_lose = {}
        for name, tags in self.images.items():
            if name not in other:
                ## if it's not in there we win with all our tags
                we_win[name] = set(tags)
            else:
                ## now we check the tags who has the new create timestamp
                for tag in tags:
                    if tag not in other[name] or self.images[name][tag][1] >= other[name][tag][1]:
                        ## we win this one
                        if name not in we_win:
                            we_win[name] = set([])
                        we_win[name].add(tag)
                    else:
                        if name not in we_lose:
                            we_lose[name] = set([])
                        we_lose[name].add(tag)
        for name, tags in other.items():
            if name not in self.images:
                ## if it's not in here we lose with all our tags
                we_lose[name] = set(tags)
        return we_win, we_lose

    def update_remote_v2_reg(self, name, tag, remote_url, dryrun=False):
        """ fetches blobs and pushes them into remote registry"""
        cmds = [
            "docker pull %s/%s:%s" % (self._url, name, tag),
            "docker tag -f %s/%s:%s  %s/%s:%s" % (self._url, name, tag, remote_url, name, tag),
            "docker push %s/%s:%s" % (remote_url, name, tag),
            "docker rmi %s/%s:%s" % (self._url, name, tag)
        ]
        def do_exec(cmd):
            proc = envoy.run(cmd)
            if proc.status_code != 0:
                print os.environ
                print proc.std_out, proc.std_err
                raise IOError("CMD '%s' failed with EC:%s" % (cmd, proc.status_code))

        for cmd in cmds:
            print " "*5 + cmd


    def fetch_image_manifest(self, name, tag):
        """ Fetches an image layer from the registry"""
        url = "%s/%s/manifests/%s" % (self._server, name, tag)
        print url
        res = self._get(url)
        return res

