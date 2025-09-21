import sys
import builtins
import json
from types import SimpleNamespace

# Override print to use hex() for ints
orig_print = builtins.print

def hex_print(*args, **kwargs):
    new_args = []
    for arg in args:
        if isinstance(arg, int):
            new_args.append(hex(arg))
        else:
            new_args.append(arg)

    orig_print(*new_args, **kwargs)

builtins.print = hex_print


class mkobj(SimpleNamespace):
    def __init__(self, name=None, **kwargs):
        self._name = name if name else "obj"
        if name:
          self.name = name
        super().__init__(**kwargs)

    def annotate(self):
      ''' Another serializer that produces argument list, mainly for comment purpose
      '''
      attrs = []
      for name, attr in vars(self).items():

        # Skip privates
        if name[0] == '_':
          continue

        # Internal use attributes
        if name in ('name', 'text', 'length', 'addr', 'label'):
          continue

        attrs.append(name)

      return f'{self._name} {", ".join(attrs)}'

    def as_macro(self):
      ''' A very silly serializer that deals with much more than it should
      '''

      # For dummy objects that got label added to them
      if self.name == 'location':
        return self.text

      attrs = []
      for name, attr in vars(self).items():

        # Skip privates
        if name[0] == '_':
          continue

        # Internal use attributes
        if name in ('name', 'text', 'length', 'addr', 'label'):
          continue

        # Preformat numbers so that words are hex
        if type(attr) == int:
          if attr > 255:
            res = f'0{attr:04x}h'
          else:
            res = f'{attr:03d}'

        # Vcmd parameters TODO: Add propery to detect these normally
        elif type(attr) == dict and name == 'args':
          # If key name is "n", then emit just value
          res = ' '.join([str(v) for v in attr.values()])

        # Some sequences will have arguments with lists, join them like vararg
        elif type(attr) == list and self.name in ('volSeq', 'gateSeq', 'noiseSeq', 'pitchSeq'):
          res = ' '.join([str(x) for x in attr])

        else:
          res = str(attr)

        attrs.append(res)

      attrs_repr = " ".join(attrs)
      if attrs and attrs[0]:
        return f"{self._name} {attrs_repr}"
      else:
        return self._name

    def __repr__(self):
        attrs = ", ".join(
          f"{k}={v!r}"
          for k, v in vars(self).items()
          if k != "_name"
        )
        return f"{self._name}{attrs}"


class SequenceParser:
  """
  Returns a SimpleNamespace with:
    name: command name | 'note' | 'drum'
    text: human-readable representation
    length: number of bytes consumed from the front of `tokens`
    vcmd: command meta (for kind='command'), else None
    args: dict of parsed args for commands, else {}
    is_terminal: True if command is final ('e' flag), else False
  """

  note_prefixes = ['c', 'cs', 'd', 'ds', 'e', 'f', 'fs', 'g', 'gs', 'a', 'as', 'b']
  param_parsers = {
    'b': lambda x: int.from_bytes(x, byteorder='little', signed=False),
    's': lambda x: int.from_bytes(x, byteorder='little', signed=True),
    'w': lambda x: int.from_bytes(x, byteorder='little', signed=False),
    'c': lambda x: int.from_bytes(x, byteorder='little', signed=False),
  }


  def __init__(self, use_long, data_buffer):
    defs = './vcmds_long.json' if use_long else './vcmds.json'
    with open(defs, 'r', encoding='utf-8') as handle:
      cfg = json.load(handle)
    self.parse_configuration(cfg)
    self.data = data_buffer


  def parse_configuration(self, cfg):
    self.note_lo, self.note_hi = [int(x, 0) for x in cfg['notes']]
    self.drum_lo, self.drum_hi = [int(x, 0) for x in cfg['drums']]

    commands = {}
    cmd_buckets = {}
    buckets_high = 0

    for code, (disp_name, *params) in cfg['commands'].items():
      code = int(code, 0)

      disp_name, *rflags_list = disp_name.split(',')
      rflags = rflags_list.pop() if rflags_list else ''

      is_final = 'f' in rflags
      is_property = 'p' in rflags
      is_control = 'c' in rflags

      signature_length = 1
      parameters = []

      for p in params:
        pname, *pflags_list = p.split(',')
        pflag = pflags_list.pop() if pflags_list else 'b'
        length = 2 if pflag == 'w' else 1
        signature_length += length

        parameter = mkobj(
          name=pname,
          parser=self.param_parsers[pflag],
          length=length,
          flag=pflag
        )
        parameters.append(parameter)

      command = mkobj(
        name=disp_name,
        is_final=is_final,
        is_control=is_control,
        is_property=is_property,
        parameters=parameters,
        length=signature_length
      )

      commands[code] = command
      cmd_buckets.setdefault(signature_length, {})[code] = command
      buckets_high = max(buckets_high, signature_length)

    self.commands = commands
    self.cmd_buckets = cmd_buckets
    self.cmd_buckets_high = buckets_high
    self._bucket_lengths_desc = sorted(self.cmd_buckets.keys(), reverse=True)

  def _note_text(self, value):
    if value < self.note_lo or value > self.note_hi:
      return None
    note = value - self.note_lo
    return f"{self.note_prefixes[note % 12]}{note // 12}"

  def _drum_text(self, value):
    if value < self.drum_lo or value > self.drum_hi:
      return None
    drum = value - self.drum_lo
    return drum

  def _parse_command_tokens(self, tokens):
    first = tokens[0]

    if first > 0xef:
      breakpoint()

    for size in self._bucket_lengths_desc:
      bucket = self.cmd_buckets.get(size)
      if not bucket or first not in bucket:
        continue

      vcmd = bucket[first]
      need = vcmd.length

      if len(tokens) < need:
        raise ValueError(
          f"Not enough bytes for command {vcmd.name}: need {need}, have {len(tokens)}"
        )

      pos = 1
      arg_repr = []
      arg_map = {}

      for p in vcmd.parameters:
        chunk = tokens[pos:pos + p.length]
        val = p.parser(chunk)
        arg_map[p.name] = val
        arg_repr.append(f"{p.name}={val:x}")
        pos += p.length

      if vcmd.parameters:
        text = f"{vcmd.name} {', '.join(arg_repr)}" \
          if vcmd.is_property \
          else f"{vcmd.name}({', '.join(arg_repr)})"
      else:
        text = vcmd.name if vcmd.is_property else f"{vcmd.name}()"

      # Return a dict the caller can pass to mkobj with addr
      return {
        "name": vcmd.name,
        "text": text,
        "length": need,
        "_vcmd": vcmd,
        "args": arg_map,
      }

    return None

  def __call__(self, head_ptr):
    tokens = self.data[head_ptr:]
    first = tokens[0]

    cmd = self._parse_command_tokens(tokens)
    if cmd is not None:
      return mkobj(addr=head_ptr, **cmd)

    # Try parsing as note if we didn't find anything yet
    note = self._note_text(first)
    if note is not None:
      return mkobj(
        name=note,
        addr=head_ptr,
        length=1,
        _vcmd=None,
        args={})

    # Finally as drum
    drum = self._drum_text(first)
    if drum is not None:
      return mkobj(
        name=f'm{drum}',
        addr=head_ptr,
        length=1,
        _vcmd=None,
        args={})

    # Fail otherwise
    raise KeyError(f"Unknown opcode byte: {first:02x}")
