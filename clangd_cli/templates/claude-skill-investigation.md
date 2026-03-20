# Structured Impact Investigation Workflow (影響範囲調査)

## Scope

- **対象**: 区分A（コード依存の影響分析）＋ 区分B（C++言語固有の影響分析）
- **対象外**: 区分C（コード外の影響分析）、報告書項目7（再テスト対象）
- 本ワークフローは `docs/impact_analysis_guide.md` 第5版に基づく

## Workflow: STEP と clangd-cli コマンドのマッピング

| STEP | 概要 | 主な clangd-cli コマンド |
|------|------|------------------------|
| STEP 0 | 変更の種類を分類 | コード読解のみ（コマンド不要） |
| STEP 1 | 修正起点＋契約確認 | `workspace-symbols`, `hover`, `describe` |
| STEP 2 | 直接呼び出し元の洗い出し | `find-references`, `impact-analysis --only callers`, `goto-implementation`（virtual時）, `type-hierarchy-sub` |
| STEP 3 | データ依存追跡 | `describe`, `find-references`（戻り値変数の参照追跡） |
| STEP 4 | 制御依存追跡 | コード読解中心、`hover` で型確認 |
| STEP 5 | 関数境界の漏洩チェック | `describe`, `find-references` で5経路を追跡 |
| STEP 6 | C++固有の波及確認 | `goto-implementation`, `type-hierarchy-super/sub`, `find-references` |
| STEP 7 | 外部観測点の確定 | STEP 3-6の結果集約（追加コマンドは原則不要） |

### STEP 0: 変更の種類を分類

コードを読み、変更を以下のどれに該当するか記録する：

- 実装だけ変更した（外部から見た振る舞いは不変）
- 戻り値の意味を変えた
- 引数の意味を変えた
- 例外の振る舞いを変えた（noexcept含む）
- 副作用を変えた（メンバ変数、グローバル状態等）
- virtual / override / finalに関係する
- inline / constexpr / consteval / template / ヘッダ定義に関係する
- クラスレイアウトや公開API/ABIに関係する

### STEP 1: 修正起点の特定と契約確認

```bash
# シンボルの位置を特定
clangd-cli workspace-symbols --query "ClassName::MethodName"

# 型情報・契約を確認
clangd-cli hover --file F --line L --col C
clangd-cli describe --file F --line L --col C --only hover
```

記録する項目：
- 修正クラス名、メソッド名
- 修正内容の概要
- 事前条件・事後条件・不変条件の維持状況
- 戻り値の値域・意味の変化
- noexcept/例外仕様の変化

### STEP 2: 直接呼び出し元の洗い出し

```bash
# 全参照箇所を取得
clangd-cli find-references --file F --line L --col C

# callerのみ取得（大規模コードベース向け）
clangd-cli impact-analysis --file F --line L --col C --only callers

# virtualメソッドの場合：全overrideを取得
clangd-cli goto-implementation --file F --line L --col C

# 派生クラスの確認
clangd-cli type-hierarchy-sub --file F --line L --col C
```

確認事項：
- 直接呼び出し箇所の完全な一覧
- 仮想関数の場合、基底クラスのポインタ/参照経由の呼び出し
- 派生クラスでの同名overrideの有無
- テンプレートのインスタンス化箇所
- 演算子オーバーロード経由の暗黙呼び出し
- コールバック/observer/signal-slot経由の間接呼び出し

### STEP 3: データ依存追跡

各呼び出し箇所について：

```bash
# 戻り値が代入された変数の参照を追跡
clangd-cli find-references --file F --line L --col C

# 変数の型情報を確認
clangd-cli describe --file F --line L --col C --only hover
```

確認事項：
- 戻り値がどの変数に代入されているか
- その変数を使用しているすべての文（前方スライスの追跡）
- 戻り値が別関数の引数として渡されている箇所
- 条件分岐の判定に使われている場合、両方の分岐先
- 複数箇所に渡されている場合（fan-out）、すべての渡し先
- エイリアス経由で同一実体を共有している箇所

各検索の結果（クエリ対象、結果件数、包含/除外の判定と理由）を調査履歴ファイルに記録する。

### STEP 4: 制御依存追跡

コード読解が中心。必要に応じて：

```bash
# 型情報の確認
clangd-cli hover --file F --line L --col C
```

確認事項：
- 修正メソッドの影響を受ける条件分岐
- その分岐によって実行が制御されるすべての文

### STEP 5: 関数境界の漏洩チェック

影響が到達したすべての関数について、5経路を確認する：

```bash
# 関数の概要を取得
clangd-cli describe --file F --line L --col C

# メンバ変数やグローバル変数の参照を追跡
clangd-cli find-references --file F --line L --col C
```

5つの漏洩経路：
1. **戻り値**: 戻り値に修正の影響が含まれるか
2. **メンバ変数**: 影響を受けた値がメンバ変数に格納され、他メソッドから読まれるか
3. **参照/ポインタ引数**: 参照渡し・ポインタ渡しの引数に影響が書き込まれるか
4. **グローバル/静的変数**: グローバル変数・静的変数・シングルトンに書き込まれるか
5. **コールバック/observer**: コールバック・observer・signal-slot等で伝播するか

