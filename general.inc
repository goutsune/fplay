include "vcmds.inc"

macro pFmToneTbl addr {
  dw addr
}

macro pNoteLengthTbl addr {
  dw addr
}

macro pVolEnvTbl addr {
  dw addr
}

macro pPitchEnvTbl addr {
  dw addr
}

macro pSongTbl addr {
  dw addr
}

macro pDrumMacroTbl addr {
  dw addr
}

macro pPitchSeq addr {
  dw addr
}

macro pVolSeq addr {
  dw addr
}

;Volume sequence defs
vMark = 080h
vStop = 081h
vRestart = 082h
vJump = 083h
vJumpFar = 084h

macro volSeq args& {
    db args
}

;Pitch sequence defs
pStop = 080h
pJump = 081h

macro pitchSeq args& {
    db args
}

;SSG noise mixer and period sequences
nEnd = 0ffh

macro gateSeq args& {
    db args
}

macro noiseSeq args& {
    db args
}

;TODO: Ungobble FM definition to something more readable
macro fmInstrument op1_dtml, op3_dtml, op2_dtml, op4_dtml, op1_tl, op3_tl, op2_tl, op4_tl, op1_ksar, op3_ksar, op2_ksar, op4_ksar, op1_dr, op3_dr, op2_dr, op4_dr, op1_sr, op3_sr, op2_sr, op4_sr, op1_slrr, op3_slrr, op2_slrr, op4_slrr, op1_ssge, op3_ssge, op2_ssge, op4_ssge, fbalg, unused1, unused2, unused3
{
  db op1_dtml
  db op3_dtml
  db op2_dtml
  db op4_dtml
  db op1_tl
  db op3_tl
  db op2_tl
  db op4_tl
  db op1_ksar
  db op3_ksar
  db op2_ksar
  db op4_ksar
  db op1_dr
  db op3_dr
  db op2_dr
  db op4_dr
  db op1_sr
  db op3_sr
  db op2_sr
  db op4_sr
  db op1_slrr
  db op3_slrr
  db op2_slrr
  db op4_slrr
  db op1_ssge
  db op3_ssge
  db op2_ssge
  db op4_ssge
  db fbalg
  db unused1
  db unused2
  db unused3
}

macro drumDef instr, note, vol_mod, vol_env_ptr, pitch_env_ptr, ssg_mask_env_ptr, ssg_noise_env_ptr
{
  db instr
  db note
  db vol_mod
  dw vol_env_ptr
  dw pitch_env_ptr
  dw ssg_mask_env_ptr
  dw ssg_noise_env_ptr
}

macro songDef flags, track_count {
  db (flags shl 4) or (track_count and 0Fh)
}

macro track num, mode, vol, vol_env, pitch_env, transpose, speed, chan, seq_ptr, instrument, unknown {
  db num
  db mode
  db vol
  db vol_env
  db pitch_env
  db transpose
  db speed
  db chan
  dw seq_ptr
  db instrument
  db unknown
}

macro magic str {
  db str
}

macro noteLen n {
  db n
}

macro song addr {
  dw addr
}

macro tr [token] {
  forward
    db token
}
