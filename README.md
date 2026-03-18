# clangd-cli

CLI wrapper around clangd's LSP capabilities.

## Install

```bash
git clone https://github.com/aRaikoFunakami/clangd-cli.git
cd clangd-cli
uv tool install -e .
```

## Prerequisites

clangd-cli requires `compile_commands.json` in your project. Generate it for your build system:

```bash
# CMake
cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
# → creates build/compile_commands.json

# Make (using Bear)
bear -- make
# → creates compile_commands.json

# Meson
meson setup build
# → creates build/compile_commands.json
```

clangd-cli auto-detects `compile_commands.json` in the project root, `build/`, `out/Default/`, `out/Release/`, `out/Debug/`, or `.build/`. For other locations, use `--compile-commands-dir`:

```bash
clangd-cli --project-root /path/to/project --compile-commands-dir /path/to/dir start
```

## Usage

```bash
# Start daemon (fast - clangd stays running)
clangd-cli --project-root /path/to/project start
clangd-cli --project-root /path/to/project hover --file /path/to/file.cpp --line 10 --col 5
clangd-cli --project-root /path/to/project stop

# One-shot mode (no setup needed)
clangd-cli --oneshot hover --file /path/to/file.cpp --line 10 --col 5
```

All `--line` / `--col` values are 0-indexed (matching LSP protocol).

## Configuration (.clangd-cli.json)

プロジェクトルートに `.clangd-cli.json` を配置すると、CLI 引数のデフォルト値を設定できます。
`clangd-cli install` を実行するとサンプルが生成されます。

```json
{
  "compile_commands_dir": ".",
  "index_file": "index.idx",
  "clangd_path": "clangd",
  "timeout": 30,
  "background_index": true
}
```

全フィールド任意です。指定しなければ自動検出またはデフォルト値が使われます。

### フィールド一覧

| フィールド | 型 | デフォルト | 説明 |
|-----------|------|----------|------|
| `compile_commands_dir` | string | 自動検出 | `compile_commands.json` が存在するディレクトリ |
| `index_file` | string | 自動検出 | 事前ビルド済みインデックスファイル (.idx) のパス |
| `clangd_path` | string | `"clangd"` | clangd バイナリのパス |
| `timeout` | number | `30` | LSP リクエストのタイムアウト（秒） |
| `background_index` | bool | `true` | バックグラウンドインデックスの有効/無効 |

### パス解決ルール

- **相対パス**: project-root を基準に解決されます
  - `"index_file": "index.idx"` → `<project-root>/index.idx`
  - `"compile_commands_dir": "build"` → `<project-root>/build`
- **絶対パス**: そのまま使用されます
  - `"index_file": "/opt/data/index.idx"` → `/opt/data/index.idx`

### 優先順位

```
CLI 引数 (--index-file, --compile-commands-dir 等)
  ↓ 未指定なら
.clangd-cli.json の値
  ↓ 未指定なら
自動検出
```

### 自動検出

| 対象 | 検索パス（優先順） |
|------|------------------|
| `compile_commands.json` | `.`, `build/`, `out/Default/`, `out/Release/`, `out/Debug/`, `.build/` |
| index file (.idx) | `index.idx`, `.clangd.idx`, `clangd.idx`, `.cache/clangd/index.idx`, `build/index.idx` |

index ファイルが見つからない場合、`start` コマンドのレスポンスに `hint` フィールドが含まれます。

## グローバルオプション

| オプション | デフォルト | 説明 |
|-----------|----------|------|
| `--project-root <dir>` | `.` (cwd) | プロジェクトルートディレクトリ |
| `--compile-commands-dir <dir>` | 自動検出 | `compile_commands.json` があるディレクトリ |
| `--index-file <path>` | 自動検出 | clangd インデックスファイル (.idx) のパス |
| `--clangd-path <path>` | `clangd` | clangd バイナリのパス |
| `--timeout <sec>` | `30` | LSP リクエストタイムアウト（秒） |
| `--oneshot` | — | デーモンなしで実行（コマンドごとに clangd を起動） |

## コマンド一覧

### デーモン管理

| コマンド | 説明 |
|---------|------|
| `start` | clangd デーモンをバックグラウンドで起動。レスポンスに `hint` があればインデックス未検出 |
| `stop` | デーモンを停止 |
| `status` | デーモンの稼働状態を確認 |

```bash
clangd-cli --project-root /path/to/project start
clangd-cli --project-root /path/to/project status
clangd-cli --project-root /path/to/project stop
```

### 複合コマンド（まずこれを使う）

| コマンド | 引数 | 説明 |
|---------|------|------|
| `impact-analysis` | `--file --line --col` | 再帰的な呼び出し元トレース (BFS)。ラムダ内の呼び出しも検出 |
| | `--max-depth N` | BFS の最大深度（デフォルト: 5） |
| | `--max-nodes N` | 探索ノード数の上限（デフォルト: 100） |
| | `--include-virtual` | 仮想ディスパッチ先も型階層経由で探索 |
| | `--no-callees` | ルートからの呼び出し先 (callees) をスキップ |
| `describe` | `--file --line --col` | シンボル概要: 型情報 + 定義 + 参照 + 呼び出し元 + 呼び出し先 |
| | `--no-callers` | 呼び出し元をスキップ |
| | `--no-callees` | 呼び出し先をスキップ |

