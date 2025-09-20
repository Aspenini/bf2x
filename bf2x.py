#!/usr/bin/env python3
# bf2x.py — Brainfuck → multi-target transpiler (no JS/GDScript)
# Targets:
#   1 Python  (.py)   [auto-run]
#   2 Go      (.go)   [auto-run if `go` exists]
#   3 C++     (.cpp)
#   4 C#      (.cs)
#   5 Lua     (.lua)
#   6 Ruby    (.rb)
#   7 Rust    (.rs)
#   0 ALL     (emit all; auto-run py/go if available)

import sys, os, subprocess, tkinter as tk
from tkinter import filedialog

BF_OPS = set("><+-.,[]")

# ---------- Front-end ----------
def sanitize(src: str) -> str:
    return "".join(c for c in src if c in BF_OPS)

def fold_runs(ops: str):
    out = []; i = 0; n = len(ops)
    while i < n:
        c = ops[i]
        if c in "+-<>":
            j = i + 1
            while j < n and ops[j] == c: j += 1
            out.append((c, j - i)); i = j
        else:
            out.append((c, 1)); i += 1
    return out

def desugar(tokens):
    out = []; i = 0
    while i < len(tokens):
        if i + 2 < len(tokens) and tokens[i] == ('[',1) and tokens[i+1] == ('-',1) and tokens[i+2] == (']',1):
            out.append(('CLR',1)); i += 3
        else:
            out.append(tokens[i]); i += 1
    return out

# ---------- Emitters ----------
def emit_python(tokens) -> str:
    L = []; w = L.append
    w("import sys")
    w("tape = bytearray(300000)"); w("dp = 0"); w("out = []")
    w("")
    w("def getchar():")
    w("    b = sys.stdin.buffer.read(1)")
    w("    return b[0] if b else 0")
    w("")
    ind = 0
    def e(s): L.append(('    '*ind)+s)
    for op, n in tokens:
        if   op == '>': e(f"dp += {n}")
        elif op == '<': e(f"dp -= {n}")
        elif op == '+': e(f"tape[dp] = (tape[dp] + {n}) & 255")
        elif op == '-': e(f"tape[dp] = (tape[dp] - {n}) & 255")
        elif op == '.':
            e("out.append(tape[dp])") if n == 1 else e(f"for _ in range({n}): out.append(tape[dp])")
        elif op == ',':
            if n == 1: e("tape[dp] = getchar()")
            else: e(f"for _ in range({n}): tape[dp] = getchar()")
        elif op == 'CLR': e("tape[dp] = 0")
        elif op == '[': e("while tape[dp] != 0:"); ind += 1
        elif op == ']': ind = max(0, ind - 1)
    w("sys.stdout.buffer.write(bytes(out))")
    w("")
    return "\n".join(L)

def emit_go(tokens) -> str:
    has_in = any(op == ',' for op, _ in tokens)
    L = []; w = L.append
    w("package main"); w("")
    w("import (")
    w('    "bufio"')
    if has_in: w('    "io"')
    w('    "os"')
    w(")"); w("")
    w("func main(){")
    w("    tape := make([]byte, 300000)")
    w("    dp := 0")
    w("    out := bufio.NewWriter(os.Stdout)")
    w("    defer out.Flush()")
    if has_in:
        w("    in := bufio.NewReader(os.Stdin)")
        w("    getchar := func() byte {")
        w("        b, err := in.ReadByte()")
        w("        if err != nil { if err == io.EOF { return 0 }; return 0 }")
        w("        return b")
        w("    }")
    ind = 1
    def e(s): L.append(('    '*ind)+s)
    for op, n in tokens:
        if   op == '>': e(f"dp += {n}")
        elif op == '<': e(f"dp -= {n}")
        elif op == '+': e(f"tape[dp] = byte(int(tape[dp]+byte({n})) & 255)")
        elif op == '-': e(f"tape[dp] = byte(int(tape[dp]-byte({n})) & 255)")
        elif op == '.':
            e("out.WriteByte(tape[dp])") if n == 1 else e(f"for i:=0; i<{n}; i++ {{ out.WriteByte(tape[dp]) }}")
        elif op == ',' and has_in:
            e("tape[dp] = getchar()") if n == 1 else e(f"for i:=0; i<{n}; i++ {{ tape[dp] = getchar() }}")
        elif op == 'CLR': e("tape[dp] = 0")
        elif op == '[': e("for tape[dp] != 0 {"); ind += 1
        elif op == ']': ind = max(1, ind - 1); e("}")
    w("}")
    w("")
    return "\n".join(L)

