#!/usr/bin/env python3
import struct, argparse
from tools import *

HEADER_BASE_ADDR = 0x4000
MAGIC_OFFSET = 0x400c
MAGIC = b'>MAIKO-HOSHINO '

FM_TONE_TBL = 0x4000
DRUM_MACRO_TBL = 0x400A

NOTE_LEN_TBL = 0x4002
VOL_TBL = 0x4004
PITCH_TBL = 0x4006

SNG_TBL = 0x4008


class GuardedDict(dict):
    def __setitem__(self, key, value):
        if key < HEADER_BASE_ADDR:
            breakpoint()
        return super().__setitem__(key, value)

DATA = b''
ADDR_MAP = GuardedDict()
EVENT_TAIL_MAP = {}
DEBUG_ENABLED = False
LONG_VCMDS = False

boundaries = {
  HEADER_BASE_ADDR,
  #MAGIC_OFFSET,
  #0x401B,
}

def get_word(ptr):
  return int.from_bytes(DATA[ptr:ptr+2], 'little')


def calc_obj_size(obj_loc):
  # Iterate over boundary list and look for the closest offset after our object location
  # Boundary list must be sorted.
  if obj_loc < HEADER_BASE_ADDR or obj_loc >= len(DATA):
    raise ValueError(f'Position {hex(obj_loc)} is outside input data!')

  for pos in sorted(boundaries):
    if pos <= obj_loc:
      continue
    return pos - obj_loc


def proc_fm_table(fm_table_ptr):

  pos = fm_table_ptr
  end = pos + calc_obj_size(fm_table_ptr)

  while pos < end:
    raw = DATA[pos:pos + 0x20]
    inst = mkobj("fmInstrument")

    inst.op1_dtml, inst.op3_dtml, inst.op2_dtml, inst.op4_dtml, inst.op1_tl, inst.op3_tl, inst.op2_tl, \
    inst.op4_tl, inst.op1_ksar, inst.op3_ksar, inst.op2_ksar, inst.op4_ksar, inst.op1_dr, inst.op3_dr, \
    inst.op2_dr, inst.op4_dr, inst.op1_sr, inst.op3_sr, inst.op2_sr, inst.op4_sr, inst.op1_slrr, inst.op3_slrr,\
    inst.op2_slrr, inst.op4_slrr, inst.op1_ssge, inst.op3_ssge, inst.op2_ssge, inst.op4_ssge, inst.fbalg, \
    inst.unused1, inst.unused2, inst.unused3 = \
      struct.unpack('<BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB', raw)
    inst.length = 0x20
    inst._addr = pos
    ADDR_MAP[pos] = inst

    pos += 0x20


def proc_drumseq(drum_seq_ptr, name='gateSeq'):
  pos = drum_seq_ptr
  size = 1
  tokens = []
  while True:

    val = DATA[pos]


    if DATA[pos] == 0xff:
      tokens.append('nEnd')
      break
    # Why does this happen? Typo?
    elif val == 0x81:
      tokens.append('vStop')
      break

    tokens.append(val)
    pos += 1
    size += 1

  ADDR_MAP[drum_seq_ptr] = mkobj(name, _addr=drum_seq_ptr, tokens=tokens, length=size)


def proc_volseq(vol_seq_ptr):
  pos = vol_seq_ptr
  size = 1
  tokens = []

  while True:

    val = DATA[pos]

    if val == 0x80:
      tokens.append('vMark')
      pos += 1
      size += 1
    elif val == 0x81:
      tokens.append('vStop')
      break
    # Whyyy
    elif val == 0xff:
      tokens.append('nEnd')
      break
    elif val == 0x82:
      tokens.append('vRestart')
      pos += 1
      size += 1
    elif val == 0x83:
      tokens.append('vJump')
      pos += 1
      size += 1
      tokens.append(int.from_bytes(DATA[pos:pos+1], byteorder='little'))
      break
    elif val == 0x84:
      tokens.append('vJumpFar')
      pos += 1
      size += 2
      tokens.append(int.from_bytes(DATA[pos:pos+2], byteorder='little'))
      break
    else:
      tokens.append(val)
      pos += 1
      size += 1

  ADDR_MAP[vol_seq_ptr] = mkobj('volSeq', _addr=vol_seq_ptr, tokens=tokens, length=size)


def proc_pitchseq(pitch_seq_ptr):
  pos = pitch_seq_ptr
  size = 1
  tokens = []

  while DATA[pos] > 0x81 or DATA[pos] < 0x80:
    val = int.from_bytes(DATA[pos:pos+1], signed=True)
    tokens.append(val)
    pos += 1
    size += 1

  if DATA[pos] == 0x80:
    tokens.append('pStop')
  elif DATA[pos] == 0x81:
    tokens.append('pJump')
    pos += 1
    size += 1
    tokens.append(int.from_bytes(DATA[pos:pos+1], byteorder='little'))
  else:
    breakpoint()

  ADDR_MAP[pitch_seq_ptr] = mkobj('pitchSeq', _addr=pitch_seq_ptr, tokens=tokens, length=size)


