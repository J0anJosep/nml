from nml.actions import action2, action2var_variables
from nml import generic, expression, global_constants, nmlop
import nml.ast

class Action2Random(action2.Action2):
    def __init__(self, feature, name, type_byte, count, triggers, randbit, nrand, choices):
        action2.Action2.__init__(self, feature, name)
        self.type_byte = type_byte
        self.count = count
        self.triggers = triggers
        self.randbit = randbit
        self.nrand = nrand
        self.choices = choices

    def prepare_output(self):
        action2.Action2.prepare_output(self)
        for choice in self.choices:
            if isinstance(choice.result, expression.Identifier):
                choice.result = action2.remove_ref(choice.result.value)
            else:
                choice.result = choice.result.value | 0x8000

    def write(self, file):
        # <type> [<count>] <random-triggers> <randbit> <nrand> <set-ids>
        size = 4 + 2 * self.nrand + (self.count is not None)
        action2.Action2.write(self, file, size)
        file.print_bytex(self.type_byte)
        if self.count is not None: file.print_bytex(self.count)
        file.print_bytex(self.triggers)
        file.print_byte(self.randbit)
        file.print_bytex(self.nrand)
        file.newline()

        for choice in self.choices:
            for i in range(0, choice.resulting_prob):
                file.print_wordx(choice.result)
            file.newline()
        file.end_sprite()

class RandomChoice(object):
    def __init__ (self, probability, result):
        if isinstance(probability, expression.Identifier) and probability.value in ('dependent', 'independent'):
            self.probability = probability
        else:
            self.probability = probability.reduce_constant(global_constants.const_list)
            self.resulting_prob = self.probability.value
            if self.probability.value <= 0:
                raise generic.ScriptError("Value for probability should be higher than 0, encountered %d" % self.probability.value, self.probability.pos)
            if result is None:
                raise generic.ScriptError("Returning the computed value is not possible in a random-block, as there is no computed value.", self.probability.pos)
        self.result = result.reduce(global_constants.const_list, False)

    def debug_print(self, indentation):
        print indentation*' ' + 'Probability:'
        self.probability.debug_print(indentation + 2)
        print indentation*' ' + 'Result:'
        if isinstance(self.result, expression.Identifier):
            print (indentation+2)*' ' + 'Go to switch:'
            self.result.debug_print(indentation + 4);
        else:
            self.result.debug_print(indentation + 2)

    def __str__(self):
        ret = str(self.probability)
        if isinstance(self.result, expression.Identifier):
            ret += ': %s;' % str(self.result)
        else:
            ret += ': return %s;' % str(self.result)
        return ret

num_random_bits = {
    0x00 : [8],
    0x01 : [8],
    0x02 : [8],
    0x03 : [8],
    0x04 : [16, 4],
    0x05 : [8],
    0x06 : [0],
    0x07 : [8],
    0x08 : [0],
    0x09 : [8],
    0x0A : [16],
    0x0B : [0],
    0x0C : [0],
    0x0D : [0],
    0x0E : [0],
    0x0F : [8],
    0x10 : [2],
    0x11 : [16, 4],
}

random_types = {
    'SELF' : {'type': 0x80, 'range': 0, 'param': 0},
    'PARENT' : {'type': 0x83, 'range': 0, 'param': 0},
    'TILE' : {'type': 0x80, 'range': 1, 'param': 0},
    'BACKWARD_SELF' : {'type': 0x84, 'range': 0, 'param': 1, 'value': 0x00},
    'FORWARD_SELF' : {'type': 0x84, 'range': 0, 'param': 1, 'value': 0x40},
    'BACKWARD_ENGINE' : {'type': 0x84, 'range': 0, 'param': 1, 'value': 0x80},
    'BACKWARD_SAMEID' : {'type': 0x84, 'range': 0, 'param': 1, 'value': 0xC0},
}

