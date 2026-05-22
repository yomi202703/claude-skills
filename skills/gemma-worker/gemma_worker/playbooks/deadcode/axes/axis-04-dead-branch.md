# Axis 4 — Dead branch / unreachable code

You audit a single source file for **dead branches and unreachable statements within otherwise live functions**. Other axes handle module-level dead code.

## What constitutes the failure

- Code after an unconditional `return`, `raise`, `sys.exit`, `os._exit`, `assert False`, or infinite loop.
- `if False:` / `if 0:` / `if DEBUG:` blocks that are guarded by a constant the surrounding code never flips.
- `try: ... except: pass` that swallows everything and leaves the body unreachable on success path.
- `while False:` blocks.
- Imports inside an unreachable block.

## What constitutes acceptable design

- `if TYPE_CHECKING:` blocks (only run by type checkers): never flag.
- Platform guards (`if sys.platform == "win32":` on a Linux-host repo): mark `low`, treat as portability code.

## Output

```json
{"file": "<path>", "line": <int>, "symbol": "(branch)", "evidence": "<the dead line>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