def proc_macro_table(macro_table_ptr):
  pos = macro_table_ptr
  end = pos + calc_obj_size(macro_table_ptr)
  seq_parser = SequenceParser(LONG_VCMDS, DATA)

  while True:

    raw = DATA[pos:pos + 0xb]
    macro = mkobj("drumDef")

    macro.instr, macro.note, macro.vol_mod, macro.vol_env_ptr, macro.pitch_env_ptr, macro.ssg_mask_env_ptr, \
    macro.ssg_noise_env_ptr = struct.unpack('<BBbHHHH', raw)
    macro.note = seq_parser._note_text(macro.note)
    macro.length = 0xb

    end = macro_table_ptr + calc_obj_size(macro_table_ptr)
    if pos > end - 0xb:
      break

    if any(
        x and (x > len(DATA) or x < HEADER_BASE_ADDR)
        for x in (macro.vol_env_ptr, macro.pitch_env_ptr, macro.ssg_mask_env_ptr, macro.ssg_noise_env_ptr)
      ):

      break

    # It's still possible to hit bogus macro structure at this point, check so by verifying pointers
    if macro.vol_env_ptr \
        and macro.vol_env_ptr < len(DATA) \
        and macro.vol_env_ptr > HEADER_BASE_ADDR:
      proc_volseq(macro.vol_env_ptr)

    if macro.pitch_env_ptr \
        and macro.pitch_env_ptr < len(DATA) \
        and macro.pitch_env_ptr > HEADER_BASE_ADDR:
      proc_pitchseq(macro.pitch_env_ptr)

    if macro.ssg_mask_env_ptr \
        and macro.ssg_mask_env_ptr < len(DATA) \
        and macro.ssg_mask_env_ptr > HEADER_BASE_ADDR:
      proc_drumseq(macro.ssg_mask_env_ptr, name='gateSeq',)

    if macro.ssg_noise_env_ptr \
        and macro.ssg_noise_env_ptr < len(DATA) \
        and macro.ssg_noise_env_ptr > HEADER_BASE_ADDR:
      proc_drumseq(macro.ssg_noise_env_ptr, name='noiseSeq',)

    boundaries.update([
      macro.vol_env_ptr,
      macro.pitch_env_ptr,
      macro.ssg_mask_env_ptr,
      macro.ssg_noise_env_ptr])

    ADDR_MAP[pos] = macro

    pos += 0xb


def proc_voltable(vol_seq_tbl):
  pos = vol_seq_tbl
  end = pos + calc_obj_size(vol_seq_tbl)

  while pos < end:
    vol_seq_ptr = get_word(pos)
    ADDR_MAP[pos] = mkobj('pVolSeq', _addr=pos, pos=vol_seq_ptr, length=2)
    boundaries.add(vol_seq_ptr)
    end = vol_seq_tbl + calc_obj_size(vol_seq_tbl)
    proc_volseq(vol_seq_ptr)
    pos += 2


def proc_pitchtable(pitch_env_tbl):
  pos = pitch_env_tbl
  end = pos + calc_obj_size(pitch_env_tbl)

  while pos < end:
    pitch_seq_ptr = get_word(pos)
    ADDR_MAP[pos] = mkobj('pPitchSeq', _addr=pos, pos=pitch_seq_ptr, length=2)
    boundaries.add(pitch_seq_ptr)
    end = pitch_env_tbl + calc_obj_size(pitch_env_tbl)
    proc_pitchseq(pitch_seq_ptr)
    pos += 2


def proc_track(track_ptr):

  if track_ptr in ADDR_MAP and not isinstance(ADDR_MAP[track_ptr], str):
    return EVENT_TAIL_MAP[track_ptr] if track_ptr in EVENT_TAIL_MAP else None

  seq_parser = SequenceParser(LONG_VCMDS, DATA)
  start = track_ptr

  while True:
    res = seq_parser(start)

    ADDR_MAP[res.addr] = res
    if res._vcmd:
      vcmd = res._vcmd
      # Recurse into control flow opcodes, which we can detect by parsing addr parameter
      if vcmd.is_control:
        if 'addr' in res.args:
          proc_track(res.args['addr'])

      if vcmd.is_final:
        return
    start += res.length