漏洩が検出された場合、その上位の呼び出し元に対してSTEP 3〜5を再帰的に繰り返す。

記録する項目：
- 追跡した関数の総数
- 漏洩が検出された関数の数
- 追跡の最大深度

### STEP 6: C++固有の波及確認

```bash
# 仮想関数のoverride一覧
clangd-cli goto-implementation --file F --line L --col C

# 型階層の確認
clangd-cli type-hierarchy-super --file F --line L --col C
clangd-cli type-hierarchy-sub --file F --line L --col C

# 基底クラスのポインタ/参照経由の参照を追跡
clangd-cli find-references --file F --line L --col C
```

確認事項：
- 仮想関数/動的ディスパッチ
- エイリアス・所有権・寿命
- template/inline/header/ODRの波及
- 例外・noexcept・契約
- ビルド・リンク・ABI

### STEP 7: 外部観測点の確定

STEP 3〜6の再帰的追跡結果を集約し、外部観測点を確定する。追加コマンドは原則不要。

確認事項：
- すべての末端が外部観測点に該当するか
- 外部観測点に到達していない追跡経路が残っていないか
- 各外部観測点の伝播経路（起点→主要な中継点→観測点）
- 各外部観測点の種類の分類
- 伝播経路上の区分B要素

外部観測点の種類：
public API戻り値 / メンバ状態 / グローバル・静的状態 / 永続化データ / ネットワーク出力 / ログ / スレッド間共有状態 / UI・CLI出力

## 報告書テンプレート（項目1-6）

```
■ 影響範囲調査報告書（区分A・B：コード依存＋C++固有）

1. 修正内容の特定
   - 修正クラス名：
   - 修正メソッド名：
   - 修正内容の概要：
   - 変更の分類（STEP 0の結果）：

2. 契約の変更確認
   | 契約項目              | 変更有無 | 変更内容（ありの場合） |
   |----------------------|---------|---------------------|
   | 事前条件              |         |                     |
   | 事後条件              |         |                     |
   | クラス不変条件         |         |                     |
   | 戻り値の値域・意味     |         |                     |
   | noexcept/例外仕様     |         |                     |

3. 調査条件
   - 参照検索ツール：clangd
   - compile_commands.jsonに基づく検索対象TU数：
   - 調査対象外：compile_commands.jsonのコンパイル条件から外れたコード

4. 影響範囲の特定結果

   4.1 直接呼び出し箇所（clangd Find All References）
   | # | ファイル:行 | 呼び出し元関数 | 戻り値の利用有無 |
   |---|------------|--------------|----------------|
   |   |            |              |                |

   4.2 C++固有の追加呼び出し箇所
   該当なしの項目は「該当なし：（確認した根拠）」と記録。

   - 仮想関数/動的ディスパッチ：
     修正メソッドはvirtual/overrideか：
     基底ポインタ/参照経由の呼び出し箇所：
     他の派生クラスでの同名override：
   - テンプレート経由のインスタンス化箇所：
   - 演算子オーバーロード経由の暗黙呼び出し：
   - コールバック/observer/signal-slot経由の間接呼び出し：
   - エイリアス（参照/ポインタ/スマートポインタ）経由の共有箇所：

   4.3 関数境界を越える漏洩の追跡
   - 追跡した関数の総数：
   - うち関数外への漏洩が検出された関数の数：
   - 追跡の最大深度（直接呼び出し元からの再帰回数）：
   - 詳細：調査履歴ファイル（項目6）参照

5. 外部観測点と伝播経路
   区分A・Bの調査により影響が到達した外部観測点の一覧。
   テスト設計・テスト選択のためのインプットとなる中核データ。
   伝播経路は起点・主要な中継点・観測点を記載し、中間関数の詳細は調査履歴ファイル（項目6）を参照。

   | # | 外部観測点 | 観測点の種類 | 伝播経路（起点→観測点） | 経路上の区分B要素 |
   |---|----------|------------|----------------------|-----------------|
   |   |          |            |                      |                 |

   観測点の種類：
   public API戻り値 / メンバ状態 / グローバル/静的状態 /
   永続化データ / ネットワーク出力 / ログ / スレッド間共有状態 / UI・CLI出力

6. 調査履歴
   - 調査履歴ファイル：（ファイルパス）
   - 調査に使用したclangd検索の総数：
   - 前方スライスから除外した参照箇所の総数：

（項目7「再テスト対象」は別スキルのスコープ）
```

## 調査履歴ファイルの仕様

- **ファイル名**: `investigation-log-YYYYMMDD-{SymbolName}.md`
- **保存先**: ユーザー指定 or プロジェクトルート配下 `docs/impact-analysis/`
- **作成方法**: Write tool でファイルを作成（allowed-tools の追加は不要）

### フォーマット

```markdown
## 調査履歴: {ClassName}::{MethodName}
調査日: YYYY-MM-DD

| # | STEP | clangdコマンド | クエリ対象 | 結果件数 | 包含/除外 | 判定理由 |
|---|------|--------------|----------|---------|----------|---------|
| 1 | 2    | find-references | Foo::bar | 5 | 包含:3, 除外:2 | ... |

### サマリ
- clangd検索の総数: N
- 前方スライスから除外した参照箇所の総数: M
```
