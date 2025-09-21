# <FRS00FPLAY>  Sequencial sound player FPLAY

This repo hosts a thorough study of Compile's PC98 sequence player.

* fplay.i64 - Reverse-engineering effort for 2.11a version of the driver (IDA 9.1)
* fplay.lst - IDA listing export
* RSNG.DAT - The smallest sequence example I found
* RSNG.M - Decompilation example with my lousy sequence splitting
* fplay_parse.py - The sequence parser utility that produces IDA-inspired listings
* vcmds.json - Supplemental file that describes sequence grammar, to be explained
* vcmds_long.json - Same, but with more readable grammar words

It is also possible to compile listing files back into playable music bank.

Requirements: fasm (not fasm2 or fasmg), awk, python3

* general.inc - FASM macroses for general listing structures
* gen_macro.py - Generated python code generator for vcmd fasm includes and awk preprocessor


## Example usage

To decompile:

```sh
./fplay_parse.py MADOU.DAT > MADOU.M     # compact listing
./fplay_parse.py -l MADOU.DAT > MADOU.M  # long vcmd format
./fplay_parse.py -d MADOU.DAT > MADOU.M  # prints adress for each token row
```

To compile data back:

```sh
# Address-prefixed listing can't be compiled
./compile.sh MADOU.M vcmds.json  # Compiles short format listing
./compile.sh MADOU.M vcmds_long.json  # Compiles long format listing
./compile.sh MADOU.M  # Compiles using whatever grammar was used before
```
