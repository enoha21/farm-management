# 農場管理アプリ — Claude Code 引き継ぎドキュメント

## プロジェクト概要

バニラJS + Tailwind CSS（CDN）のシングルファイル HTML 農場管理アプリ。
サーバー不要、ブラウザで直接開くだけで動作する。

**メインファイル**: `farm-management-complete.html`（約1261行）

---

## アーキテクチャ

### 基本方針
- `appState` オブジェクトで全状態管理
- `render()` 関数が DOM を毎回全再構築（仮想DOMなし）
- `localStorage` で自動保存・自動ロード
- テンプレートリテラル（`` ` ` ``）を `html +=` ブロック内で使用
- 独立したレンダー関数（`renderCropSegments`, `renderPlanMap`, `renderPlanGantt`）内では文字列連結を使用（テンプレートリテラルのネスト問題を回避）

### データ構造

```javascript
// 圃場定義
const FIELDS = [
  {id:1, name:"圃場1", loc:"北側"},
  {id:2, name:"圃場2", loc:"南側"},
];

// 畝定義（各圃場6畝、東=1〜西=6）
const RIDGES = [
  {id:"F1R1", field:1, no:1}, ... {id:"F1R6", field:1, no:6},
  {id:"F2R1", field:2, no:1}, ... {id:"F2R6", field:2, no:6},
];

// 作物科目データベース
const CROP_FAMILIES = {
  "ナス科":    { minYears:3, color:"#7c3aed", crops:["トマト","ナス","ピーマン","ジャガイモ"] },
  "アブラナ科": { minYears:2, color:"#2563eb", crops:["キャベツ","ブロッコリー","大根","ダイコン","白菜","ハクサイ","小松菜","コマツナ"] },
  // ... 他の科目
};

// appState
let appState = {
  tab: 'map',           // 'map' | 'input' | 'history' | 'plan' | 'rotation' | 'dashboard'
  plantings: [],        // 作付け実績データ
  showForm: false,
  editId: null,
  form: {
    ridgeId:'F1R1', cropName:'', cropFamily:'その他',
    variety:'', count:'',          // 品種・株数
    from:0, to:100,                // 畝内区間（北=0% 南=100%）
    plantDate:'', harvestDate:'',
    year:2026, season:'春夏',
    status:'active',               // 'planned' | 'active' | 'completed'
    notes:''
  },
  planYear: 2026,
  plans: [],            // 作付け計画データ
  showPlanForm: false, planEditId: null,
  planForm: {ridgeId:'F1R1', cropName:'', cropFamily:'その他', from:0, to:100, startMonth:'', endMonth:'', notes:''},
  planView: 'gantt',    // 'gantt' | 'map' | 'list'
  planMapMonth: 4,      // 0=全期間, 1〜12=月フィルター
  planListSort: 'ridge' // 'ridge' | 'time'
};
```

### plantings データ構造
```javascript
{
  id: "p" + Date.now(),
  ridgeId: "F1R1",
  cropName: "トマト",
  cropFamily: "ナス科",
  variety: "桃太郎",      // 品種（任意）
  count: "20",            // 株数（任意）
  from: 0, to: 60,        // 畝内区間 %
  plantDate: "2026-04-01",
  harvestDate: "2026-07-31",
  year: 2026,
  season: "春夏",
  status: "active",       // 'planned' | 'active' | 'completed'
  notes: "メモ自由記入"
}
```

### plans データ構造
```javascript
{
  id: "pl" + Date.now(),
  ridgeId: "F1R1",
  cropName: "キャベツ",
  cropFamily: "アブラナ科",
  from: 0, to: 100,
  startMonth: "2026-09",  // YYYY-MM 形式
  endMonth: "2026-11",
  notes: ""
}
```

---

## タブ構成

| tab値 | 表示名 | 内容 |
|-------|--------|------|
| `map` | 圃場マップ | 圃場の視覚的マップ、畝ごとに栽培中作物を表示。空き畝サマリー付き |
| `input` | 作付け入力 | 新規登録フォーム＋一覧（圃場・畝別グループ表示） |
| `history` | 作付け履歴 | 全plantings履歴、年度フィルター付き、畝別グループ、編集・削除ボタン付き |
| `plan` | 作付け計画 | ガントチャート / マップ / 一覧の3ビュー。「🌱 実績へ」変換ボタン付き |
| `warnings` | 連作警告 | 連作障害の警告 + 収穫予定日超過アラート |
| `guide` | 輪作ガイド | 作物科目別輪作基準・畝別作付け履歴 |
| `data` | データ管理 | JSON保存・読み込み（マージ方式）、統計サマリー |

---

## 主要関数

### `render()`
全DOM再構築。`html` 文字列を組み立てて `document.getElementById('app').innerHTML = html` で反映。

### `renderCropSegments(crops)`
混植対応レンダラー。複数作物が同一畝の同区間に重なる場合、横に均等分割して表示。
- 既存作付け（`_isExisting:true`）: 白背景＋色付き左ボーダー
- 計画（通常）: 科目カラーの塗りつぶし

### `renderPlanMap(year, filterMonth)`
作付け計画の圃場マップ。`filterMonth`（0=全期間, 1〜12）でその月に有効な作物のみ表示。
- `isActiveInMonth()` で期間判定

### `renderPlanGantt(year)`
畝×月のガントチャート。畝ごとに交互背景色（6色パレット）。

### `saveData()`
フォームバリデーション後、`appState.plantings` に追加 or 更新。`autoSave()` → `render()`。

### `exportJSON()`（async）
`window.showSaveFilePicker()` API でOS保存ダイアログ（Google Driveも指定可）。非対応ブラウザはダウンロードフォールバック。

### `importJSON()`
JSONファイル読み込み、既存データとマージ（id重複スキップ）。

---

## CSS クラス
```css
.label  /* フォームラベル: text-sm font-bold text-gray-700 mb-1 block */
.input  /* フォーム入力: border rounded px-3 py-2 w-full */
.btn    /* ボタン基底 */
.btn-green, .btn-gray  /* ボタンバリアント */
.no-print   /* 印刷時非表示 */
.print-only /* 印刷時のみ表示 */
```

---

## 既知の仕様・注意点

1. **作物名入力でrender()を呼ばない**: `oninput` でカーソルが飛ぶ問題があるため、`onchange` を使用
2. **テンプレートリテラルのネスト**: 独立関数（`renderCropSegments`等）では文字列連結を使う
3. **JS構文チェック方法**: 編集後に必ず以下を実行
   ```bash
   node -e "const fs=require('fs'),html=fs.readFileSync('farm-management-complete.html','utf8'),m=html.match(/<script>([\s\S]*?)<\/script>/);try{new Function(m[1]);console.log('OK')}catch(e){console.error(e.message)}"
   ```
4. **輪作警告**: 同じ畝・同じ科目の作物で、エリア重複かつ期間重複の場合のみ警告
5. **混植判定**: マップビューで同月フィルター時に同位置に複数作物 = 真の混植

---

## 今後の改善候補（未実装）

- 作付け計画から作付け実績への自動変換機能
- 印刷レイアウトの改善
- 圃場・畝の追加・削除機能（現在は固定2圃場×6畝）
- 作業日誌機能（施肥・農薬記録）
- 収量記録機能
