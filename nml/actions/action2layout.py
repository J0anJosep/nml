from nml import generic, expression
from nml.actions import action2

class Action2Layout(action2.Action2):
    def __init__(self, feature, name, ground_sprite, sprite_list):
        action2.Action2.__init__(self, feature, name)
        assert ground_sprite.type == Action2LayoutSpriteType.GROUND
        self.ground_sprite = ground_sprite
        self.sprite_list = sprite_list

    def write(self, file):
        size = 5
        for sprite in self.sprite_list:
            if sprite.type == Action2LayoutSpriteType.CHILD:
                size += 7
            else:
                size += 10
        if len(self.sprite_list) == 0:
            size += 9

        action2.Action2.write_sprite_start(self, file, size)
        file.print_byte(len(self.sprite_list))
        file.print_dwordx(self.ground_sprite.get_sprite_number())
        file.newline()
        if len(self.sprite_list) == 0:
            file.print_dwordx(0) #sprite number 0 == no sprite
            for i in range(0, 5):
                file.print_byte(0) #empty bounding box. Note that number of zeros is 5, not 6
        else:
            for sprite in self.sprite_list:
                file.print_dwordx(sprite.get_sprite_number())
                file.print_byte(sprite.get_param('xoffset'))
                file.print_byte(sprite.get_param('yoffset'))
                if sprite.type == Action2LayoutSpriteType.CHILD:
                    file.print_bytex(0x80)
                else:
                    #normal building sprite
                    file.print_byte(sprite.get_param('zoffset'))
                    file.print_byte(sprite.get_param('xextent'))
                    file.print_byte(sprite.get_param('yextent'))
                    file.print_byte(sprite.get_param('zextent'))
                file.newline()
        file.end_sprite()


class Action2LayoutSpriteType(object):
    GROUND   = 0
    BUILDING = 1
    CHILD    = 2

#these keywords are used to identify a ground/building/childsprite
layout_sprite_types = {
    'ground'      : Action2LayoutSpriteType.GROUND,
    'building'    : Action2LayoutSpriteType.BUILDING,
    'childsprite' : Action2LayoutSpriteType.CHILD,
}

