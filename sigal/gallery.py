# -*- coding:utf-8 -*-

# Copyright (c) 2009-2012 - Simon Conseil

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from __future__ import absolute_import

import codecs
import logging
import markdown
import os
import PIL

from clint.textui import progress

from .image import Image, copy_exif
from .settings import get_thumb
from .writer import Writer

DESCRIPTION_FILE = "index.md"


class Gallery:
    "Prepare images"

    def __init__(self, settings, input_dir, output_dir, force=False):
        self.settings = settings
        self.force = force
        self.input_dir = os.path.abspath(input_dir)
        self.output_dir = os.path.abspath(output_dir)
        self.logger = logging.getLogger(__name__)
        self.writer = Writer(settings, output_dir)

    def build_paths(self):
        "Build the list of directories with images"

        self.paths = {}

        for path, dirnames, filenames in os.walk(self.input_dir):
            relpath = os.path.relpath(path, self.input_dir)

            # sort images and sub-albums by name
            filenames.sort(key=str.lower)
            dirnames.sort(key=str.lower)

            self.paths[relpath] = {
                'img': [
                    f for f in filenames
                    if os.path.splitext(f)[1] in self.settings['ext_list']],
                'subdir': dirnames
            }
            self.paths[relpath].update(get_metadata(path))

            if relpath != '.':
                alb_thumb = self.paths[relpath].setdefault('representative',
                                                           '')
                if (not alb_thumb) or \
                   (not os.path.isfile(os.path.join(path, alb_thumb))):
                    alb_thumb = self.find_representative(relpath)
                    self.paths[relpath]['representative'] = alb_thumb

    def find_representative(self, path):
        "Find the representative image for a given path"

        for f in self.paths[path]['img']:
            # find and return the first landscape image
            im = PIL.Image.open(os.path.join(self.input_dir, path, f))
            if im.size[0] > im.size[1]:
                return f

        # else simply return the 1st image
        return self.paths[path]['img'][0]

    def build(self):
        "Create the image gallery"

        self.logger.info("Generate gallery in %s ...", self.output_dir)
        self.build_paths()
        check_or_create_dir(self.output_dir)

        # loop on directories
        for path in self.paths.keys():
            imglist = [os.path.join(self.input_dir, path, f)
                       for f in self.paths[path]['img']]

            self.logger.warning("%s - %i images", path, len(imglist))

            # output dir for the current path
            img_out = os.path.join(self.output_dir, path)
            check_or_create_dir(img_out)

            if len(imglist) != 0:
                self.process_dir(imglist, img_out)

            self.writer.write(self.paths, path)

    def process_dir(self, imglist, img_out):
        "Process images for a directory"

        # Create thumbnails directory and optionally the one for original img
        check_or_create_dir(os.path.join(img_out, self.settings['thumb_dir']))

        if self.settings['big_img']:
            bigimg_dir = os.path.join(img_out, self.settings['bigimg_dir'])
            check_or_create_dir(bigimg_dir)

        # loop on images
        for f in progress.bar(imglist):
            filename = os.path.split(f)[1]
            im_name = os.path.join(img_out, filename)

            if os.path.isfile(im_name) and not self.force:
                self.logger.info("%s exists - skipping", filename)
                continue

            self.logger.info(filename)
            img = Image(f)

            if self.settings['big_img']:
                img.save(os.path.join(bigimg_dir, filename),
                         quality=self.settings['jpg_quality'])

            img.resize(self.settings['img_size'])

            if self.settings['copyright']:
                img.add_copyright(self.settings['copyright'])

            img.save(im_name, quality=self.settings['jpg_quality'])

            if self.settings['make_thumbs']:
                thumb_name = os.path.join(img_out,
                                          get_thumb(self.settings, filename))
                img.thumbnail(thumb_name, self.settings['thumb_size'],
                              fit=self.settings['thumb_fit'],
                              quality=self.settings['jpg_quality'])

            if self.settings['exif']:
                copy_exif(f, im_name)


def get_metadata(path):
    """ Get album metadata from DESCRIPTION_FILE:

    - title
    - representative image
    - description
    """

    descfile = os.path.join(path, DESCRIPTION_FILE)
    meta = {}

    if not os.path.isfile(descfile):
        # default: get title from directory name
        meta['title'] = os.path.basename(path).replace('_', ' ').\
            replace('-', ' ').capitalize()
    else:
        md = markdown.Markdown(extensions=['meta'])

        with codecs.open(descfile, "r", "utf-8") as f:
            text = f.read()

        html = md.convert(text)

        meta = {
            'title': md.Meta.get('title', [''])[0],
            'description': html,
            'representative': md.Meta.get('representative', [''])[0]
        }

    return meta


def check_or_create_dir(path):
    "Create the directory if it does not exist"

    if not os.path.isdir(path):
        os.makedirs(path)
