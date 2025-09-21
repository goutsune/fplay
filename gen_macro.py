#!/usr/bin/env python3
import json, re, argparse

NOTE_NAMES = ["c","cs","d","ds","e","f","fs","g","gs","a","as","b"]

# Disclaimer: ChatGPT-generated, I am lazy to build proper DSL compiler.
def parse_hex_or_int(s) -> int:
  s = s.strip().lower()
  return int(s, 0)


def sanitize_ident(name) -> str:
  n = re.sub(r"[^A-Za-z0-9_]", "_", name)
  return "_" + n if re.match(r"^\d", n) else n


def split_name_and_flags(s):
  parts = [p.strip() for p in s.split(",", 1)]
  return (parts[0], parts[1] if len(parts) == 2 else "")


def parse_arg_descriptor(s):
  parts = [p.strip() for p in s.split(",", 1)]
  return (parts[0], parts[1] if len(parts) == 2 else "")


def is_word_attr(attr) -> bool:
  return attr == "w"


def emit_note_equates(start_hex, end_hex) -> str:
  start, end = parse_hex_or_int(start_hex), parse_hex_or_int(end_hex)
  if end < start: raise ValueError("notes: end < start")
  out, idx = [], 0
  for val in range(start, end + 1):
    out.append(f"{NOTE_NAMES[idx % 12]}{idx // 12} = 0{val:02x}h")
    idx += 1
  return "\n".join(out)

def emit_drum_equates(start_hex, end_hex) -> str:
  start, end = parse_hex_or_int(start_hex), parse_hex_or_int(end_hex)
  if end < start: raise ValueError("drums: end < start")
  return "\n".join(f"m{i} = 0{val:02x}h" for i, val in enumerate(range(start, end + 1)))

def generate_command_macros(commands):
  lines = []
  for opcode_hex in commands.keys():
    spec = commands[opcode_hex]
    opcode = parse_hex_or_int(opcode_hex)
    if not spec: continue

    name_raw, _ = split_name_and_flags(spec[0])
    name = sanitize_ident(name_raw)
    args = [parse_arg_descriptor(x) for x in spec[1:]]
    params = [sanitize_ident(a or f"arg{i+1}") for i, (a, _) in enumerate(args)]
    lines.append(f"macro {name}" + ("" if not params else " " + ", ".join(params)) + " {")
    lines.append(f"  db 0{opcode:x}h")
    for i, (_, attr) in enumerate(args):
      lines.append(("  dw " if is_word_attr(attr) else "  db ") + params[i])
    lines.append("}\n")
  return "\n".join(lines)

def generate_include(data) -> str:
  notes = data["notes"]
  drums = data["drums"]
  commands = data["commands"]

  return f"""\
; ==== AUTO-GENERATED FASM INCLUDE ====
  use16

; --- note equates ---
{emit_note_equates(notes[0], notes[1])}

; --- drum equates ---
{emit_drum_equates(drums[0], drums[1])}

; --- command macros ---
{generate_command_macros(commands)}"""

def build_cmd_arity(commands):
  arity = {}
  for _, spec in commands.items():
    if not spec: continue
    name_raw, _ = split_name_and_flags(spec[0])
    arity[sanitize_ident(name_raw)] = max(0, len(spec) - 1)
  return arity

def generate_note_base_init():
  # emit AWK associative array initializers for semitone bases
  return "\n  " + "\n  ".join([f'note_base["{n}"]={i}' for i, n in enumerate(NOTE_NAMES)])