class Action2LayoutSprite(object):
    def __init__(self, type, pos = None):
        self.type = type
        self.pos = pos
        self.params = {
            'sprite'      : {'value': 0,  'validator': self._validate_sprite},
            'ttdsprite'   : {'value': 0,  'validator': self._validate_ttdsprite},
            'recolor'     : {'value': 0,  'validator': self._validate_recolor},
            'always_draw' : {'value': 0,  'validator': self._validate_always_draw},
            'xoffset'     : {'value': 0,  'validator': self._validate_bounding_box},
            'yoffset'     : {'value': 0,  'validator': self._validate_bounding_box},
            'zoffset'     : {'value': 0,  'validator': self._validate_bounding_box},
            'xextent'     : {'value': 16, 'validator': self._validate_bounding_box},
            'yextent'     : {'value': 16, 'validator': self._validate_bounding_box},
            'zextent'     : {'value': 16, 'validator': self._validate_bounding_box}
        }
        for i in self.params:
            self.params[i]['is_set'] = False

    def get_sprite_number(self):
        assert not (self.is_set('sprite') and self.is_set('ttdsprite'))
        if not (self.is_set('sprite') or self.is_set('ttdsprite')):
            raise generic.ScriptError("Either 'sprite' or 'ttdsprite' must be set for this layout sprite", self.pos)
        sprite_num = self.get_param('ttdsprite') if self.is_set('ttdsprite') else self.get_param('sprite') | (1 << 31)
        recolor = self.get_param('recolor')
        if recolor == -1:
            sprite_num |= 1 << 14
        elif recolor != 0:
            sprite_num |= 1 << 15
            sprite_num |= recolor << 16
        if self.get_param('always_draw'):
            sprite_num |= 1 << 30
        return sprite_num

    def get_param(self, name):
        assert name in self.params
        return self.params[name]['value']

    def is_set(self, name):
        assert name in self.params
        return self.params[name]['is_set']

    def set_param(self, name, value):
        assert isinstance(name, expression.Identifier)
        assert isinstance(value, expression.Expression) or isinstance(value, action2.SpriteGroupRef)
        name = name.value

        if not name in self.params:
            raise generic.ScriptError("Unknown sprite parameter '%s'" % name, value.pos)
        if self.is_set(name):
            raise generic.ScriptError("Sprite parameter '%s' can be set only once per sprite." % name, value.pos)

        self.params[name]['value'] = self.params[name]['validator'](name, value)
        self.params[name]['is_set'] = True

    def _validate_sprite(self, name, value):
        if not isinstance(value, action2.SpriteGroupRef):
            raise generic.ScriptError("Value of 'sprite' should be a spriteset identifier, possibly with offset", value.pos)
        spriteset = action2.resolve_spritegroup(value.name)

        if len(value.param_list) == 0:
            offset = 0
        elif len(value.param_list) == 1:
            id_dicts = [(spriteset.labels, lambda val, pos: expression.ConstantNumeric(val, pos))]
            offset = value.param_list[0].reduce_constant(id_dicts).value
            generic.check_range(offset, 0, spriteset.action1_count - 1, "offset within spriteset", value.pos)
        else:
            raise generic.ScriptError("Expected 0 or 1 parameter, got " + str(len(value.param_list)), value.pos)

        num = spriteset.action1_num + offset
        generic.check_range(num, 0, (1 << 14) - 1, "sprite", value.pos)
        if self.is_set('ttdsprite'):
            raise generic.ScriptError("Only one 'sprite'/'ttdsprite' definition allowed per ground/building/childsprite", value.pos)
        return num

    def _validate_ttdsprite(self, name, value):
        if not isinstance(value, expression.ConstantNumeric):
            raise generic.ScriptError("Expected a compile-time constant number.", value.pos)

        generic.check_range(value.value, 0, (1 << 14) - 1, "ttdsprite", value.pos)
        if self.is_set('sprite'):
            raise generic.ScriptError("Only one 'sprite'/'ttdsprite' definition allowed per ground/building/childsprite", value.pos)
        return value.value

    def _validate_recolor(self, name, value):
        if not isinstance(value, expression.ConstantNumeric):
            raise generic.ScriptError("Expected a compile-time constant number.", value.pos)
        generic.check_range(value.value, -1, (1 << 14) - 1, "recolor", value.pos)
        return value.value

    def _validate_always_draw(self, name, value):
        if not isinstance(value, expression.ConstantNumeric):
            raise generic.ScriptError("Expected a compile-time constant number.", value.pos)

        if value.value not in (0, 1):
            raise generic.ScriptError("Value of 'always_draw' should be 0 or 1", value.pos)
        #bit has no effect for ground sprites but should be left empty, so ignore it
        return value.value if self.type != Action2LayoutSpriteType.GROUND else 0

    def _validate_bounding_box(self, name, value):
        if not isinstance(value, expression.ConstantNumeric):
            raise generic.ScriptError("Expected a compile-time constant number.", value.pos)
        val = value.value

        if self.type == Action2LayoutSpriteType.GROUND:
            raise generic.ScriptError(name + " can not be set for ground sprites", value.pos)
        elif self.type == Action2LayoutSpriteType.CHILD:
            if name not in ('xoffset', 'yoffset'):
                raise generic.ScriptError(name + " can not be set for child sprites", value.pos)
            generic.check_range(val, 0, 255, name, value.pos)
        else:
            assert self.type == Action2LayoutSpriteType.BUILDING
            if name == 'zoffset':
                if val != 0:
                    raise generic.ScriptError("Value of 'zoffset' should always be 0", value.pos)
            elif name in ('xoffset', 'yoffset'):
                generic.check_range(val, -128, 127, name, value.pos)
            else:
                generic.check_range(val, 0, 255, name, value.pos)
        return val

def get_layout_action2s(spritegroup):
    ground_sprite = None
    building_sprites = []

    feature = spritegroup.feature.value
    if feature not in action2.features_sprite_layout:
        raise generic.ScriptError("Sprite layouts are not supported for this feature: 0x" + generic.to_hex(feature, 2))

    for layout_sprite in spritegroup.layout_sprite_list:
        if layout_sprite.type.value not in layout_sprite_types:
            raise generic.ScriptError("Invalid sprite type '%s' encountered. Expected 'ground', 'building', or 'childsprite'." % layout_sprite.type.value, layout_sprite.type.pos)
        sprite = Action2LayoutSprite(layout_sprite_types[layout_sprite.type.value], layout_sprite.pos)
        for param in layout_sprite.param_list:
            sprite.set_param(param.name, param.value)
        if sprite.type == Action2LayoutSpriteType.GROUND:
            if ground_sprite is not None:
                raise generic.ScriptError("Sprite layout can have no more than one ground sprite", spritegroup.pos)
            ground_sprite = sprite
        else:
            building_sprites.append(sprite)

    if ground_sprite is None:
        if len(building_sprites) == 0:
            #no sprites defined at all, that's not very much.
            raise generic.ScriptError("Sprite layout requires at least one sprite", spritegroup.pos)
        #set to 0 for no ground sprite
        ground_sprite = Action2LayoutSprite(Action2LayoutSpriteType.GROUND)
        ground_sprite.set_param(expression.Identifier('ttdsprite'), expression.ConstantNumeric(0))

    return [Action2Layout(feature, spritegroup.name.value, ground_sprite, building_sprites)]
