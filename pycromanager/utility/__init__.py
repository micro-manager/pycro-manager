# Copyright 2018-2020 Nick Anthony, Backman Biophotonics Lab, Northwestern University
#
# This file is part of PWSpy.
#
# PWSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PWSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PWSpy.  If not, see <https://www.gnu.org/licenses/>.

"""
Objects useful for dealing with files saved by Micro-Manager. https://micro-manager.org/

Classes
----------
.. autosummary::
   :toctree: generated/

   Image
   Position1d
   Position2d
   PositionList
   Property
   PropertyMap
   MultiStagePosition

"""
__all__ = ['PositionList', 'Position2d', 'Position1d', 'MultiStagePosition', 'Property', 'PropertyMap']
from .positions import Position1d, Position2d, PositionList, MultiStagePosition
from .PropertyMap import Property, PropertyMap
