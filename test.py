#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""

Usage:
    cli.py [options]
    cli.py (-h | --help)
    cli.py --version

Options:
    --local-url <url>    URL of local docker-registry (default: $DOCKER_HOST)
    --local-port <int>   Port of local docker-registry [default: 5000]
    --remote-url <url>   URL of remote registry.
    --remote-port <int>  Port of docker-registry [default: 5000]
    --dry-run            just print images:tags

General Options:
    -h --help               Show this screen.
    --version               Show version.
    --loglevel, -L=<str>    Loglevel [default: WARN]
                            (ERROR, CRITICAL, WARN, INFO, DEBUG)
    --log2stdout, -l        Log to stdout, otherwise to logfile. [default: True]
    --logfile, -f=<path>    Logfile to log to (default: <scriptname>.log)
    --cfg, -c=<path>        Configuration file.

"""

from ConfigParser import RawConfigParser, NoOptionError
import re
import os
import logging
import sys
from pprint import pprint

import docker_reg
try:
    from docopt import docopt
except ImportError:
    HAVE_DOCOPT = False
else:
    HAVE_DOCOPT = True

__author__ = 'Christian Kniep <christian@qnib.org>'
__license__ = 'Apache License 2.0'

class QnibConfig(RawConfigParser):
    """ Class to abstract config and options
    """
    specials = {
        'TRUE': True,
        'FALSE': False,
        'NONE': None,
    }

    def __init__(self, opt):
        """ init """
        RawConfigParser.__init__(self)
        self.logformat = '%(asctime)-15s %(levelname)-5s [%(module)s] %(message)s'
        if opt is None:
            self._opt = {
                "--log2stdout": False,
                "--logfile": None,
                "--loglevel": "ERROR",
            }
        else:
            self._opt = opt
            self.loglevel = opt['--loglevel']
            self.logformat = '%(asctime)-15s %(levelname)-5s [%(module)s] %(message)s'
            self.log2stdout = opt['--log2stdout']
            if self.loglevel is None and opt.get('--cfg') is None:
                print "please specify loglevel (-L)"
                sys.exit(0)
            self.eval_cfg()

        self.eval_opt()
        self.set_logging()
        logging.info("SetUp of QnibConfig is done...")

    def do_get(self, section, key, default=None):
        """ Also lent from: https://github.com/jpmens/mqttwarn
            """
        try:
            val = self.get(section, key)
            if val.upper() in self.specials:
                return self.specials[val.upper()]
            return ast.literal_eval(val)
        except NoOptionError:
            return default
        except ValueError:  # e.g. %(xxx)s in string
            return val
        except:
            raise
            return val

    def config(self, section):
        ''' Convert a whole section's options (except the options specified
                explicitly below) into a dict, turning

                    [config:mqtt]
                    host = 'localhost'
                    username = None
                    list = [1, 'aaa', 'bbb', 4]

                into

                    {u'username': None, u'host': 'localhost', u'list': [1, 'aaa', 'bbb', 4]}

                Cannot use config.items() because I want each value to be
                retrieved with g() as above
            SOURCE: https://github.com/jpmens/mqttwarn
            '''

        d = None
        if self.has_section(section):
            d = dict((key, self.do_get(section, key))
                     for (key) in self.options(section) if key not in ['targets'])
        return d

    def eval_cfg(self):
        """ eval configuration which overrules the defaults
            """
        cfg_file = self._opt.get('--cfg')
        if cfg_file is not None:
            fd = codecs.open(cfg_file, 'r', encoding='utf-8')
            self.readfp(fd)
            fd.close()
            self.__dict__.update(self.config('defaults'))

    def eval_opt(self):
        """ Updates cfg according to options """

        def handle_logfile(val):
            """ transforms logfile argument
                """
            if val is None:
                logf = os.path.splitext(os.path.basename(__file__))[0]
                self.logfile = "%s.log" % logf.lower()
            else:
                self.logfile = val

        self._mapping = {
            '--logfile': lambda val: handle_logfile(val),
        }
        for key, val in self._opt.items():
            if key in self._mapping:
                if isinstance(self._mapping[key], str):
                    self.__dict__[self._mapping[key]] = val
                else:
                    self._mapping[key](val)
                break
            else:
                if val is None:
                    continue
                mat = re.match("\-\-(.*)", key)
                if mat:
                    self.__dict__[mat.group(1)] = val
                else:
                    logging.info("Could not find opt<>cfg mapping for '%s'" % key)

    def set_logging(self):
        """ sets the logging """
        self._logger = logging.getLogger()
        self._logger.setLevel(logging.DEBUG)
        if self.log2stdout:
            hdl = logging.StreamHandler()
            hdl.setLevel(self.loglevel)
            formatter = logging.Formatter(self.logformat)
            hdl.setFormatter(formatter)
            self._logger.addHandler(hdl)
        else:
            hdl = logging.FileHandler(self.logfile)
            hdl.setLevel(self.loglevel)
            formatter = logging.Formatter(self.logformat)
            hdl.setFormatter(formatter)
            self._logger.addHandler(hdl)

    def __str__(self):
        """ print human readble """
        ret = []
        for key, val in self.__dict__.items():
            if not re.match("_.*", key):
                ret.append("%-15s: %s" % (key, val))
        return "\n".join(ret)

    def __getitem__(self, item):
        """ return item from opt or __dict__
        :param item: key to lookup
        :return: value of key
        """
        if item in self.__dict__.keys():
            return self.__dict__[item]
        else:
            return self._opt[item]


def main():
    """ main function """
    options = None
    if HAVE_DOCOPT:
        options = docopt(__doc__, version='0.0.1')
    else:
        print "No python-docopt found..."
    cfg = QnibConfig(options)
    if cfg['--local-url'] is None:
        local_url = os.environ['DOCKER_HOST'].replace("tcp://", "")
        if len(local_url.split(":")) > 1:
            local_url = "%s:%s" % (local_url.split(":")[0], cfg['--local-port'])
    if cfg['--remote-url'] is None:
        print "please specify '--remote-url"
        sys.exit(1)
    remote_url = "%s:%s" % (cfg['--remote-url'], cfg['--remote-port'])

    dreg1 = docker_reg.DockerRegAPI(url=local_url)
    dreg1.populate_image_details()

    dreg2 = docker_reg.DockerRegAPI(url=remote_url)
    dreg2.populate_image_details()

    win, lose = dreg1.diff_image_list(dreg2.get_image_details())
    print "echo '## pull image from %s and push it to %s...'" % (local_url, remote_url)
    for name, tags in win.items():
        for tag in tags:
            print "echo '%s:%s'" % (name, tag)
            dreg1.update_remote_v2_reg(name, tag, remote_url=remote_url)
    print "echo 'the remote system has %s images that should be synced as well'" % len(lose)

if __name__ == "__main__":
    main()
