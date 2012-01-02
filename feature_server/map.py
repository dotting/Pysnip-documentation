# Copyright (c) Mathias Kaerlev 2011-2012.

# This file is part of pyspades.

# pyspades is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# pyspades is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with pyspades.  If not, see <http://www.gnu.org/licenses/>.

from pyspades.load import VXLData

import os
import imp

import mapmaker

DEFAULT_LOAD_DIR = './maps'
RESERVED_NAMES = set(['random'])

class MapNotFound(IOError):
    pass

def get_filename(name, load_dir = DEFAULT_LOAD_DIR):
    return os.path.join(load_dir, '%s.vxl' % name)

def check_rotation(maps, load_dir = DEFAULT_LOAD_DIR):
    for map in maps:
        if map in RESERVED_NAMES:
            continue
        if not os.path.isfile(get_filename(map, load_dir)):
            raise MapNotFound('map %s does not exist' % map)

class Map(object):
    def __init__(self, name, load_dir = DEFAULT_LOAD_DIR):
        self.load_information(name, load_dir)
        if not self.generate_map(name):
            self.load_vxl(name, load_dir)

    def load_information(self, name, load_dir):
        info_file = os.path.join(load_dir, '%s.txt' % name)
        try:
            info = imp.load_source(name, info_file)
        except IOError:
            info = None
        self.data = info
        self.name = getattr(info, 'name', name)
        self.author = getattr(info, 'author', '(unknown)')
        self.version = getattr(info, 'version', '1.0')
        self.description = getattr(info, 'description', '')
        self.extensions = getattr(info, 'extensions', {})
        self.script = getattr(info, 'apply_script', None)
        self.time_limit = getattr(info, 'time_limit', None)
        self.cap_limit = getattr(info, 'cap_limit', None)
        self.get_spawn_location = getattr(info, 'get_spawn_location', None)
        self.get_entity_location = getattr(info, 'get_entity_location', None)
        
    def apply_script(self, protocol, connection, config):
        if self.script is not None:
            protocol, connection = self.script(protocol, connection, config)
        return protocol, connection

    def load_vxl(self, name, load_dir):
        check_rotation((name,))
        self.data = VXLData(open(get_filename(name, load_dir), 'rb'))

    def generate_map(self, name):
        if name == 'random':
            self.data = mapmaker.generator_random()
            self.author = "Triplefox"
            return True
        else:
            return False