def generate_awk_preprocessor(data):
  notes = data["notes"]
  drums = data["drums"]
  commands = data["commands"]

  note_count = parse_hex_or_int(notes[1]) - parse_hex_or_int(notes[0]) + 1
  drum_count = parse_hex_or_int(drums[1]) - parse_hex_or_int(drums[0]) + 1
  max_note_idx = note_count - 1
  max_drum_idx = drum_count - 1

  arity = build_cmd_arity(commands)
  argless = sorted([k for k,v in arity.items() if v == 0])

  passthru = [
    "db","dw","dd","dq","rb","rw","rd","rq","times","org","use16","use32","use64",
    "equ","macro","endm","include","if","else","endif","align","label","format"
  ]

  arity_init = ("\n  " + "\n  ".join([f'arity["{k}"]={arity[k]}' for k in sorted(arity)])) if arity else ""
  arg0_init = ("\n  " + "\n  ".join([f'arg0["{k}"]=1' for k in argless])) if argless else ""
  passthru_init = "\n  " + "\n  ".join([f'pass["{p}"]=1' for p in passthru])
  note_base_init = generate_note_base_init()
  note_regex = "^(" + "|".join(NOTE_NAMES) + ")[0-9]+$"

  awk = f"""\
# ==== AUTO-GENERATED AWK PREPROCESSOR ====
# Usage: awk -f preproc.awk < input.asm > output.asm
# Splits vcmds into one-per-line and groups argless/note/drum into tr lines.
# Adds commas for whitespace-separated macro args on unknown-but-not-assembly lines.
BEGIN {{
  OFS=""; ORS="\\n";
{arity_init}
{arg0_init}
{passthru_init}
  max_note_idx={max_note_idx};
  max_drum_idx={max_drum_idx};
  note_re="{note_regex}";
  drum_re="^m[0-9]+$";
{note_base_init}
}}

function ltrim(s) {{ sub(/^([ \\t]+)/, "", s); return s; }}
function rtrim(s) {{ sub(/[ \\t]+$/, "", s); return s; }}
function trim(s)  {{ return rtrim(ltrim(s)); }}
function leading_ws(s,  m) {{ if (match(s,/^[ \\t]+/)) return substr(s, RSTART, RLENGTH); return ""; }}

# Tokenizer that respects quoted strings and escaped quotes
function tokenize(s, arr,    i,c,n,in_q,qch,tok,nextc) {{
  n=0; in_q=0; qch=""; tok="";
  for(i=1;i<=length(s);i++) {{
    c=substr(s,i,1);
    if(in_q) {{
      if(c=="\\"" && i<length(s)) {{
        nextc=substr(s,i+1,1);
        if(nextc==qch) {{ tok=tok c nextc; i++; continue; }}
      }}
      if(c==qch) {{ tok=tok c; in_q=0; qch=""; continue; }}
      tok=tok c; continue;
    }}
    if(c=="\\"" || c=="'") {{ in_q=1; qch=c; tok=tok c; continue; }}
    if(c ~ /[ \\t]/) {{
      if(tok!="") {{ n++; arr[n]=tok; tok=""; }}
      continue;
    }}
    tok=tok c;
  }}
  if(tok!="") {{ n++; arr[n]=tok; }}
  return n;
}}

function is_number(tok){{
  return (tok ~ /^-?[0-9]+$/) || (tok ~ /^0[xX][0-9A-Fa-f]+$/) || (tok ~ /^[0-9]+[QqWwDdBbHh]$/);
}}
function looks_like_passthru(tok){{ return (tok in pass); }}

function is_note(tok,    prefix,oct,idx) {{
  if (!(tok ~ note_re)) return 0;
  prefix = tok; sub(/[0-9]+$/, "", prefix);  # c, cs, ...
  oct = tok; sub(/^[A-Za-z]+/, "", oct); oct = oct + 0;
  if (!(prefix in note_base)) return 0;
  idx = oct*12 + note_base[prefix];
  return (idx >= 0 && idx <= max_note_idx);
}}
function is_drum(tok, s) {{
  if (!(tok ~ drum_re)) return 0;
  s = substr(tok,2); return ((s+0) >= 0 && (s+0) <= max_drum_idx);
}}
function has_arity(tok) {{ return (tok in arity); }}
function arity_of(tok) {{ return (tok in arity)?arity[tok]:-1; }}
function is_arg0(tok) {{ return (tok in arg0); }}

{{
  line=$0
  # keep comments intact but out of the parser’s way
  cpos = index(line, ";")
  comment = ""; body = line
  if (cpos > 0) {{ comment = substr(line, cpos); body = substr(line, 1, cpos-1); }}

  if (match(body, /^[ \\t]*$/)) {{ print $0; next; }}
  if (match(body, /^[ \\t]*[A-Za-z_][A-Za-z0-9_]*:[ \\t]*$/)) {{ print $0; next; }}

  l = leading_ws(body); body = trim(body);
  nt = tokenize(body, toks);

  if (nt==0) {{ print $0; next; }}

  head = toks[1];
  if (looks_like_passthru(head) || head ~ /^(db|dw|dd|dq|rb|rw|rd|rq)$/ || body ~ /^[ \\t]*%/) {{
    print $0; next;
  }}

  # Unknown macro with space-separated args and no commas: add commas safely
  if (!(has_arity(head)) && !(is_note(head)) && !(is_drum(head)) && !(is_number(head)) && index(body, ",")==0 && nt>1) {{
    printf "%s%s ", l, head;
    for (j=2; j<=nt; j++) printf (j==2?"":", ") "%s", toks[j];
    if (comment!="") printf " %s", comment;
    print "";
    next;
  }}

  i=1; trN=0;
  while (i <= nt) {{
    t = toks[i];
    if (has_arity(t) && arity_of(t) > 0) {{
      if (trN>0) {{
        printf "%str ", l;
        for (k=1; k<=trN; k++) printf (k==1?"":", ") "%s", trbuf[k];
        print ""; trN=0;
      }}
      need = arity_of(t);
      printf "%s%s ", l, t;
      for (k=1; k<=need; k++) {{
        if (i+k > nt) break;
        printf (k==1?"":", ") "%s", toks[i+k];
      }}
      print "";
      i += need + 1; continue;
    }}
    if (is_note(t) || is_drum(t)) {{ trN++; trbuf[trN]=t; i++; continue; }}
    if (trN>0) {{
      printf "%str ", l;
      for (k=1; k<=trN; k++) printf (k==1?"":", ") "%s", trbuf[k];
      print ""; trN=0;
    }}
    print l t; i++;
  }}
  if (trN>0) {{
    printf "%str ", l;
    for (k=1; k<=trN; k++) printf (k==1?"":", ") "%s", trbuf[k];
    print "";
  }}
  next;
}}
"""
  return awk

def main():
  ap = argparse.ArgumentParser(description="Generate vcmds.inc and preproc.awk from JSON grammar.")
  ap.add_argument("grammar", help="Path to grammar file")
  args = ap.parse_args()

  with open(args.grammar, "r", encoding="utf-8") as f:
    data = json.load(f)

  with open("vcmds.inc", "w", encoding="utf-8") as f:
    f.write(generate_include(data))
  with open("preproc.awk", "w", encoding="utf-8") as f:
    f.write(generate_awk_preprocessor(data))

if __name__ == "__main__":
  main()
