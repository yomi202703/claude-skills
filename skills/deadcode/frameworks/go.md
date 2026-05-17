# Go

## LENSES

All lenses output schema: `[{file, line, name, kind, lens, safety}]`.

### L1 — deadcode (safety: 3)

```
deadcode -test -json ./... \
  | jq '[.[] | {file: (.position | split(":")[0]), line: (.position | split(":")[1] | tonumber), name: .name, kind: "func", lens: "deadcode", safety: 3}]'
```

Monorepo (`go.work`): `deadmono ./...` with the same jq filter.

### L3 — unreachable & vet (safety: 1)

```
go vet ./... 2>&1 \
  | rg '^(\S+):(\d+):\d+: (unreachable|.*never used)' \
  | awk -F: '{printf "{\"file\":\"%s\",\"line\":%s,\"name\":\"vet\",\"kind\":\"branch\",\"lens\":\"vet\",\"safety\":1}\n", $1, $2}' \
  | jq -s '.'
```

## TEST_CMD

`go test ./...`
Build check: `go vet ./...` + `go build ./...`

## FRAMEWORK_HOOKS (skip — treated as live)

### Language conventions

- `func main()` (entry)
- `func init()` (auto-run on package init)
- `func TestXxx(t *testing.T)` / `func BenchmarkXxx` / `func ExampleXxx` (testing package)
- `MarshalJSON` / `UnmarshalJSON` / `MarshalText` / `UnmarshalText` / `MarshalBinary` / `UnmarshalBinary`
- `String()` (fmt.Stringer)
- `Error()` (error interface)
- `Read` / `Write` / `Close` (io interfaces)
- `ServeHTTP` (http.Handler)

### Web frameworks

- net/http: handler arg of `http.HandleFunc("/path", handler)`
- gin: handler arg of `r.GET("/path", handler)`
- echo: handler arg of `e.GET("/path", handler)`
- chi: handler arg of `r.Get("/path", handler)`

### Exported (public) identifiers

- Capitalized names (`Foo`, `Bar`) are external API
- Library repos (module path is `github.com/<user>/<repo>`, not under `internal/`): keep exported names conservatively

### Special comments

- `//go:linkname` / `//go:noinline` / `//go:nosplit` and other pragmas
- `//export` (cgo)

## ENTRYPOINTS

- `cmd/<name>/main.go`
- For library modules, treat all exported API as entry