def emit_cpp(tokens) -> str:
    has_in = any(op == ',' for op, _ in tokens)
    L = []; w = L.append
    w("#include <iostream>")
    w("int main(){")
    w("    static unsigned char tape[300000] = {0};")
    w("    size_t dp = 0;")
    w("    std::ios::sync_with_stdio(false); std::cin.tie(nullptr);")
    ind = 1
    def e(s): L.append(('    '*ind)+s)
    for op, n in tokens:
        if   op == '>': e(f"dp += {n};")
        elif op == '<': e(f"dp -= {n};")
        elif op == '+': e(f"tape[dp] = (tape[dp] + {n}) & 255;")
        elif op == '-': e(f"tape[dp] = (tape[dp] - {n}) & 255;")
        elif op == '.':
            e("std::cout.put((char)tape[dp]);") if n == 1 else e(f"for(int i=0;i<{n};++i) std::cout.put((char)tape[dp]);")
        elif op == ',' and has_in:
            if n == 1:
                e("int c = std::cin.get(); tape[dp] = (c==EOF?0:(unsigned char)c);")
            else:
                e(f"for(int i=0;i<{n};++i){{ int c=std::cin.get(); tape[dp]=(c==EOF?0:(unsigned char)c); }}")
        elif op == 'CLR': e("tape[dp] = 0;")
        elif op == '[': e("while(tape[dp] != 0){"); ind += 1
        elif op == ']': ind = max(1, ind - 1); e("}")
    e("return 0;")
    w("}")
    w("")
    return "\n".join(L)

def emit_csharp(tokens) -> str:
    has_in = any(op == ',' for op, _ in tokens)
    L = []; w = L.append
    w("using System;")
    w("using System.IO;")
    w("class Program { static void Main(){")
    w("    byte[] tape = new byte[300000]; int dp = 0;")
    if has_in: w("    Stream input = Console.OpenStandardInput();")
    w("    var stdout = Console.OpenStandardOutput();")
    ind = 1
    def e(s): L.append(('    '*ind)+s)
    for op, n in tokens:
        if   op == '>': e(f"dp += {n};")
        elif op == '<': e(f"dp -= {n};")
        elif op == '+': e(f"tape[dp] = (byte)((tape[dp] + {n}) & 255);")
        elif op == '-': e(f"tape[dp] = (byte)((tape[dp] - {n}) & 255);")
        elif op == '.':
            if n == 1: e("stdout.WriteByte(tape[dp]);")
            else: e(f"for (int i=0;i<{n};i++) stdout.WriteByte(tape[dp]);")
        elif op == ',' and has_in:
            if n == 1:
                e("int c = input.ReadByte(); tape[dp] = (byte)(c==-1?0:c);")
            else:
                e(f"for (int i=0;i<{n};i++) {{ int c = input.ReadByte(); tape[dp] = (byte)(c==-1?0:c); }}")
        elif op == 'CLR': e("tape[dp] = 0;")
        elif op == '[': e("while (tape[dp] != 0) {"); ind += 1
        elif op == ']': ind = max(1, ind - 1); e("}")
    w("}}")
    w("")
    return "\n".join(L)

def emit_lua(tokens) -> str:
    has_in = any(op == ',' for op, _ in tokens)
    L = []; w = L.append
    w("local tape = {} for i=1,300000 do tape[i]=0 end")
    w("local dp = 1")
    if has_in:
        w("local function getchar() local c=io.read(1); if c==nil then return 0 else return string.byte(c) end end")
    else:
        w("local function getchar() return 0 end")
    ind = 0
    def e(s): L.append(('    '*ind)+s)
    for op, n in tokens:
        if   op == '>': e(f"dp = dp + {n}")
        elif op == '<': e(f"dp = dp - {n}")
        elif op == '+': e(f"tape[dp] = (tape[dp] + {n}) % 256")
        elif op == '-': e(f"tape[dp] = (tape[dp] - {n}) % 256")
        elif op == '.':
            if n == 1: e("io.write(string.char(tape[dp]))")
            else: e(f"for i=1,{n} do io.write(string.char(tape[dp])) end")
        elif op == ',':
            if n == 1: e("tape[dp] = getchar()")
            else: e(f"for i=1,{n} do tape[dp] = getchar() end")
        elif op == 'CLR': e("tape[dp] = 0")
        elif op == '[': e("while tape[dp] ~= 0 do"); ind += 1
        elif op == ']': ind = max(0, ind - 1); e("end")
    w("")
    return "\n".join(L)

def emit_ruby(tokens) -> str:
    has_in = any(op == ',' for op, _ in tokens)
    L = []; w = L.append
    w("tape = Array.new(300000, 0)"); w("dp = 0")
    if has_in: w("def getchar; c=$stdin.read(1); c ? c.ord : 0; end")
    else: w("def getchar; 0; end")
    ind = 0
    def e(s): L.append(('    '*ind)+s)
    for op, n in tokens:
        if   op == '>': e(f"dp += {n}")
        elif op == '<': e(f"dp -= {n}")
        elif op == '+': e(f"tape[dp] = (tape[dp] + {n}) & 0xFF")
        elif op == '-': e(f"tape[dp] = (tape[dp] - {n}) & 0xFF")
        elif op == '.':
            if n == 1: e("STDOUT.write(tape[dp].chr)")
            else: e(f"{n}.times {{ STDOUT.write(tape[dp].chr) }}")
        elif op == ',':
            if n == 1: e("tape[dp] = getchar")
            else: e(f"{n}.times {{ tape[dp] = getchar }}")
        elif op == 'CLR': e("tape[dp] = 0")
        elif op == '[': e("while tape[dp] != 0"); ind += 1
        elif op == ']': ind = max(0, ind - 1); e("end")
    w("")
    return "\n".join(L)