def proc_song(song_ptr):
  # Load track pointers and track type from header
  # Structure is 4b flags, 4b track_count then track_count[track_ptr]
  song_props = DATA[song_ptr]
  song_flags = (song_props & 0b11110000) >> 4
  track_count = song_props & 0b00001111
  ADDR_MAP[song_ptr] = mkobj("songDef", flags=song_flags, track_count=track_count, length=1)
  res = []

  track_ptr = song_ptr + 1
  for i in range(0, track_count):

    hdr = DATA[track_ptr:track_ptr + 0xc]
    track = mkobj("track")

    track.num, track.mode, track.vol, track.vol_env, track.pitch_env, track.transpose, \
    track.speed, track.chan, track.seq_ptr, track.instrument, track.unknown = struct.unpack('<BBbBBbBBHBB', hdr)
    track._addr = track_ptr
    track.length = 12

    proc_track(track.seq_ptr)
    ADDR_MAP[track_ptr] = track
    res.append(track)
    track_ptr += 0xc

  return res


def proc_notelentable(note_len_tbl):
  pos = note_len_tbl
  end = pos + calc_obj_size(note_len_tbl)

  while pos < end:
    note_len = DATA[pos]
    ADDR_MAP[pos] = mkobj('noteLen', _addr=pos, duration=note_len, length=1)
    pos += 1


def proc_songtable(song_ptr_tbl):
  # Loop over song header pointers and update boundary set with song header start locations.
  # When our new pointer location overlaps with highest known song header, consider job done.
  # This does not handle weird case with music headers coming above other structures, I guess.

  pos = song_ptr_tbl
  end = pos + calc_obj_size(song_ptr_tbl)

  while True:
    head_addr = get_word(pos)
    boundaries.add(head_addr)
    end = song_ptr_tbl + calc_obj_size(song_ptr_tbl)
    if pos > end or (head_addr > 0 and head_addr < 0x4000) :
      break

    # There are blanks in form of these values, however valid song pointer can come after that
    if head_addr in (0x0000, 0xffff):
      pos += 2
      continue

    song = mkobj('song', _addr=pos, pos=head_addr, length=2)
    ADDR_MAP[pos] = song
    proc_song(head_addr)

    pos += 2

def process_single_label(obj, offset):

  # Skip whatever lies outside our token map
  if offset not in ADDR_MAP:
    return

  reference = ADDR_MAP[offset]
  diff = None

  # Look for closest known object and calculate offset
  if reference is None:
    pos = offset
    while (reference := ADDR_MAP[pos]) is None:
      pos -= 1

    diff = offset - pos

  if hasattr(reference, 'label'):
    label = reference.label
    if diff:
      label += f'+{diff}'
    return label

  if isinstance(reference, str):
    label = f'loc_{offset:x}'
    reference = mkobj('location', text=reference, label=label)
  else:
    label = f'{reference.name}_{offset:x}'
    reference.label = label

  if diff:
    label += f'+{diff}'
  return label

def proc_magic(magic_ptr):
  if FORCE:
    return
  pos = magic_ptr
  end = pos + calc_obj_size(magic_ptr)

  if DATA[pos] > 0x7f or end == pos:
    return

  # Stop on non-ascii
  for i in range(pos, end):
    if DATA[i] > 0x7f or DATA[i] < 0x20:
      end = i

  ADDR_MAP[MAGIC_OFFSET] = mkobj("magic", data=f'"{DATA[pos:end].decode()}"', length=end-pos)


def process_address_map():

  # Pass 0: Clean up bytes which got defining after object processing
  for addr, obj in ADDR_MAP.items():
    if isinstance(obj, str) or obj is None:
      continue

    if not hasattr(obj, 'length'):
      breakpoint()

    length = obj.length

    for i in range(addr+1, addr+length):
      ADDR_MAP[i] = None

  # Pass 1: For all objects with pos attribute, add label at that address
  pointers = ('pos', 'vol_env_ptr', 'pitch_env_ptr', 'ssg_mask_env_ptr', 'ssg_noise_env_ptr', 'seq_ptr')
  for obj_addr, obj in ADDR_MAP.items():
    if isinstance(obj, str) or obj is None:
      continue

    for ref_attr in pointers:
      if hasattr(obj, ref_attr):
        label_name = process_single_label(obj, getattr(obj, ref_attr))
        if label_name:
          setattr(obj, ref_attr, label_name)

    if hasattr(obj, 'args') and type(obj.args) == dict and 'addr' in obj.args:
      label_name = process_single_label(obj, obj.args['addr'])
      if label_name:
        obj.args['addr'] = label_name


