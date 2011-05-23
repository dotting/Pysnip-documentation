# Copyright (c) Mathias Kaerlev 2011.

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

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from pyspades.protocol import (BaseConnection, sized_sequence, 
    sized_data, in_packet, out_packet)
from pyspades.bytereader import ByteReader
from pyspades.packet import Packet, load_client_packet
from pyspades.loaders import *
from pyspades.common import *
from pyspades.constants import *
from pyspades import serverloaders, clientloaders
from pyspades.multidict import MultikeyDict
from pyspades.idpool import IDPool
from pyspades.master import get_master_connection
from pyspades.collision import vector_collision

import random
import math

player_data = serverloaders.PlayerData()
create_player = serverloaders.CreatePlayer()
position_data = serverloaders.PositionData()
orientation_data = serverloaders.OrientationData()
movement_data = serverloaders.MovementData()
animation_data = serverloaders.AnimationData()
hit_packet = serverloaders.HitPacket()
grenade_packet = serverloaders.GrenadePacket()
set_weapon = serverloaders.SetWeapon()
set_color = serverloaders.SetColor()
existing_player = serverloaders.ExistingPlayer()
intel_action = serverloaders.IntelAction()
block_action = serverloaders.BlockAction()
kill_action = serverloaders.KillAction()
chat_message = serverloaders.ChatMessage()