def emit_rust(tokens) -> str:
    has_in = any(op == ',' for op, _ in tokens)
    L = []; w = L.append
    w("use std::io::{self, Read, Write};")
    w("fn main(){")
    w("    let mut tape = [0u8; 300000];")
    w("    let mut dp: usize = 0;")
    w("    let mut out = io::BufWriter::new(io::stdout());")
    if has_in:
        w("    let mut stdin = io::stdin();")
        w("    let mut buf = [0u8; 1];")
        w("    let mut getchar = || -> u8 { match stdin.read(&mut buf) { Ok(1) => buf[0], _ => 0 } };")
    ind = 1
    def e(s): L.append(('    '*ind)+s)
    for op, n in tokens:
        if   op == '>': e(f"dp += {n};")
        elif op == '<': e(f"dp -= {n};")
        elif op == '+': e(f"tape[dp] = tape[dp].wrapping_add({n});")
        elif op == '-': e(f"tape[dp] = tape[dp].wrapping_sub({n});")
        elif op == '.':
            if n == 1: e("out.write_all(&[tape[dp]]).unwrap();")
            else: e(f"for _ in 0..{n} {{ out.write_all(&[tape[dp]]).unwrap(); }}")
        elif op == ',' and has_in:
            if n == 1: e("tape[dp] = getchar();")
            else: e(f"for _ in 0..{n} {{ tape[dp] = getchar(); }}")
        elif op == 'CLR': e("tape[dp] = 0;")
        elif op == '[': e("while tape[dp] != 0 {"); ind += 1
        elif op == ']': ind = max(1, ind - 1); e("}")
    e("out.flush().unwrap();")
    w("}")
    w("")
    return "\n".join(L)

# ---- Target registry ----
TARGETS = {
    "1": ("python", ".py",  emit_python, ["python", "{out}"]),
    "2": ("go",     ".go",  emit_go,     ["go", "run", "{out}"]),
    "3": ("cpp",   ".cpp",  emit_cpp,    None),
    "4": ("csharp",".cs",   emit_csharp, None),
    "5": ("lua",   ".lua",  emit_lua,    None),
    "6": ("ruby",   ".rb",  emit_ruby,   None),
    "7": ("rust",   ".rs",  emit_rust,   None),
    "0": ("all",    "",     None,        None),
}

# ---------- UI ----------
def pick_target() -> str:
    print("Pick target:\n"
          "  [1] Python\n  [2] Go\n  [3] C++\n  [4] C#\n"
          "  [5] Lua\n  [6] Ruby\n  [7] Rust\n  [0] ALL")
    while True:
        c = input("> ").strip()
        if c in TARGETS: return c
        print("Enter 0-7")

def pick_bf_path() -> str:
    tk.Tk().withdraw()
    p = filedialog.askopenfilename(title="Select a Brainfuck (.bf) file",
                                   filetypes=[("Brainfuck","*.bf"), ("All files","*.*")])
    if not p:
        print("No file selected."); sys.exit(1)
    return p

def write_out(code: str, base: str, ext: str) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, f"{base}{ext}")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    return out_path

def try_run(cmd_tpl: list[str], out_path: str):
    if not cmd_tpl: return
    cmd = [(out_path if x == "{out}" else x) for x in cmd_tpl]
    try:
        print("[run] -------- output --------")
        subprocess.check_call(cmd)
    except FileNotFoundError as e:
        print(f"[warn] can't auto-run: {e}")
    except subprocess.CalledProcessError as e:
        print(f"[err] program exited with {e.returncode}")

# ---------- main ----------
def main():
    choice = pick_target()
    bf_path = pick_bf_path()
    src = open(bf_path, "r", encoding="utf-8").read()
    toks = desugar(fold_runs(sanitize(src)))
    base = os.path.splitext(os.path.basename(bf_path))[0]

    def emit_one(key):
        name, ext, emitter, runner = TARGETS[key]
        if key == "0": return
        code = emitter(toks)
        suffix = {
            "python":"_py","go":"_go","cpp":"_cpp","csharp":"_cs",
            "lua":"_lua","ruby":"_rb","rust":"_rs"
        }[name]
        out_path = write_out(code, f"{base}{suffix}", ext)
        print(f"[ok] wrote {out_path}")
        if runner: try_run(runner, out_path)

    if choice == "0":
        for k in [k for k in TARGETS if k != "0"]:
            emit_one(k)
    else:
        emit_one(choice)

if __name__ == "__main__":
    main()
