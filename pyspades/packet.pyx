# Copyright (c) Mathias Kaerlev 2011.# This file is part of pyspades.# pyspades program is free software: you can redistribute it and/or modify# it under the terms of the GNU General Public License as published by# the Free Software Foundation, either version 3 of the License, or# (at your option) any later version.# pyspades is distributed in the hope that it will be useful,# but WITHOUT ANY WARRANTY; without even the implied warranty of# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the# GNU General Public License for more details.# You should have received a copy of the GNU General Public License# along with pyspades.  If not, see <http://www.gnu.org/licenses/>.from pyspades.common import *from pyspades.loaders cimport Loaderfrom pyspades import debugfrom pyspades.bytes cimport ByteReader, ByteWriterfrom pyspades import containedCONTAINED_LOADERS = {    0 : contained.PositionData,    1 : contained.OrientationData,    2 : contained.WorldUpdate,    3 : contained.InputData,    5 : contained.GrenadePacket,    6 : contained.SetTool,    7 : contained.SetColor,    8 : contained.ExistingPlayer,    9 : contained.MoveObject,    10 : contained.CreatePlayer,    11 : contained.BlockAction,    12 : contained.StateData,    13 : contained.KillAction,    14 : contained.ChatMessage,    15 : contained.MapStart,    16 : contained.MapChunk,    17 : contained.PlayerLeft,    18 : contained.TerritoryCapture,    19 : contained.ProgressBar,    20 : contained.IntelCapture,    21 : contained.IntelPickup,    22 : contained.IntelDrop,    23 : contained.Restock,    24 : contained.FogColor,    25 : contained.WeaponReload,    26 : contained.ChangeTeam,    27 : contained.ChangeWeapon,    28 : contained.BasicServerMessage,    29 : contained.ServerMessage,    30 : contained.ServerLoadMessage}SERVER_LOADERS = CONTAINED_LOADERS.copy()SERVER_LOADERS.update({    4 : contained.SetHP})CLIENT_LOADERS = CONTAINED_LOADERS.copy()CLIENT_LOADERS.update({    4 : contained.HitPacket})def load_server_packet(data):    return load_contained_packet(data, SERVER_LOADERS)def load_client_packet(data):    return load_contained_packet(data, CLIENT_LOADERS)cdef inline Loader load_contained_packet(ByteReader data, dict table):    type = data.readByte(True)    return table[type](data)