def parse_randomblock(random_block):
    feature = random_block.feature.value

    #parse type
    if isinstance(random_block.type, expression.Identifier):
        type_name = random_block.type.value
        type_param = None
    elif isinstance(random_block.type, expression.FunctionCall):
        type_name = random_block.type.name.value
        if len(random_block.type.params) == 0:
            type_param = None
        elif len(random_block.type.params) == 1:
            type_param = random_block.type.params[0]
        else:
            raise generic.ScriptError("Value for random-block parameter 2 'type' can have only one parameter.", random_block.type.pos)
    else:
        raise generic.ScriptError("Random-block parameter 2 'type' should be an identifier, possibly with a parameter.", random_block.type.pos)
    if type_name in random_types:
        if type_param is None:
            if random_types[type_name]['param'] == 1:
                raise generic.ScriptError("Value '%s' for random-block parameter 2 'type' requires a parameter." % type_name, random_block.type.pos)
            count_type = None
        else:
            if random_types[type_name]['param'] == 0:
                raise generic.ScriptError("Value '%s' for random-block parameter 2 'type' should not have a parameter." % type_name, random_block.type.pos)
            if not (0 <= feature <= 3):
                raise generic.ScriptError("Value '%s' for random-block parameter 2 'type' is valid only for vehicles." % type_name, random_block.type.pos)
            count_type = random_types[type_name]['value']
            count_expr = type_param
        type = random_types[type_name]['type']
        bit_range = random_types[type_name]['range']
    else:
        raise generic.ScriptError("Unrecognized value for random-block parameter 2 'type': " + type_name, random_block.type.pos)
    assert (type == 0x84) == (count_type is not None)

    if feature not in num_random_bits:
        raise generic.ScriptError("Invalid feature for random-block: " + str(feature), random_block.feature.pos)
    if type == 0x83: feature = action2var_variables.varact2parent_scope[feature]
    if feature is None:
        raise generic.ScriptError("Feature '%d' does not have a 'PARENT' scope." % random_block.feature.value, random_block.feature.pos)
    if bit_range != 0 and feature not in (0x04, 0x11):
        raise generic.ScriptError("Type 'TILE' is only supported for stations and airport tiles.")
    bits_available = num_random_bits[feature][bit_range]
    start_bit = sum(num_random_bits[feature][0:bit_range])
    if bits_available == 0:
        raise generic.ScriptError("No random data is available for the given feature and scope, feature: " + str(feature), random_block.feature.pos)

    #determine total probability
    total_prob = 0
    for choice in random_block.choices:
        total_prob += choice.probability.value
        #make reference
        if isinstance(choice.result, expression.Identifier):
            if choice.result.value != 'CB_FAILED':
                action2.add_ref(choice.result.value)
        elif not isinstance(choice.result, expression.ConstantNumeric):
            raise generic.ScriptError("Invalid return value in random-block.", choice.result.pos)
    if len(random_block.choices) == 0:
        raise generic.ScriptError("random-block requires at least one possible choice", random_block.pos)
    assert total_prob > 0

    #How many random bits are needed ?
    nrand = 1
    while nrand < total_prob: nrand <<= 1
    #verify that enough random data is available
    if min(1 << bits_available, 0x80) < nrand:
        raise generic.ScriptError("The maximum sum of all random-block probabilities is %d, encountered %d." % (min(1 << bits_available, 0x80), total_prob), random_block.pos)

    #Dependent random chains
    act2_to_copy = None
    for dep in random_block.dependent:
        if dep.value not in action2.action2_map:
            raise generic.ScriptError("Unknown identifier of random-block: " + dep.value, dep.pos)
        act2 = action2.action2_map[dep.value]
        if not isinstance(act2, Action2Random):
            raise generic.ScriptError("Value for 'dependent' (%s) should refer to another random-block" % dep.value, dep.pos)
        if act2_to_copy is not None:
            if act2_to_copy.randbit != act2.randbit:
                raise generic.ScriptError("Random-block '%s' cannot be dependent on both '%s' and '%s' as these are independent of eachother." %
                    (random_block.name.value, act2_to_copy.name, act2.name), random_block.pos)
            if act2_to_copy.nrand != act2.nrand:
                raise generic.ScriptError("Random-block '%s' cannot be dependent on both '%s' and '%s' as they don't use the same amount of random data." %
                    (random_block.name.value, act2_to_copy.name, act2.name), random_block.pos)
        else:
            act2_to_copy = act2

    if act2_to_copy is not None:
        randbit = act2_to_copy.randbit
        if nrand > act2_to_copy.nrand:
            raise generic.ScriptError("Random-block '%s' cannot be dependent on '%s' as it requires more random data." %
                (random_block.name.value, act2_to_copy.name), random_block.pos)
        nrand = act2_to_copy.nrand
    else:
        randbit = -1

    #INdependent random chains
    possible_mask = ((1 << bits_available) - 1) << start_bit
    for indep in random_block.independent:
        if indep.value not in action2.action2_map:
            raise generic.ScriptError("Unknown identifier of random-block: " + indep.value, indep.pos)
        act2 = action2.action2_map[indep.value]
        if not isinstance(act2, Action2Random):
            raise generic.ScriptError("Value for 'independent' (%s) should refer to another random-block" % indep.value, indep.pos)
        possible_mask &= ~((act2.nrand - 1) << act2.randbit)

    required_mask = nrand - 1
    if randbit != -1:
        #randbit has already been determined. Check that it is suitable
        if possible_mask & (required_mask << randbit) != (required_mask << randbit):
            raise generic.ScriptError("Combination of dependence on and independence from random-blocks is not possible for random-block '%s'." % random_block.name.value, random_block.pos)
    else:
        #find a suitable randbit
        for i in range(start_bit, bits_available + start_bit):
            if possible_mask & (required_mask << i) == (required_mask << i):
                randbit = i
                break
        else:
            raise generic.ScriptError("Independence of all given random-blocks is not possible for random-block '%s'." % random_block.name.value, random_block.pos)

    #divide the 'extra' probabilities in an even manner
    i = 0
    while i < (nrand - total_prob):
        best_choice = None
        best_ratio = 0
        for choice in random_block.choices:
            #float division, so 9 / 10 = 0.9
            ratio = choice.probability.value / float(choice.resulting_prob + 1)
            if ratio > best_ratio:
                best_ratio = ratio
                best_choice = choice
        assert best_choice is not None
        best_choice.resulting_prob += 1
        i += 1

    #handle the 'count' parameter, if necessary
    need_varact2 = False
    if count_type is not None:
        try:
            expr = count_expr.reduce_constant(global_constants.const_list)
            if not (1 <= expr.value <= 15):
                need_varact2 = True
        except generic.ConstError:
            need_varact2 = True
        except generic.ScriptError:
            need_varact2 = True
        count = count_type if need_varact2 else count_type | expr.value
        name = random_block.name.value + '@random'
    else:
        count = None
        name = random_block.name.value
    action_list = [Action2Random(random_block.feature.value, name, type, count, random_block.triggers.value, randbit, nrand, random_block.choices)]

    if need_varact2:
        #Add varaction2 that stores count_expr in temporary register 0x100
        pos = random_block.pos
        va2_feature = expression.ConstantNumeric(random_block.feature.value)
        va2_range = expression.Identifier('SELF', pos)
        va2_name = expression.Identifier(random_block.name.value, pos)
        va2_expr = expression.BinOp(nmlop.STO_TMP, count_expr, expression.ConstantNumeric(0x100))
        va2_body = nml.ast.SwitchBody([], expression.Identifier(name, pos))
        switch = nml.ast.Switch(va2_feature, va2_range, va2_name, va2_expr, va2_body, pos)
        action_list.extend(switch.get_action_list())
    return action_list