class ServerConnection(BaseConnection):
    protocol = None
    send_id = False
    address = None
    player_id = None
    map_packets_sent = 0
    team = None
    name = None
    kills = 0
    orientation_sequence = 0
    hp = None
    tool = None
    color = (0x70, 0x70, 0x70)
    grenades = None
    
    up = down = left = right = False
    position = orientation = None
    fire = jump = aim = crouch = None
    
    def __init__(self, protocol, address):
        BaseConnection.__init__(self)
        self.protocol = protocol
        self.address = address
        self.connection_id = 0
    
    def loader_received(self, loader):
        if loader.id == ConnectionRequest.id:
            if loader.client and loader.version != self.protocol.version:
                self.disconnect()
                return
            self.auth_val = loader.auth_val
            if loader.client:
                self.connection_id = self.protocol.connection_ids.pop()
            else:
                self.connection_id = 0
            self.unique = random.randint(0, 3)
            connection_response = ConnectionResponse()
            connection_response.auth_val = loader.auth_val
            connection_response.unique = self.unique
            connection_response.connection_id = self.connection_id
            
            self.map_data = ByteReader(self.protocol.map.generate())
            self.send_loader(connection_response, True, 0xFF).addCallback(
                self.send_map)
        elif loader.id == Ack.id:
            pass
        elif loader.id == Packet10.id:
            print 'got packet 10'
        elif loader.id == Disconnect.id:
            self.disconnect()
        elif loader.id == Ping.id:
            pass
        elif loader.id in (SizedData.id, SizedSequenceData.id):
            contained = load_client_packet(loader.data)
            if contained.id == clientloaders.JoinTeam.id:
                if self.name is None and contained.name is not None:
                    self.name = contained.name
                    self.protocol.players[self.name, self.player_id] = self
                    create_player.name = self.name
        
                self.team = [self.protocol.blue_team, 
                    self.protocol.green_team][contained.team]
                create_player.player_id = self.player_id
                self.orientation = Vertex3(0, 0, 0)
                x, y, z = self.team.get_random_position()
                self.position = position = Vertex3(x, y, z)
                create_player.x = position.x
                create_player.y = position.y - 128
                create_player.z = position.z
                self.hp = 100
                self.tool = 3
                self.grenades = 2
                self.protocol.send_contained(create_player)
            if contained.id == clientloaders.OrientationData.id:
                self.orientation.set(contained.x, contained.y, contained.z)
                orientation_data.x = contained.x
                orientation_data.y = contained.y
                orientation_data.z = contained.z
                orientation_data.player_id = self.player_id
                self.protocol.send_contained(orientation_data,
                    self.orientation_sequence, sender = self)
                self.orientation_sequence += 1
            elif contained.id == clientloaders.PositionData.id:
                self.position.set(contained.x, contained.y, contained.z)
                position_data.x = contained.x
                position_data.y = contained.y
                position_data.z = contained.z
                position_data.player_id = self.player_id
                other_flag = self.team.other.flag
                if vector_collision(self.position, self.team.base):
                    self.refill()
                    if other_flag.player is self:
                        self.capture_flag()
                if other_flag.player is None and vector_collision(
                self.position, other_flag):
                    self.take_flag()
                self.protocol.send_contained(position_data, sender = self)
            elif contained.id == clientloaders.MovementData.id:
                self.up = contained.up
                self.down = contained.down
                self.left = contained.left
                self.right = contained.right
                movement_data.up = self.up
                movement_data.down = self.down
                movement_data.left = self.left
                movement_data.right = self.right
                movement_data.player_id = self.player_id
                self.protocol.send_contained(movement_data, sender = self)
            elif contained.id == clientloaders.AnimationData.id:
                self.fire = contained.fire
                self.jump = contained.jump
                self.crouch = contained.crouch
                self.aim = contained.aim
                animation_data.fire = self.fire
                animation_data.jump = self.jump
                animation_data.crouch = self.crouch
                animation_data.aim = self.aim
                animation_data.player_id = self.player_id
                self.protocol.send_contained(animation_data, sender = self)
            elif contained.id == clientloaders.HitPacket.id:
                if contained.player_id is not None:
                    player, = self.protocol.players[contained.player_id]
                    player.hit(HIT_VALUES[contained.value], self)
                else:
                    self.hit(contained.value)
            elif contained.id == clientloaders.GrenadePacket.id:
                self.grenades -= 1
                grenade_packet.player_id = self.player_id
                grenade_packet.value = contained.value
                self.protocol.send_contained(grenade_packet, sender = self)
            elif contained.id == clientloaders.SetWeapon.id:
                self.tool = contained.value
                set_weapon.player_id = self.player_id
                set_weapon.value = contained.value
                self.protocol.send_contained(set_weapon, sender = self)
            elif contained.id == clientloaders.SetColor.id:
                self.color = get_color(contained.value)
                set_color.player_id = self.player_id
                set_color.value = contained.value
                self.protocol.send_contained(set_color, sender = self)
            elif contained.id == clientloaders.BlockAction.id:
                value = contained.value
                map = self.protocol.map
                x = contained.x
                y = contained.y
                z = contained.z
                if value == BUILD_BLOCK:
                    map.set_point(x, y, z, self.color + (255,))
                elif value == DESTROY_BLOCK:
                    map.remove_point(x, y, z)
                elif value == SPADE_DESTROY:
                    map.remove_point(x, y, z)
                    map.remove_point(x, y, z + 1)
                    map.remove_point(x, y, z - 1)
                elif value == GRENADE_DESTROY:
                    for nade_x in xrange(x - 1, x + 2):
                        for nade_y in xrange(y - 1, y + 2):
                            for nade_z in xrange(z - 1, z + 2):
                                map.remove_point(nade_x, nade_y, nade_z)
                block_action.x = x
                block_action.y = y
                block_action.z = z
                block_action.value = contained.value
                block_action.player_id = self.player_id
                self.protocol.send_contained(block_action)
            elif contained.id == clientloaders.KillAction.id:
                other_player, = self.protocol.players[contained.player_id]
                self.kill(other_player)
            elif contained.id == clientloaders.ChatMessage.id:
                chat_message.global_message = contained.global_message
                chat_message.value = contained.value
                chat_message.player_id = self.player_id
                self.protocol.send_contained(chat_message, sender = self)
            else:
                print 'received:', contained
        else:
            print 'received:', loader
            raw_input('unknown loader')
    
    def refill(self):
        self.hp = 100
        self.grenades = 2
        intel_action.action_type = 4
        self.send_contained(intel_action)
    
    def take_flag(self):
        flag = self.team.other.flag
        if flag.player is not None:
            return
        flag.player = self
        intel_action.action_type = 1
        intel_action.player_id = self.player_id
        self.protocol.send_contained(intel_action)
    
    def capture_flag(self):
        other_team = self.team.other
        flag = other_team.flag
        player = flag.player
        if player is not self:
            return
        intel_action.action_type = 3
        intel_action.player_id = self.player_id
        if self.team.score + 1 >= self.protocol.max_score:
            intel_action.game_end = True
            blue_team = self.protocol.blue_team
            green_team = self.protocol.green_team
            blue_team.initialize()
            green_team.initialize()
            intel_action.blue_flag_x = green_team.flag.x
            intel_action.blue_flag_y = green_team.flag.y
            intel_action.blue_base_x = green_team.base.x
            intel_action.blue_base_y = green_team.base.y
            intel_action.green_flag_x = green_team.flag.x
            intel_action.green_flag_y = green_team.flag.y
            intel_action.green_base_x = green_team.base.x
            intel_action.green_base_y = green_team.base.y
        else:
            intel_action.game_end = False
            self.team.score += 1
            flag = other_team.set_flag()
            intel_action.x = flag.x
            intel_action.y = flag.y
        self.protocol.send_contained(intel_action)
    
    def drop_flag(self):
        flag = self.team.other.flag
        player = flag.player
        if player is not self:
            return
        position = self.position
        x = int(position.x)
        y = int(position.y)
        z = int(position.z)
        z = self.protocol.map.get_z(x, y, z)
        flag.set_vector(x, y, z)
        flag.player = None
        intel_action.action_type = 2
        intel_action.player_id = self.player_id
        intel_action.x = flag.x
        intel_action.y = flag.y
        intel_action.z = flag.z
        self.protocol.send_contained(intel_action)
    
    def disconnect(self):
        if self.disconnected:
            return
        BaseConnection.disconnect(self)
        del self.protocol.connections[self.address]
        if self.connection_id is not None:
            self.protocol.connection_ids.put_back(self.connection_id)
        if self.player_id is not None:
            self.protocol.player_ids.put_back(self.player_id)
        if self.name is not None:
            self.drop_flag()
            player_data.player_left = self.player_id
            self.protocol.send_contained(player_data, sender = self)
            del self.protocol.players[self]
    
    def hit(self, value, by = None):
        self.hp -= value
        if self.hp <= 0:
            self.kill(by)
            return
        if by is not None:
            hit_packet.value = HIT_CONSTANTS[value]
            self.send_contained(hit_packet)
    
    def kill(self, by = None):
        self.drop_flag()
        if by is None:
            kill_action.player1 = self.player_id
        else:
            kill_action.player1 = by.player_id
        kill_action.player2 = self.player_id
        if by is self:
            sender = self
        else:
            sender = None
        self.protocol.send_contained(kill_action, sender = sender)
    
    def send_map(self, ack = None):
        if self.map_data is None:
            return
        if not self.map_data.dataLeft():
            self.map_data = None
            # send players
            for player in self.protocol.players.values():
                if player.name is None:
                    continue
                existing_player.name = player.name
                existing_player.player_id = player.player_id
                existing_player.tool = player.tool
                existing_player.kills = player.kills
                existing_player.team = player.team.id
                existing_player.color = player.color
                self.send_contained(existing_player)
            
            # send initial data
            blue = self.protocol.blue_team
            green = self.protocol.green_team
            blue_flag = blue.flag
            green_flag = green.flag
            blue_base = blue.base
            green_base = green.base
            
            self.player_id = self.protocol.player_ids.pop()
            player_data.player_left = None
            player_data.player_id = self.player_id
            player_data.max_score = self.protocol.max_score
            player_data.blue_score = blue.score
            player_data.green_score = green.score
            
            player_data.blue_base_x = blue_base.x
            player_data.blue_base_y = blue_base.y
            player_data.blue_base_z = blue_base.z
            
            player_data.green_base_x = green_base.x
            player_data.green_base_y = green_base.y
            player_data.green_base_z = green_base.z
            
            player_data.blue_flag_x = blue_flag.x
            player_data.blue_flag_y = blue_flag.y
            player_data.blue_flag_z = blue_flag.z
            
            player_data.green_flag_x = green_flag.x
            player_data.green_flag_y = green_flag.y
            player_data.green_flag_z = green_flag.z
            
            self.send_contained(player_data)
            return
        for _ in xrange(4):
            sequence = self.packet_handler1.sequence + 1
            data_size = min(4096, self.map_data.dataLeft())
            new_data = ByteReader('\x0F' + self.map_data.read(data_size))
            new_data_size = len(new_data)
            nums = int(math.ceil(new_data_size / 1024.0))
            for i in xrange(nums):
                map_data = MapData()
                map_data.data = new_data.readReader(1024)
                map_data.sequence2 = sequence
                map_data.num = i
                map_data.total_num = nums
                map_data.data_size = new_data_size
                map_data.current_pos = i * 1024
                self.send_loader(map_data, True).addCallback(self.got_map_ack)
                self.map_packets_sent += 1
    
    def got_map_ack(self, ack):
        self.map_packets_sent -= 1
        if not self.map_packets_sent:
            self.send_map()
    
    def send_data(self, data):
        self.protocol.transport.write(data, self.address)

