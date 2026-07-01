#!/usr/bin/env python3
"""Drive the MATLAB Editor in the user's live GUI session.

This talks to a *shared* MATLAB session over the official Engine API and uses
MATLAB's documented `matlab.desktop.editor` API to open / create / read / write
files as real editor tabs. Edits show up in the GUI editor, and reads see the
live buffer — including unsaved changes.

Scope: editor only. The Command Window scrollback cannot be driven on the
R2026a JS desktop (no CDP endpoint, no AX web tree — see _dev/decisions.md); the
editor API is the supported, GUI-reflecting surface, so that is all this does.

Commands:
  list                       list open editor docs (path + modified flag)
  open   FILE                open an existing file as an editor tab
  new    FILE [--text/--stdin]   create FILE (with content), open it, save
  read   [FILE]              print the live buffer text (active doc if no FILE)
  write  FILE (--text/--stdin)   set FILE's whole content and save
  append FILE (--text/--stdin)   append to FILE's content and save
  goto   FILE LINE           open FILE and jump the cursor to LINE
  close  FILE [--nosave]      close FILE's tab (saves first unless --nosave)

Exit: 0 ok · 2 MATLAB error · 3 no shared session · 4 usage/env error
"""
import argparse
import io
import os
import sys
import tempfile

try:
    import matlab.engine
except Exception as e:
    sys.stderr.write(
        "matlab.engine not importable here. Use scripts/.venv/bin/python.\n"
        f"detail: {e}\n")
    sys.exit(4)

SETUP_HINT = (
    "No shared MATLAB session found.\n"
    "In your running MATLAB, run this ONCE in the Command Window:\n"
    "    matlab.engine.shareEngine\n"
    "Then re-run. The share lasts the life of that MATLAB session.")


def connect():
    sessions = matlab.engine.find_matlab()
    if not sessions:
        sys.stderr.write(SETUP_HINT + "\n")
        sys.exit(3)
    return matlab.engine.connect_matlab(sessions[0])


def run(eng, code):
    """eval MATLAB code, return (stdout, error_or_None)."""
    out, err = io.StringIO(), io.StringIO()
    try:
        eng.eval(code, nargout=0, stdout=out, stderr=err)
        return out.getvalue(), None
    except matlab.engine.MatlabExecutionError as e:
        return out.getvalue(), str(e)


def get_text_arg(args):
    """Resolve --text / --stdin into a string, or None if neither given."""
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    return getattr(args, "text", None)


def stage_text(text):
    """Write text to a temp file and return its path (robust content transfer,
    avoids MATLAB string-escaping hell for multi-line/quotes)."""
    fd, path = tempfile.mkstemp(suffix=".txt", prefix="mledit_")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    return path


def m_open_or_create():
    """MATLAB snippet: get doc for path in `p`, opening/creating as needed -> d."""
    return (
        "d = matlab.desktop.editor.findOpenDocument(p);"
        "if isempty(d),"
        "  if isfile(p), d = matlab.desktop.editor.openDocument(p);"
        "  else, d = matlab.desktop.editor.newDocument(''); d.saveAs(p); end;"
        "end;")


def main():
    ap = argparse.ArgumentParser(prog="edit.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")
    p = sub.add_parser("open"); p.add_argument("file")
    p = sub.add_parser("new"); p.add_argument("file")
    p.add_argument("--text"); p.add_argument("--stdin", action="store_true")
    p = sub.add_parser("read"); p.add_argument("file", nargs="?")
    p = sub.add_parser("write"); p.add_argument("file")
    p.add_argument("--text"); p.add_argument("--stdin", action="store_true")
    p = sub.add_parser("append"); p.add_argument("file")
    p.add_argument("--text"); p.add_argument("--stdin", action="store_true")
    p = sub.add_parser("goto"); p.add_argument("file"); p.add_argument("line", type=int)
    p = sub.add_parser("close"); p.add_argument("file")
    p.add_argument("--nosave", action="store_true")
    args = ap.parse_args()

    eng = connect()

    def finish(out, err):
        if out:
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
        if err:
            sys.stderr.write(err if err.endswith("\n") else err + "\n")
            return 2
        return 0

    if args.cmd == "list":
        code = (
            "ds = matlab.desktop.editor.getAll;"
            "if isempty(ds), disp('(no open editor documents)');"
            "else, for i=1:numel(ds),"
            "  f = ds(i).Filename; if isempty(f), f='<untitled>'; end;"
            "  m = ''; if ds(i).Modified, m=' *modified'; end;"
            "  fprintf('%s%s\\n', f, m); end; end")
        return finish(*run(eng, code))

    if args.cmd == "open":
        p = os.path.abspath(args.file)
        code = f"p = '{p}';" + (
            "if ~isfile(p), error('no such file: %s', p); end;"
            "d = matlab.desktop.editor.openDocument(p); d.makeActive;"
            "fprintf('opened %s\\n', p);")
        return finish(*run(eng, code))

    if args.cmd == "new":
        text = get_text_arg(args) or ""
        tmp = stage_text(text)
        p = os.path.abspath(args.file)
        code = (
            f"p = '{p}'; tmp='{tmp}';"
            "txt = fileread(tmp);"
            "d = matlab.desktop.editor.newDocument(txt); d.saveAs(p); d.makeActive;"
            "fprintf('created %s (%d chars)\\n', p, numel(txt));")
        rc = finish(*run(eng, code))
        os.unlink(tmp)
        return rc

    if args.cmd == "read":
        if args.file:
            p = os.path.abspath(args.file)
            code = (f"p = '{p}';"
                    "d = matlab.desktop.editor.findOpenDocument(p);"
                    "if isempty(d), d = matlab.desktop.editor.openDocument(p); end;"
                    "disp(d.Text);")
        else:
            code = ("d = matlab.desktop.editor.getActive;"
                    "if isempty(d), disp('(no active editor document)');"
                    "else, disp(d.Text); end")
        return finish(*run(eng, code))

    if args.cmd in ("write", "append"):
        text = get_text_arg(args)
        if text is None:
            sys.stderr.write("provide content with --text or --stdin\n")
            return 4
        tmp = stage_text(text)
        p = os.path.abspath(args.file)
        setline = ("d.Text = txt;" if args.cmd == "write"
                   else "d.appendText(txt);")
        code = (f"p = '{p}'; tmp='{tmp}'; txt = fileread(tmp);"
                + m_open_or_create()
                + setline + "d.save; d.makeActive;"
                + f"fprintf('{args.cmd} ok: %s\\n', p);")
        rc = finish(*run(eng, code))
        os.unlink(tmp)
        return rc

    if args.cmd == "goto":
        p = os.path.abspath(args.file)
        code = (f"p = '{p}'; ln = {args.line};"
                "matlab.desktop.editor.openAndGoToLine(p, ln);"
                "fprintf('at %s:%d\\n', p, ln);")
        return finish(*run(eng, code))

    if args.cmd == "close":
        p = os.path.abspath(args.file)
        closer = "d.closeNoPrompt;" if args.nosave else "d.save; d.close;"
        code = (f"p = '{p}';"
                "d = matlab.desktop.editor.findOpenDocument(p);"
                "if isempty(d), fprintf('not open: %s\\n', p);"
                f"else, {closer} fprintf('closed %s\\n', p); end")
        return finish(*run(eng, code))

    return 4


if __name__ == "__main__":
    sys.exit(main())
