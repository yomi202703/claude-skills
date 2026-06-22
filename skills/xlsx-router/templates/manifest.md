# Workbook: <original filename>

> 元ファイル: <absolute path>
> シート数: <N>
> 生成日: <YYYY-MM-DD>

## Sheets

| シート | 規模 (行×列 / Nマージ) | パス | 忠実性 | 出力ファイル |
|---|---|---|---|---|
| <sheet1> | 11×21 / 18マージ | html | 187/187 | `<slug1>.html` |
| <sheet2> | 60×32 / 147マージ | html (図形あり) | 232/232 | `<slug2>.html` |
| <sheet3> | 3862×11 | sqlite | — | `<slug3>.sqlite` |
| <sheet4> | 7472×3 | sqlite | — | `<slug4>.sqlite` |

## Detected relationships (heuristic)

(If none found, write `なし` explicitly. Do not omit the section.)

- `<slug3>.sqlite` と `<slug4>.sqlite` に共通カラム候補: `プランコード`
  - 推定JOIN: `SELECT * FROM <table3> JOIN <table4> USING (プランコード)`
  - 備考: heuristic — 人間確認が必要

## Notes

- 判定根拠 / 未解決事項を自由記述。
- 結合解釈で特殊な判断をした場合はここに書く（例: `sheet3` の D11:G11 は Rule 2b でD列のみに帰属させた）。