def print_listing():

  print('\n\tinclude "general.inc"\n\torg 04000h\n\nstart:')

  # To explicitly add new line on object type change
  hanging = False
  old_obj = str()

  # Print the whole listing
  for addr, obj in ADDR_MAP.items():

    if isinstance(obj, str):
      if (addr - 1 in ADDR_MAP) and (ADDR_MAP[addr-1] is None) or hanging:
        print()
        hanging = False

      print(f'{addr-HEADER_BASE_ADDR:04x}\t{obj}' if DEBUG_ENABLED else f'\t{obj}')

    elif obj is None:
      continue

    else:
      if hasattr(obj, 'label'):
        if hanging: print(); hanging = False
        print(f'\n{obj.label}:')

      # Ugh, I need to add some proper type instead of these lousy heuristics
      if hasattr(obj, '_vcmd'):
        if obj._vcmd and not obj._vcmd.is_property:

          if hanging: print(); hanging = False
          print(f'{addr-HEADER_BASE_ADDR:04x}\t{obj.as_macro()}' if DEBUG_ENABLED else f'\t{obj.as_macro()}' )
        else:

          if not hanging: print('\t', end='')
          print(f'{obj.as_macro()}' , end=' ')
          hanging = True

      else:
        if hanging: print(); hanging = False
        if old_obj != obj.name:

          print(f';\t{obj.annotate()}')

        print(f'{addr-HEADER_BASE_ADDR:04x}\t{obj.as_macro()}' if DEBUG_ENABLED else f'\t{obj.as_macro()}' )
        old_obj = obj.name


def do_barrel_roll(data):

  # Populate maps with raw bytes
  for i, db, in enumerate(DATA[HEADER_BASE_ADDR:], start=HEADER_BASE_ADDR):
    ADDR_MAP[i] = f"db 0{db:02x}h"

  # Gather all pointers and file end location, this will allow us to determine object boundaries.
  fm_inst_ptr = get_word(FM_TONE_TBL)
  macro_table_ptr = get_word(DRUM_MACRO_TBL)
  note_len_ptr = get_word(NOTE_LEN_TBL)
  vol_seq_ptr = get_word(VOL_TBL)
  pitch_seq_ptr = get_word(PITCH_TBL)
  sng_tbl_ptr = get_word(SNG_TBL)

  ADDR_MAP[FM_TONE_TBL] = mkobj("pFmToneTbl", pos=fm_inst_ptr, text=f"dw {fm_inst_ptr:04x}h", length=2)
  ADDR_MAP[DRUM_MACRO_TBL] = mkobj("pDrumMacroTbl", pos=macro_table_ptr, text=f"dw {macro_table_ptr:04x}h", length=2)
  ADDR_MAP[NOTE_LEN_TBL] = mkobj("pNoteLengthTbl", pos=note_len_ptr, text=f"dw {note_len_ptr:04x}h", length=2)
  ADDR_MAP[VOL_TBL] = mkobj("pVolEnvTbl", pos=vol_seq_ptr, text=f"dw {vol_seq_ptr:04x}h", length=2)
  ADDR_MAP[PITCH_TBL] = mkobj("pPitchEnvTbl", pos=pitch_seq_ptr, text=f"dw {pitch_seq_ptr:04x}h", length=2)
  ADDR_MAP[SNG_TBL] = mkobj("pSongTbl", pos=sng_tbl_ptr, text=f"dw {sng_tbl_ptr:04x}h", length=2)

  boundaries.update([
    fm_inst_ptr,
    macro_table_ptr,
    note_len_ptr,
    vol_seq_ptr,
    pitch_seq_ptr,
    sng_tbl_ptr,
    len(DATA),
  ])

  proc_fm_table(fm_inst_ptr)
  proc_voltable(vol_seq_ptr)
  proc_pitchtable(pitch_seq_ptr)
  proc_notelentable(note_len_ptr)
  proc_macro_table(macro_table_ptr)
  proc_songtable(sng_tbl_ptr)
  proc_magic(MAGIC_OFFSET)  # There seem to be interesting stuff from time to time

  process_address_map()
  print_listing()

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Compile FPLAY data parser')
  parser.add_argument('file', help='Path to SONG.DAT')
  parser.add_argument('-d', '--debug', action='store_true', help='Print address of each token')
  parser.add_argument('-f', '--force', action='store_true', help='Don\'t check magic')
  parser.add_argument('-l', '--long', action='store_true', help='Use long command names for listing')
  args = parser.parse_args()

  DEBUG_ENABLED = args.debug
  LONG_VCMDS = args.long
  FORCE = args.force

  with open(args.file, 'rb') as f:
    raw = f.read()

  DATA = b'\x00'*HEADER_BASE_ADDR + raw

  if DATA[MAGIC_OFFSET:MAGIC_OFFSET + len(MAGIC)] != MAGIC and not FORCE:
    raise ValueError('Not a FRS00PLAY data?')

  do_barrel_roll(raw)
