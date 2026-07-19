# 農場管理アプリ — Claude Code 引き継ぎドキュメント

## プロジェクト概要

バニラJS + Tailwind CSS（CDN）のシングルファイル HTML 農場管理アプリ。
Firebase（Google認証 + Realtime Database）でクラウド同期し、localStorage をローカルバックアップとして併用する。
GitHub Pages で公開中: https://enoha21.github.io/farm-management/farm-management-complete.html

**メインファイル**: `farm-management-complete.html`（約2,150行）

**リポジトリ**: https://github.com/enoha21/farm-management （公開リポジトリ。
`.gitignore` で家計簿xlsx・エクスポートJSON・作業ドキュメント等を除外している。
**個人情報を含むファイルを追跡対象に追加しないこと**）

---

## アーキテクチャ

### 基本方針
- `appState` オブジェクトで全状態管理
- `render()` 関数が DOM を毎回全再構築（仮想DOMなし）
- テンプレートリテラル（`` ` ` ``）を `html +=` ブロック内で使用
- 独立したレンダー関数（`renderCropSegments`, `renderPlanMap`, `renderPlanGantt`, `renderSuggestTab`, `renderMonthlyOverview`）内では文字列連結を使用（テンプレートリテラルのネスト問題を回避）

### 認証・データ保存の流れ

```
起動 → 認証確認画面 → Googleログイン
  → loadDataFromFirebase():
      1. localStorage を即時表示（loadFromLocal）
      2. Firebase users/{uid}/farmData を取得して上書き
      3. 取得成功時に cloudLoaded = true（これまでクラウド保存は禁止）
      4. ensureDailyBackup() でその日最初の状態を世代バックアップ
編集操作 → autoSave():
      1. localStorage に常に保存
      2. cloudLoaded が true の場合のみ users/{uid}/farmData を set()
```

**重要な保護機構**（削除・変更しないこと）:
- `cloudLoaded` フラグ: クラウド読込完了前の保存はローカルのみ。
  新端末（ローカル空）でログイン直後に操作しても空データでクラウドを上書きしない。
  読込失敗時・アカウント切替時は false に戻る。
- `ensureDailyBackup()`: 1日1回、`users/{uid}/backups/{YYYY-MM-DD}` に
  その日最初のデータを退避（transaction で同日上書きなし・深いコピーで退避）。
  `BACKUP_KEEP_DAYS`（30日）より古い世代は自動削除。
- `todayStr()`: 端末タイムゾーン基準の "YYYY-MM-DD"。
  **日付初期値に `toISOString().split('T')[0]` を使わないこと**（UTC基準のため
  日本では朝9時まで前日になるバグの原因。過去に全箇所を todayStr() へ置換済み）。
- Firebase セキュリティルールはコンソール側で「本人のuidのみ読み書き可」に設定済み。

### データ構造

```javascript
// 圃場定義（固定2圃場）
const FIELDS = [
  {id:1, name:"圃場1", loc:"北側"},
  {id:2, name:"圃場2", loc:"南側"},
];

// 畝定義（各圃場6畝）。表示上の畝番号 no と id の数字は逆順なので注意
const RIDGES = [ {id:"F1R1",field:1,no:6}, ... {id:"F2R6",field:2,no:1} ];

// 畝の寸法
const RIDGE_LENGTH_CM = 980;  // 9.8m
const RIDGE_WIDTH_CM  = 75;   // 0.75m

// 作物科目データベース（輪作年数・色・表記ゆれ含む作物名リスト）
const CROP_FAMILIES = { "ナス科": {minYears:3, color:"#dc2626", crops:[...]}, ... };

// 配置提案用の作物情報（条数・株間・推奨株数・収穫/保存メモ）
const CROP_INFO = { 'トマト': {family:'ナス科', height:'tall', rows:1, spacing:60, ...}, ... };
```

```javascript
// plantings（作付け実績）1件
{
  id: "p" + Date.now(),
  ridgeId: "F1R1",
  cropName: "トマト",
  cropFamily: "ナス科",
  variety: "桃太郎",      // 品種（任意）
  count: "20",            // 株数（任意）
  from: 0, to: 60,        // 畝内区間 %（北=0, 南=100）
  plantDate: "2026-04-01",
  harvestDate: "2026-07-31",
  year: 2026,             // ※植付日から自動算出（手入力不可）
  season: "春夏",
  status: "active",       // 'planned' | 'active' | 'completed' | 'failed'
  notes: ""
}

// plans（作付け計画）1件
{
  id: "pl" + Date.now(),
  ridgeId: "F1R1", cropName: "キャベツ", cropFamily: "アブラナ科",
  from: 0, to: 100,
  startMonth: "2026-09",  // YYYY-MM
  endMonth: "2026-11",
  notes: ""
}
```

### appState の主要フィールド

```javascript
{
  tab: 'map',        // 'map'|'input'|'history'|'warnings'|'plan'|'suggest'|'guide'|'data'
  plantings: [], plans: [],
  showForm, editId, form: {...},          // 実績入力フォーム
  planYear, showPlanForm, planEditId, planForm: {...},
  planView: 'gantt', // 'monthly'|'gantt'|'map'|'list'
  planMapMonth,      // 0=全期間, 1〜12=月フィルター
  planListSort,      // 'ridge'|'time'
  historyYear,       // 0=全年
  suggestTab, suggestCrops, suggestions, suggestUnplaced  // 配置提案
}
```

