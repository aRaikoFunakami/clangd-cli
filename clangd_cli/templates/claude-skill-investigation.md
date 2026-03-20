# Structured Impact Investigation Workflow (影響範囲調査)

## Scope

- **対象**: 区分A（コード依存の影響分析）＋ 区分B（C++言語固有の影響分析）
- **対象外**: 区分C（コード外の影響分析）、報告書項目7（再テスト対象）
- 本ワークフローは `docs/impact_analysis_guide.md` 第5版に基づく

## 並列実行の原則

clangd-cli はデーモン型アーキテクチャのため、独立したコマンドは並列に発行できる。各 STEP 内・STEP 間を問わず、データ依存がないコマンドは積極的に並列実行して調査時間を短縮すること。

## Workflow: STEP と clangd-cli コマンドのマッピング

| STEP | 概要 | 主な手段 |
|------|------|---------|
| STEP 0 | 変更の種類を分類 | コード読解のみ（コマンド不要） |
| STEP 1 | 修正起点＋契約確認 | `workspace-symbols`, `hover`, `describe` |
| STEP 2 | データ収集＋ファイル保存 | `investigate`（推奨）、`find-references`, `impact-analysis --only callers`, `goto-implementation`（virtual時） |
| STEP 3 | データ依存追跡（前方スライス） | **Readツール + jq抽出中心**、補助: `find-references`（メンバ変数追跡）、`hover`（型確認） |
| STEP 4 | 制御依存追跡 | コード読解中心、`hover` で型確認 |
| STEP 5 | 関数境界の漏洩チェック | **Readツール中心**、補助: `find-references`（漏洩先の参照追跡） |
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

### STEP 2: データ収集＋ファイル保存

`investigate` で全データを一括取得し、ファイルに保存する。以降のSTEPではこのファイルから `jq` で必要なデータを抽出する。

```bash
# 全データを一括取得してファイルに保存
clangd-cli investigate --file F --line L --col C > investigation-data.json

# 規模を確認
jq '.stats' investigation-data.json
jq '.callers | length' investigation-data.json
jq '[.callers[] | select(.depth == 1)] | length' investigation-data.json
```

`investigate` が使えない場合の代替：
```bash
# 個別コマンドで段階的に取得
clangd-cli impact-analysis --file F --line L --col C --only callers
clangd-cli find-references --file F --line L --col C
clangd-cli goto-implementation --file F --line L --col C  # virtualメソッドの場合
```

確認事項：
- 直接呼び出し箇所の完全な一覧（`callers` で `depth == 1` のもの）
- 仮想関数の場合、基底クラスのポインタ/参照経由の呼び出し（`virtual_dispatch.dispatch_callers`）
- 派生クラスでの同名overrideの有無（`virtual_dispatch.sibling_overrides`）
- テンプレートのインスタンス化箇所
- 演算子オーバーロード経由の暗黙呼び出し
- コールバック/observer/signal-slot経由の間接呼び出し
- `uncovered_references`（callerとして捕捉されなかった参照）の確認

### STEP 3: データ依存追跡（前方スライス）

#### 原則

前方スライス追跡は構造的・機械的な作業である。clangdは関数内のデータフローを公開していないため、**LLMがソースコードをReadツールで読んでuse-defチェーンを追跡する**必要がある。

#### 処理戦略 — caller数に応じた分岐

まず depth=1 のcaller数を確認する：

```bash
jq '[.callers[] | select(.depth == 1)] | length' investigation-data.json
```

| depth=1のcaller数 | 処理方法 |
|-------------------|---------|
| 1-5件 | 逐次処理（メインコンテキストで直接処理） |
| 6-20件 | **Agent tool で並列処理**（3-5エージェント、各4-5件担当） |
| 21件以上 | **Agent tool で並列処理**（5-10エージェント） + 結果をファイルに集約 |

#### 並列処理の手順（6件以上の場合）

1. **jqでcallerをバッチに分割**:
   ```bash
   # depth=1のcaller一覧をファイルに保存
   jq '[.callers[] | select(.depth == 1)]' investigation-data.json > depth1-callers.json
   # バッチ分割（例: 5件ずつ）
   jq '.[0:5]' depth1-callers.json > batch-0.json
   jq '.[5:10]' depth1-callers.json > batch-1.json
   ```

2. **各バッチをAgentに並列投入**: 各Agentに以下を指示
   - 担当callerの位置情報（batch-N.json）
   - 修正メソッド名と汚染追跡ルール（下記「各callerに対する処理手順」）
   - 結果を調査履歴ファイル（batch-N-results.md）に出力

3. **結果を集約**: 全Agentの結果ファイルを読み、調査履歴ファイルの前方スライス追跡テーブルに統合

#### 各callerに対する処理手順（逐次・並列共通）

1. **caller情報を取得**: investigation-data.json から jq で位置情報を抽出
   ```bash
   jq '.callers[N]' investigation-data.json
   ```

