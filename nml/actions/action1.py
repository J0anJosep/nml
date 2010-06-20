from nml import generic
from nml.actions import action2real, action2layout, real_sprite

class Action1(object):
    def __init__(self, feature, num_sets, num_ent):
        self.feature = feature
        self.num_sets = num_sets
        self.num_ent = num_ent

    def prepare_output(self):
        pass

    def write(self, file):
        #<Sprite-number> * <Length> 01 <feature> <num-sets> <num-ent>
        file.start_sprite(6)
        file.print_bytex(1)
        self.feature.write(file, 1)
        file.print_byte(self.num_sets)
        file.print_varx(self.num_ent, 3)
        file.newline()
        file.end_sprite()

    def skip_action7(self):
        return True

    def skip_action9(self):
        return True

    def skip_needed(self):
        return True

class SpriteSet(object):
    def __init__(self, name, pcx, sprite_list, pos):
        self.name = name
        self.pcx = pcx
        self.sprite_list = sprite_list
        self.pos = pos

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite set:', self.name.value
        print (indentation+2)*' ' + 'Source:  ', self.pcx.value
        print (indentation+2)*' ' + 'Sprites:'
        for sprite in self.sprite_list:
            sprite.debug_print(indentation + 4)

class SpriteGroup(object):
    def __init__(self, name, spriteview_list):
        self.name = name
        self.spriteview_list = spriteview_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Sprite group:', self.name.value
        for spriteview in self.spriteview_list:
            spriteview.debug_print(indentation + 2)

class LayoutSpriteGroup(object):
    def __init__(self, name, layout_sprite_list):
        self.name = name
        self.layout_sprite_list = layout_sprite_list

    def debug_print(self, indentation):
        print indentation*' ' + 'Tile layout sprite group:', self.name.value
        for layout_sprite in self.layout_sprite_list:
            layout_sprite.debug_print(indentation + 2)

#vehicles, stations, canals, cargos, airports, railtypes, houses, industry tiles, airport tiles
action1_features = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x0B, 0x0D, 0x10, 0x07, 0x09, 0x11]

def parse_sprite_block(sprite_block):
    global action1_features
    action_list = [None] #reserve one for action 1
    action_list_append = []
    spritesets = {} #map names to action1 entries
    num_sets = 0
    num_ent = -1

    if sprite_block.feature.value not in action1_features:
        raise generic.ScriptError("Sprite blocks are not supported for this feature: 0x" + generic.to_hex(sprite_block.feature.value, 2), feature.pos)

    for item in sprite_block.spriteset_list:
        if isinstance(item, SpriteSet):
            real_sprite_list = real_sprite.parse_sprite_list(item.sprite_list)
            spritesets[item.name.value] = num_sets
            num_sets += 1

            if num_ent == -1:
                num_ent = len(real_sprite_list)
            elif num_ent != len(real_sprite_list):
                raise generic.ScriptError("All sprite sets in a spriteblock should contain the same number of sprites. Expected " + str(num_ent) + ", got " + str(len(item.sprite_list)), item.pos)

            last_sprite = real_sprite_list[-1][0]
            for sprite, id_dict in real_sprite_list:
                action_list.append(real_sprite.parse_real_sprite(sprite, item.pcx, sprite == last_sprite, id_dict))

        elif isinstance(item, SpriteGroup):
            action_list_append.extend(action2real.get_real_action2s(item, sprite_block.feature.value, spritesets))
        else:
            assert isinstance(item, LayoutSpriteGroup)
            action_list_append.extend(action2layout.get_layout_action2s(item, sprite_block.feature.value, spritesets))

    action_list[0] = Action1(sprite_block.feature, num_sets, num_ent)
    action_list.extend(action_list_append)
    return action_list