---

## タブ構成

| tab値 | 表示名 | 内容 |
|-------|--------|------|
| `map` | 圃場マップ | 畝ごとの栽培中作物。スマホ（幅640px未満）は横バー表示、PCは縦型マップ |
| `input` | 作付け入力 | 登録フォーム（作物名datalist・年度自動・区間/NaN検証付き）＋圃場・畝別一覧 |
| `history` | 作付け履歴 | 全履歴、年フィルター、畝別テーブル、編集・削除 |
| `warnings` | 連作警告 | 連作障害の警告一覧と推奨対策 |
| `plan` | 作付け計画 | 年間マップ／ガント／月別マップ／一覧の4ビュー。「🌱 実績へ」変換 |
| `suggest` | 配置提案 | 作物リストから輪作・日照・空きスペースを考慮した配置を自動提案 |
| `guide` | 輪作ガイド | 科目別輪作基準・畝別作付け履歴 |
| `data` | データ管理 | JSONエクスポート／インポート（マージ）、最終バックアップ日表示、統計 |

---

## 主要関数

- `render()` — 全DOM再構築。`#app` に innerHTML で反映
- `autoSave()` / `loadDataFromFirebase()` / `loadFromLocal()` — 保存・読込（上記の流れ参照）
- `ensureDailyBackup(data)` — 世代バックアップ（1日1回・30日保持）
- `todayStr()` — ローカルタイムゾーンの YYYY-MM-DD
- `saveData()` — 実績保存。検証：作物名・植付日必須、from<to、NaN補正、
  year=植付日の年を自動設定、科目「その他」は confirm で確認
- `savePlan()` / `deletePlan()` / `convertPlanToPlanting()` — 計画のCRUDと実績変換
- `calculateWarnings()` — 実績間の連作警告（同畝・同科目・輪作年数未満）
- `checkPlanRotation(plan)` — 計画の連作チェック（実績・他計画との重複）
- `getRotationStatus(ridgeId, family)` — 'ok'|'caution'|'ng'
- `generateSuggestions()` — 配置提案の本体（輪作→草丈→サイズ順に配置）
- `exportJSON()` — showSaveFilePicker 対応＋ダウンロードフォールバック。
  成功時 `markExported()` で日時記録 → データ管理タブに「最終バックアップ：○日前」
  表示（`getLastExportInfo()`、30日超で警告）
- `importJSON()` — id重複スキップのマージ方式

---

## CSS クラス

```css
.label / .input          /* フォーム部品 */
.btn / .btn-green / .btn-blue / .btn-gray
.warning-critical / .warning-alert
.no-print / .print-only  /* 印刷制御 */
```

---

## 既知の仕様・注意点

1. **作物名入力（実績フォーム）で render() は onchange で呼ぶ**: `oninput` はカーソルが飛ぶ
2. **テンプレートリテラルのネスト禁止**: 独立レンダー関数内は文字列連結
3. **JS構文チェック（編集後必ず実行）**:
   ```bash
   node -e "const fs=require('fs'),html=fs.readFileSync('farm-management-complete.html','utf8'),m=html.match(/<script>([\s\S]*?)<\/script>/);try{new Function(m[1]);console.log('OK')}catch(e){console.error(e.message)}"
   ```
4. **CROP_FAMILIES の参照は必ずガード**: `(CROP_FAMILIES[fam]&&CROP_FAMILIES[fam].color)||'#999'`
   の形にする。直接 `.color` を参照すると辞書外の科目名1件で白画面になる（修正済みバグ）
5. **resize リスナーは横幅変化時のみ再描画**: スマホのキーボード開閉（縦幅のみ変化）で
   再描画すると入力中の内容が消えるため。この条件を外さないこと
6. **起動時の render() は DOMContentLoaded の1回のみ**（末尾の直接呼び出しは削除済み）
7. **輪作警告**: 同じ畝・同じ科目で輪作年数（minYears）未満の場合に警告。
   year フィールドを使うため、year は植付日から自動算出に統一している
8. **検証方法**: ブラウザを対話的に開かず、Firebase/DOMをモックした Node
   シミュレーションで行う（過去の作業でテストハーネス構築の実績あり）

---

## 運用メモ

- commit / push はユーザーの動作確認と明示的な指示を待ってから行う
- 修正前に `D:\claude作業フォルダ\backup_YYYYMMDD` 形式でリポジトリ外バックアップを取る
- `動作確認手順書_*.md` はユーザー向けチェックリスト（gitignore対象）

## 今後の改善候補（未実装）

- 農薬使用の作業記録機能（構造化した散布記録。農薬マスタはハードコードしない方針）
- スマホの操作ボタン拡大・屋外向けコントラスト改善
- ユーザー入力のHTMLエスケープ（引用符で表示が崩れる問題）
- 印刷レイアウトの改善
- 圃場・畝の追加・削除機能（現在は固定2圃場×6畝）
- 収量記録機能
