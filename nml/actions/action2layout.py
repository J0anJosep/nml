from nml import generic, global_constants, expression, nmlop
from nml.actions import action2, action6, actionD, action1, action2var, real_sprite

class Action2Layout(action2.Action2):
    def __init__(self, feature, name, ground_sprite, sprite_list):
        action2.Action2.__init__(self, feature, name)
        assert ground_sprite.type == Action2LayoutSpriteType.GROUND
        self.ground_sprite = ground_sprite
        self.sprite_list = sprite_list

    def write(self, file):
        advanced = any(x.is_advanced_sprite() for x in self.sprite_list + [self.ground_sprite])
        size = 5
        if advanced: size += self.ground_sprite.get_registers_size()
        for sprite in self.sprite_list:
            if sprite.type == Action2LayoutSpriteType.CHILD:
                size += 7
            else:
                size += 10
            if advanced: size += sprite.get_registers_size()
        if len(self.sprite_list) == 0:
            size += 9

        action2.Action2.write_sprite_start(self, file, size)
        if advanced:
            file.print_byte(0x40 | len(self.sprite_list))
        else:
            file.print_byte(len(self.sprite_list))
        self.ground_sprite.write_sprite_number(file)
        if advanced:
            self.ground_sprite.write_flags(file)
            self.ground_sprite.write_registers(file)
        file.newline()
        if len(self.sprite_list) == 0:
            file.print_dwordx(0) #sprite number 0 == no sprite
            for i in range(0, 5):
                file.print_byte(0) #empty bounding box. Note that number of zeros is 5, not 6
        else:
            for sprite in self.sprite_list:
                sprite.write_sprite_number(file)
                if advanced: sprite.write_flags(file)
                file.print_byte(sprite.get_param('xoffset').value)
                file.print_byte(sprite.get_param('yoffset').value)
                if sprite.type == Action2LayoutSpriteType.CHILD:
                    file.print_bytex(0x80)
                else:
                    #normal building sprite
                    file.print_byte(sprite.get_param('zoffset').value)
                    file.print_byte(sprite.get_param('xextent').value)
                    file.print_byte(sprite.get_param('yextent').value)
                    file.print_byte(sprite.get_param('zextent').value)
                if advanced: sprite.write_registers(file)
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
            'sprite'        : {'value': None, 'validator': self._validate_sprite},
            'recolour_mode' : {'value': 0,  'validator': self._validate_recolour_mode},
            'palette'       : {'value': expression.ConstantNumeric(0), 'validator': self._validate_palette},
            'always_draw'   : {'value': 0,  'validator': self._validate_always_draw},
            'xoffset'       : {'value': expression.ConstantNumeric(0),  'validator': self._validate_bounding_box},
            'yoffset'       : {'value': expression.ConstantNumeric(0),  'validator': self._validate_bounding_box},
            'zoffset'       : {'value': expression.ConstantNumeric(0),  'validator': self._validate_bounding_box},
            'xextent'       : {'value': expression.ConstantNumeric(16), 'validator': self._validate_bounding_box},
            'yextent'       : {'value': expression.ConstantNumeric(16), 'validator': self._validate_bounding_box},
            'zextent'       : {'value': expression.ConstantNumeric(16), 'validator': self._validate_bounding_box},
            'hide_sprite'   : {'value': None, 'validator': self._validate_hide_sprite}, # Value not used
        }
        for i in self.params:
            self.params[i]['is_set'] = False
            self.params[i]['register'] = None
        self.sprite_from_action1 = False
        self.palette_from_action1 = False

    def is_advanced_sprite(self):
        if self.palette_from_action1: return True
        return len(self.get_all_registers()) != 0

    def get_registers_size(self):
        # Number of registers to write
        size = len(self.get_all_registers())
        # Add 2 for the flags
        size += 2
        return size

    def write_flags(self, file):
        flags = 0
        if self.get_register('hide_sprite') is not None:
            flags |= 1 << 0
        if self.get_register('sprite') is not None:
            flags |= 1 << 1
        if self.get_register('palette') is not None:
            flags |= 1 << 2
        if self.palette_from_action1:
            flags |= 1 << 3
        # for building sprites: bit 4 => xoffset+yoffset, bit 5 => zoffset (x and y always set totgether)
        # for child sprites: bit 4 => xoffset, bit 5 => yoffset
        if self.type == Action2LayoutSpriteType.BUILDING:
            assert (self.get_register('xoffset') is not None) == (self.get_register('yoffset') is not None)
        if self.get_register('xoffset') is not None:
            flags |= 1 << 4
        nextreg = 'zoffset' if self.type == Action2LayoutSpriteType.BUILDING else 'yoffset'
        if self.get_register(nextreg) is not None:
            flags |= 1 << 5
        file.print_wordx(flags)

    def write_register(self, file, name):
        register = self.get_register(name)[0]
        file.print_bytex(register.parameter)

    def write_registers(self, file):
        if self.is_set('hide_sprite'):
            self.write_register(file, 'hide_sprite')
        if self.get_register('sprite') is not None:
            self.write_register(file, 'sprite')
        if self.get_register('palette') is not None:
            self.write_register(file, 'palette')
        if self.get_register('xoffset') is not None:
            self.write_register(file, 'xoffset')
        if self.get_register('yoffset') is not None:
            self.write_register(file, 'yoffset')
        if self.get_register('zoffset') is not None:
            self.write_register(file, 'zoffset')

    def write_sprite_number(self, file):
        num = self.get_sprite_number()
        if isinstance(num, expression.ConstantNumeric):
            num.write(file, 4)
        else:
            file.print_dwordx(0)

    def get_sprite_number(self):
        # Layout of sprite number
        # bit  0 - 13: Sprite number
        # bit 14 - 15: Recolour mode (normal/transparent/remap)
        # bit 16 - 29: Palette sprite number
        # bit 30: Always draw sprite, even in transparent mode
        # bit 31: This is a custom sprite (from action1), not a TTD sprite
        if not self.is_set('sprite'):
            raise generic.ScriptError("'sprite' must be set for this layout sprite", self.pos)

        # Make sure that recolouring is set correctly
        if self.get_param('recolour_mode') == 0 and self.is_set('palette'):
            raise generic.ScriptError("'palette' may not be set when 'recolour_mode' is RECOLOUR_NONE.")
        elif self.get_param('recolour_mode') != 0 and not self.is_set('palette'):
            raise generic.ScriptError("'palette' must be set when 'recolour_mode' is not set to RECOLOUR_NONE.")

        # add the constant terms first
        sprite_num = self.get_param('recolour_mode') << 14
        if self.get_param('always_draw'):
            sprite_num |= 1 << 30
        if self.sprite_from_action1:
            sprite_num |= 1 << 31

        add_sprite = False
        sprite = self.get_param('sprite')
        if isinstance(sprite, expression.ConstantNumeric):
            sprite_num |= sprite.value
        else:
            add_sprite = True

        add_palette = False
        palette = self.get_param('palette')
        if isinstance(palette, expression.ConstantNumeric):
            sprite_num |= palette.value << 16
        else:
            add_palette = True

        expr = expression.ConstantNumeric(sprite_num, sprite.pos)
        if add_sprite:
            expr = expression.BinOp(nmlop.ADD, sprite, expr, sprite.pos)
        if add_palette:
            expr = expression.BinOp(nmlop.ADD, palette, expr, sprite.pos)
        return expr.reduce()

    def get_param(self, name):
        assert name in self.params
        return self.params[name]['value']

    def is_set(self, name):
        assert name in self.params
        return self.params[name]['is_set']

    def get_register(self, name):
        assert name in self.params
        return self.params[name]['register']

    def get_all_registers(self):
        return [self.get_register(name) for name in self.params if self.get_register(name) is not None]

    def create_register(self, name, value):
        if isinstance(value, expression.StorageOp) and value.name == "LOAD_TEMP" and isinstance(value.register, expression.ConstantNumeric):
            store_tmp = None
            load_tmp = action2var.VarAction2Var(0x7F, 0, 0xFFFFFFFF, value.register.value)
        else:
            store_tmp = action2var.VarAction2StoreTempVar()
            load_tmp = action2var.VarAction2LoadTempVar(store_tmp)
        self.params[name]['register'] = (load_tmp, store_tmp, value)

    def set_param(self, name, value):
        assert isinstance(name, expression.Identifier)
        assert isinstance(value, expression.Expression) or isinstance(value, expression.SpriteGroupRef)
        name = name.value
        if name == 'ttdsprite':
            name = 'sprite'
            generic.print_warning("Using 'ttdsprite' in sprite layouts is deprecated, use 'sprite' instead", value.pos)

        if not name in self.params:
            raise generic.ScriptError("Unknown sprite parameter '%s'" % name, value.pos)
        if self.is_set(name):
            raise generic.ScriptError("Sprite parameter '%s' can be set only once per sprite." % name, value.pos)

        self.params[name]['value'] = self.params[name]['validator'](name, value)
        self.params[name]['is_set'] = True

    def resolve_spritegroup_ref(self, sg_ref):
        """
        Resolve a reference to a (sprite/palette) sprite group

        @param sg_ref: Reference to a sprite group
        @type sg_ref: L{SpriteGroupRef}

        @return: Sprite number (index of action1 set) to use
        @rtype: L{Expression}
        """
        spriteset = action2.resolve_spritegroup(sg_ref.name)

        if len(sg_ref.param_list) == 0:
            offset = None
        elif len(sg_ref.param_list) == 1:
            id_dicts = [(spriteset.labels, lambda val, pos: expression.ConstantNumeric(val, pos))]
            expression.identifier.ignore_all_invalid_ids = True
            offset = sg_ref.param_list[0].reduce(global_constants.const_list + id_dicts)
            expression.identifier.ignore_all_invalid_ids = False
            if isinstance(offset, expression.ConstantNumeric):
                generic.check_range(offset.value, 0, len(real_sprite.parse_sprite_list(spriteset.sprite_list, spriteset.pcx)) - 1, "offset within spriteset", sg_ref.pos)
        else:
            raise generic.ScriptError("Expected 0 or 1 parameter, got " + str(len(sg_ref.param_list)), sg_ref.pos)

        num = action1.get_action1_index(spriteset)
        generic.check_range(num, 0, (1 << 14) - 1, "sprite", sg_ref.pos)
        return expression.ConstantNumeric(num), offset

    def _validate_sprite(self, name, value):
        if isinstance(value, expression.SpriteGroupRef):
            self.sprite_from_action1 = True
            val, offset = self.resolve_spritegroup_ref(value)
            if offset is not None:
                self.create_register(name, offset)
            return val
        else:
            self.sprite_from_action1 = False
            if isinstance(value, expression.ConstantNumeric):
                generic.check_range(value.value, 0, (1 << 14) - 1, "sprite", value.pos)
                return value
            self.create_register(name, value)
            return expression.ConstantNumeric(0)

    def _validate_recolour_mode(self, name, value):
        if not isinstance(value, expression.ConstantNumeric):
            raise generic.ScriptError("Expected a compile-time constant.", value.pos)

        if not value.value in (0, 1, 2):
            raise generic.ScriptError("Value of 'recolour_mode' must be RECOLOUR_NONE, RECOLOUR_TRANSPARENT or RECOLOUR_REMAP.")
        return value.value

    def _validate_palette(self, name, value):
        if isinstance(value, expression.SpriteGroupRef):
            self.palette_from_action1 = True
            val, offset = self.resolve_spritegroup_ref(value)
            if offset is not None:
                self.create_register(name, offset)
            return val
        else:
            if isinstance(value, expression.ConstantNumeric):
                generic.check_range(value.value, 0, (1 << 14) - 1, "palette", value.pos)
            self.palette_from_action1 = False
            return value

    def _validate_always_draw(self, name, value):
        if not isinstance(value, expression.ConstantNumeric):
            raise generic.ScriptError("Expected a compile-time constant number.", value.pos)
        # Not valid for ground sprites, raise error
        if self.type == Action2LayoutSpriteType.GROUND:
            raise generic.ScriptError("'always_draw' may not be set for groundsprites, these are always drawn anyways.", value.pos)

        if value.value not in (0, 1):
            raise generic.ScriptError("Value of 'always_draw' should be 0 or 1", value.pos)
        return value.value

    def _validate_bounding_box(self, name, value):
        if self.type == Action2LayoutSpriteType.GROUND:
            raise generic.ScriptError(name + " can not be set for ground sprites", value.pos)
        elif self.type == Action2LayoutSpriteType.CHILD:
            if name not in ('xoffset', 'yoffset'):
                raise generic.ScriptError(name + " can not be set for child sprites", value.pos)
            if isinstance(value, expression.ConstantNumeric):
                generic.check_range(value.value, 0, 255, name, value.pos)
                return value
        else:
            assert self.type == Action2LayoutSpriteType.BUILDING
            if name in ('xoffset', 'yoffset', 'zoffset'):
                if isinstance(value, expression.ConstantNumeric):
                    generic.check_range(value.value, -128, 127, name, value.pos)
                    return value
            else:
                assert name in ('xextent', 'yextent', 'zextent')
                if not isinstance(value, expression.ConstantNumeric):
                    raise generic.ScriptError("Value of '%s' must be a compile-time constant number." % name, value.pos)
                generic.check_range(value.value, 0, 255, name, value.pos)
                return value
        # Value must be written to a register
        self.create_register(name, value)
        if self.type == Action2LayoutSpriteType.BUILDING:
            # For building sprites, x and y registers are always written together
            if name == 'xoffset' and self.get_register('yoffset') is None:
                self.create_register('yoffset', expression.ConstantNumeric(0))
            if name == 'yoffset' and self.get_register('xoffset') is None:
                self.create_register('xoffset', expression.ConstantNumeric(0))
        return expression.ConstantNumeric(0)

    def _validate_hide_sprite(self, name, value):
        self.create_register(name, expression.Not(value))
        return None