2. **Readツールで関数本体を読む**: caller の `location` から関数の開始〜終了行を読む

3. **汚染伝播を追跡**（use-defチェーン）:
   - 修正メソッド呼び出しの戻り値が代入された変数を「汚染済み」としてマーク
   - 汚染済み変数を使用する文を特定し、出力変数も汚染済みに（推移的伝播）
   - 条件分岐の判定式に汚染済み変数がある場合 → 両分岐先をスライスに含む
   - 汚染済み変数と無関係な文 → スライス外

4. **結果を調査履歴ファイルに記録**: 前方スライス追跡テーブルに1行追記

#### 具体例

```cpp
int result = foo.calculate();  // result: 汚染済み
int b = result * 2;            // result使用 → b: 汚染済み
network.send(b);               // b使用 → sendの引数が汚染 → STEP 5で漏洩チェック
logger.log("done");            // result/bと無関係 → スライス外
```

#### clangdコマンドの位置づけ（補助的）

STEP 3の主な作業はReadツールによるソースコード読解である。clangdコマンドは以下の場合に補助的に使用する：
- `find-references`: 汚染済み変数がメンバ変数の場合に、他メソッドからの参照を追跡
- `hover`: 変数の型が不明な場合の型確認（auto, template等）

各検索の結果（クエリ対象、結果件数、包含/除外の判定と理由）を調査履歴ファイルに記録する。

### STEP 4: 制御依存追跡

STEP 3で基本的な制御依存（if文の条件式に汚染済み変数 → 両分岐先をスライスに含む）は既に扱っている。STEP 4ではSTEP 3で捕捉しきれない制御依存を追加で確認する。

コード読解が中心。必要に応じて：

```bash
# 型情報の確認
clangd-cli hover --file F --line L --col C
```

確認事項：
- **例外発生条件の変化**: 修正によって例外が発生/発生しなくなるケース → catch側の処理に影響
- **early return条件の変化**: ガード節の条件が修正の影響を受ける場合 → 後続コードの到達可能性が変化
- **ループ回数の変化**: ループ条件が汚染済み変数に依存する場合 → ループ本体の実行回数が変化

### STEP 5: 関数境界の漏洩チェック

STEP 3で汚染が到達した各関数について、**Readツールで関数本体を読み**、5経路それぞれについてコードから判定する。

#### 各経路の判定方法

1. **戻り値**: return文の式に汚染済み変数が含まれるか
   ```cpp
   return result;         // result が汚染済み → 漏洩
   return result > 0;     // result が汚染済み → 漏洩（値域は変わる）
   return CONSTANT;       // 汚染済み変数と無関係 → 漏洩なし
   ```

2. **メンバ変数**: `this->member = tainted;` のパターン
   → 漏洩検出時: `find-references` でそのメンバ変数の他メソッドからの参照を追跡

3. **参照/ポインタ引数**: `T&` / `T*` 引数への書き込み
   ```cpp
   void func(int& out) { out = tainted; }  // out への書き込み → 漏洩
   ```

4. **グローバル/静的変数**: `globalVar = tainted;` のパターン
   → 漏洩検出時: `find-references` でそのグローバル変数の全参照を追跡

5. **コールバック/observer**: `emit()` / `notify()` / `signal()` パターン
   → 汚染済み変数がコールバック引数に渡されていないか確認

#### 漏洩検出時の処理

漏洩が検出された場合：
- 結果を調査履歴ファイルの前方スライス追跡テーブルに記録（漏洩経路・漏洩先を明記）
- 「追跡継続要否」を「要」にし、上位callerを新たな追跡対象としてSTEP 3〜5を再帰的に繰り返す

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

### clangd検索ログ（STEP 1-2, 6）

| # | STEP | clangdコマンド | クエリ対象 | 結果件数 | 包含/除外 | 判定理由 |
|---|------|--------------|----------|---------|----------|---------|
| 1 | 2    | investigate | Foo::bar | callers:15, callees:3 | — | データ収集 |

### 前方スライス追跡（STEP 3-5）

各callerを処理するたびに1行追記する。「追跡継続要否」列で、漏洩が検出されたcallerの上位追跡をキューとして管理する。STEP 7で全行を集約して外部観測点を確定する。

| # | caller関数 | ファイル:行 | 汚染変数 | 伝播先 | 漏洩経路 | 漏洩先 | 追跡継続要否 |
|---|-----------|-----------|---------|--------|---------|--------|------------|
| 1 | processRequest | server.cpp:120 | result, adjusted | network.send(adjusted) | 経路1:戻り値 | caller of processRequest | 要 |
| 2 | handleError | error.cpp:45 | code | logger.log(code) | なし | — | 否（末端） |

### サマリ
- clangd検索の総数: N
- 前方スライスから除外した参照箇所の総数: M
- 追跡した関数の総数: X
- 漏洩が検出された関数の数: Y
- 追跡の最大深度: Z
```
