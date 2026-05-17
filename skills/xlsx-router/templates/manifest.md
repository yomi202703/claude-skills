# Workbook: <original filename>

> 元ファイル: <absolute path>
> シート数: <N>
> 生成日: <YYYY-MM-DD>

## Sheets

| シート | 形状 | 規模 (行×列 / Nマージ) | 実ヘッダ行 | パス | 出力ファイル |
|---|---|---|---|---|---|
| <sheet1> | structured | 11×21 / 18マージ | 3 | P3 YAML | `<slug1>.yaml` |
| <sheet2> | db | 18×10 | 1 | P1 Markdown | `<slug2>.md` |
| <sheet3> | db-large | 3862×11 | 1 | P2 SQLite | `<slug3>.sqlite` |
| <sheet4> | db-large | 7472×3 | 1 | P2 SQLite | `<slug4>.sqlite` |

## Detected relationships (heuristic)

(If none found, write `なし` explicitly. Do not omit the section.)

- `<slug3>.sqlite` と `<slug4>.sqlite` に共通カラム候補: `プランコード`
  - 推定JOIN: `SELECT * FROM <table3> JOIN <table4> USING (プランコード)`
  - 備考: heuristic — 人間確認が必要

## Notes

- 判定根拠 / 未解決事項を自由記述。
- 結合解釈で特殊な判断をした場合はここに書く（例: `sheet3` の D11:G11 は Rule 2b でD列のみに帰属させた）。