class Vertex3(object):
    def __init__(self, *arg, **kw):
        self.set(*arg, **kw)
    
    def set(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
    
    def set_vector(self, vector):
        self.set(vector.x, vector.y, vector.z)

class Flag(Vertex3):
    player = None
    team = None

class Team(object):
    score = None
    flag = None
    other = None
    map = None
    
    def __init__(self, id, map):
        self.id = id
        self.map = map
        self.initialize()
    
    def initialize(self):
        self.score = 0
        self.set_flag()
        self.base = Vertex3(*self.get_random_position())
    
    def set_flag(self):
        self.flag = Flag(*self.get_random_position())
        self.flag.team = self
        return self.flag
    
    def get_random_position(self):
        x = self.id * 384 + random.randrange(128)
        y = 128 + random.randrange(256)
        z = self.map.get_z(x, y)
        return x, y, z

class ServerProtocol(DatagramProtocol):
    name = 'pyspades WIP test'
    max_players = 20

    connections = None
    connection_ids = None
    player_ids = None
    master = False
    max_score = 10
    map = None
    
    master_connection = None
    
    def __init__(self):
        self.connections = {}
        self.players = MultikeyDict()
        self.connection_ids = IDPool()
        self.player_ids = IDPool()
        self.ip_list = []
        ip_list = open('ip_list.txt', 'rb').read().splitlines()
        for ip in ip_list:
            reactor.resolve(ip).addCallback(self.add_ip)
        self.blue_team = Team(0, self.map)
        self.green_team = Team(1, self.map)
        self.blue_team.other = self.green_team
        self.green_team.other = self.blue_team
    
    def add_ip(self, ip):
        self.ip_list.append(ip)
        print 'added IP:', ip
    
    def startProtocol(self):
        self.version = crc32(open('client.exe', 'rb').read())
        if self.master:
            get_master_connection(self.name, self.max_players).addCallback(
                self.got_master_connection)
        
    def got_master_connection(self, connection):
        self.master_connection = connection
    
    def datagramReceived(self, data, address):
        # if address[0] not in self.ip_list:
            # return
        if address not in self.connections:
            self.connections[address] = ServerConnection(self, address)
        connection = self.connections[address]
        connection.data_received(data)
    
    def send_contained(self, contained, sequence = None, sender = None):
        if sequence is not None:
            loader = sized_sequence
            loader.sequence2 = sequence
        else:
            loader = sized_data
        data = ByteReader()
        contained.write(data)
        loader.data = data
        for player in self.connections.values():
            if player is sender or player.player_id is None:
                continue
            player.send_loader(loader, sequence is None)