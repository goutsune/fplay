#!/usr/bin/env bash

which fasm || exit $?

if [[ -n "$2" ]]; then
  ./gen_macro.py "$2"
fi

awk -f preproc.awk < "$1" > "$1".asm
fasm -m 65536 "$1".asm