```bash
# 関数の影響範囲を調査
clangd-cli --project-root . impact-analysis --file src/main.cpp --line 10 --col 5 --max-depth 3

# シンボルの全体像を把握
clangd-cli --project-root . describe --file src/main.cpp --line 10 --col 5
```

### ナビゲーション

| コマンド | 引数 | 説明 |
|---------|------|------|
| `goto-definition` | `--file --line --col` | シンボルの定義へジャンプ |
| `goto-declaration` | `--file --line --col` | シンボルの宣言へジャンプ |
| `goto-type-definition` | `--file --line --col` | シンボルの型定義へジャンプ（`auto` 変数に便利） |
| `goto-implementation` | `--file --line --col` | 仮想メソッドのオーバーライド先を検索 |
| `find-references` | `--file --line --col` | シンボルの全参照を検索（テキストマッチではなく意味的） |
| | `--no-declaration` | 宣言を結果から除外 |
| `switch-header-source` | `--file` | ヘッダ ↔ ソースファイルを切り替え (.h ↔ .cpp) |

```bash
clangd-cli --project-root . goto-definition --file src/main.cpp --line 10 --col 5
clangd-cli --project-root . find-references --file src/main.cpp --line 10 --col 5 --no-declaration
clangd-cli --project-root . switch-header-source --file src/main.cpp
```

### シンボル検索

| コマンド | 引数 | 説明 |
|---------|------|------|
| `workspace-symbols` | `--query <name>` | ワークスペース全体からシンボルを名前で検索。ファイル/行/列が不明な時に最初に使う |
| | `--limit N` | 結果数の上限（デフォルト: 100） |
| `file-symbols` | `--file` | ファイル内のシンボル一覧（階層的） |

```bash
# シンボルの位置を特定（grep の代わりに）
clangd-cli --project-root . workspace-symbols --query OnThemeChanged

# ファイル内のシンボル構造を確認
clangd-cli --project-root . file-symbols --file src/main.cpp
```

### コード理解

| コマンド | 引数 | 説明 |
|---------|------|------|
| `hover` | `--file --line --col` | 型シグネチャ、auto 推論型、ドキュメントを表示 |
| `ast` | `--file --line --col` | 指定位置の AST 構造を表示 |
| | `--depth N` | AST 子ノードの最大深度 |
| `diagnostics` | `--file` | コンパイルエラー・警告を表示 |
| `inlay-hints` | `--file` | パラメータ名、推論型などのインレイヒントを表示 |
| | `--range START:END` | 行範囲を指定（0-indexed） |
| `semantic-tokens` | `--file` | トークンの型・修飾子情報を表示 |
| | `--range START:END` | 行範囲を指定（0-indexed） |

```bash
clangd-cli --project-root . hover --file src/main.cpp --line 10 --col 5
clangd-cli --project-root . diagnostics --file src/main.cpp
clangd-cli --project-root . inlay-hints --file src/main.cpp --range 0:50
```

### 階層解析

| コマンド | 引数 | 説明 |
|---------|------|------|
| `call-hierarchy-in` | `--file --line --col` | 直接の呼び出し元（1 階層のみ）。ラムダ内は検出不可 → `impact-analysis` を使用 |
| `call-hierarchy-out` | `--file --line --col` | 直接の呼び出し先（1 階層のみ） |
| `type-hierarchy-super` | `--file --line --col` | 基底クラス一覧 |
| `type-hierarchy-sub` | `--file --line --col` | 派生クラス一覧 |

```bash
clangd-cli --project-root . call-hierarchy-in --file src/main.cpp --line 10 --col 5
clangd-cli --project-root . type-hierarchy-sub --file src/main.cpp --line 20 --col 8
```

### 構造情報

| コマンド | 引数 | 説明 |
|---------|------|------|
| `highlight-symbol` | `--file --line --col` | ドキュメント内のシンボル出現箇所（Read/Write/Text 種別付き） |
| `document-links` | `--file` | `#include` の解決先パス一覧 |

### セットアップ

| コマンド | 引数 | 説明 |
|---------|------|------|
| `install` | | Claude Code / GitHub Copilot の指示ファイルを生成 |
| | `-y, --yes` | 確認プロンプトをスキップ（非対話モード） |

```bash
clangd-cli --project-root /path/to/project install
clangd-cli --project-root /path/to/project install -y
```

## 既知の制限事項

- `call-hierarchy-in` はラムダ内からの呼び出しを検出できません。代わりに `impact-analysis` を使用してください（未カバーの参照を自動検出します）。
- 仮想ディスパッチ: `impact-analysis --include-virtual` または `type-hierarchy-sub` を使用してください。

## Documentation

- [compile_commands.json 技術資料](docs/compile_commands_json_guide.md)
