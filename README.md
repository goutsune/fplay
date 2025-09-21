# <FRS00FPLAY>  Sequencial sound player FPLAY

This repo hosts a thorough study of Compile's PC98 sequence player.

* fplay.i64 - reverse-engineering effort for 2.11a version of the driver (IDA 9.1)
* RSNG.DAT - the smallest sequence example I found
* fplay_parse.py - the sequence parser utility that produces IDA-inspired listings
* vcmds.json - supplemental file that describes sequence grammar, to be explained
* vcmds.json - same, but with more readable grammar words

It is also possible to compile listing files back into playable music bank.

Requirements: fasm (not fasm2 or fasmg), awk, python3

* general.inc - FASM macroses for general listing structures
* gen_macro.py - Generated python code generator for vcmd fasm includes and awk preprocessor


## Example usage

To decompile:

```sh
./fplay_parse.py MADOU.DAT > MADOU.LST     # compact listing
./fplay_parse.py -l MADOU.DAT > MADOU.LST  # long vcmd format
./fplay_parse.py -d MADOU.DAT > MADOU.LST  # prints adress for each token row
```

To compile data back:

```sh
./compile.sh MADOU.LST vcmds.json  # Compiles short format listing
./compile.sh MADOU.LST vcmds_long.json  # Compiles long format listing
./compile.sh MADOU.LST  # Compiles using whatever grammar was used before

# Addres-prefixed listing can't be compiled
```