def get_layout_action2s(spritelayout, feature):
    ground_sprite = None
    building_sprites = []
    actions = []

    if feature not in action2.features_sprite_layout:
        raise generic.ScriptError("Sprite layouts are not supported for feature '%02X'." % feature)

    actions.extend(action1.add_to_action1(spritelayout.used_sprite_sets, feature, spritelayout.pos))

    temp_registers = []
    for layout_sprite in spritelayout.layout_sprite_list:
        if layout_sprite.type.value not in layout_sprite_types:
            raise generic.ScriptError("Invalid sprite type '%s' encountered. Expected 'ground', 'building', or 'childsprite'." % layout_sprite.type.value, layout_sprite.type.pos)
        sprite = Action2LayoutSprite(layout_sprite_types[layout_sprite.type.value], layout_sprite.pos)
        for param in layout_sprite.param_list:
            sprite.set_param(param.name, param.value)
        temp_registers.extend(sprite.get_all_registers())
        if sprite.type == Action2LayoutSpriteType.GROUND:
            if ground_sprite is not None:
                raise generic.ScriptError("Sprite layout can have no more than one ground sprite", spritelayout.pos)
            ground_sprite = sprite
        else:
            building_sprites.append(sprite)

    if ground_sprite is None:
        if len(building_sprites) == 0:
            #no sprites defined at all, that's not very much.
            raise generic.ScriptError("Sprite layout requires at least one sprite", spritegroup.pos)
        #set to 0 for no ground sprite
        ground_sprite = Action2LayoutSprite(Action2LayoutSpriteType.GROUND)
        ground_sprite.set_param(expression.Identifier('sprite'), expression.ConstantNumeric(0))

    action6.free_parameters.save()
    act6 = action6.Action6()

    offset = 4
    sprite_num = ground_sprite.get_sprite_number()
    if not isinstance(sprite_num, expression.ConstantNumeric):
        param, extra_actions = actionD.get_tmp_parameter(sprite_num)
        actions.extend(extra_actions)
        act6.modify_bytes(param, 4, offset)
    offset += 4
    offset += ground_sprite.get_registers_size()

    for sprite in building_sprites:
        sprite_num = sprite.get_sprite_number()
        if not isinstance(sprite_num, expression.ConstantNumeric):
            param, extra_actions = actionD.get_tmp_parameter(sprite_num)
            actions.extend(extra_actions)
            act6.modify_bytes(param, 4, offset)
        offset += sprite.get_registers_size()
        offset += 7 if sprite.type == Action2LayoutSpriteType.CHILD else 10

    if len(act6.modifications) > 0:
        actions.append(act6)

    layout_action = Action2Layout(feature, spritelayout.name.value + (" - feature %02X" % feature), ground_sprite, building_sprites)
    actions.append(layout_action)

    if temp_registers:
        varact2parser = action2var.Varaction2Parser(feature)
        for register_info in temp_registers:
            reg, expr = register_info[1], register_info[2]
            if reg is None: continue
            varact2parser.parse_expr(action2var.reduce_varaction2_expr(expr, feature))
            varact2parser.var_list.append(nmlop.STO_TMP)
            varact2parser.var_list.append(reg)
            varact2parser.var_list.append(nmlop.VAL2)
            varact2parser.var_list_size += reg.get_size() + 2

    # Only continue if we actually needed any new registers
    if temp_registers and varact2parser.var_list:
        #Remove the last VAL2 operator
        varact2parser.var_list.pop()
        varact2parser.var_list_size -= 1

        actions.extend(varact2parser.extra_actions)
        extra_act6 = action6.Action6()
        for mod in varact2parser.mods:
            extra_act6.modify_bytes(mod.param, mod.size, mod.offset + 4)
        if len(extra_act6.modifications) > 0: actions.append(extra_act6)

        varaction2 = action2var.Action2Var(feature, "%s@registers - feature %02X" % (spritelayout.name.value, feature), 0x89)
        varaction2.var_list = varact2parser.var_list
        ref = expression.SpriteGroupRef(spritelayout.name, [], None, layout_action)
        varaction2.ranges.append(action2var.Varaction2Range(expression.ConstantNumeric(0), expression.ConstantNumeric(0), ref, ''))
        varaction2.default_result = ref
        varaction2.default_comment = ''

        # Add two references (default + range)
        action2.add_ref(ref, varaction2)
        action2.add_ref(ref, varaction2)
        spritelayout.set_action2(varaction2, feature)
        actions.append(varaction2)
    else:
        spritelayout.set_action2(layout_action, feature)

    action6.free_parameters.restore()
    return actions
