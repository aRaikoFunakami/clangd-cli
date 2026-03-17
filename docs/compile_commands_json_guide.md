# compile_commands.json 技術資料

## 1. compile_commands.json とは

**JSON Compilation Database** と呼ばれる、C/C++ プロジェクトの各翻訳単位（ソースファイル）のコンパイルコマンドを機械可読な JSON 形式で記録するファイルである。

### 1.1 仕様

Clang プロジェクトによって仕様が策定されている。

- **仕様書**: https://clang.llvm.org/docs/JSONCompilationDatabase.html

各エントリは以下のフィールドで構成される:

| フィールド | 必須 | 説明 |
|---|---|---|
| `directory` | ○ | コンパイル時の作業ディレクトリ。`command` / `arguments` 内の相対パスはこのディレクトリからの相対パス |
| `file` | ○ | コンパイル対象のソースファイル |
| `arguments` | △ | コンパイルコマンドの argv をリスト形式で記述。`command` と排他（推奨） |
| `command` | △ | コンパイルコマンドを単一の文字列として記述。`arguments` と排他 |
| `output` | × | 出力ファイル名（省略可） |

> 仕様より: "Either arguments or command is required. arguments is preferred, as shell (un)escaping is a possible source of errors."

### 1.2 フォーマット例

```json
[
  {
    "directory": "/home/user/llvm/build",
    "arguments": ["/usr/bin/clang++", "-Irelative", "-DSOMEDEF=With spaces, quotes and \\-es.", "-c", "-o", "file.o", "file.cc"],
    "file": "file.cc"
  }
]
```

（出典: https://clang.llvm.org/docs/JSONCompilationDatabase.html#format ）

### 1.3 配置場所

仕様上の慣例はプロジェクトの**ビルドディレクトリのトップ**に `compile_commands.json` という名前で配置する。

clangd はファイルの親ディレクトリを上方向に走査し、また `build/` サブディレクトリも探索する。

> clangd 公式より: "clangd will look in the parent directories of the files you edit looking for it, and also in subdirectories named build/."
>
> 出典: https://clangd.llvm.org/installation#compile_commandsjson

### 1.4 代替手段: compile_flags.txt

単純なプロジェクトでは、ソースルートに `compile_flags.txt` を配置する方法もある。1 行に 1 つのフラグを記述し、全ファイルに同じフラグが適用される。ただし**バックグラウンドインデックスが動作しない**ため、`compile_commands.json` が存在する場合はそちらが優先される。

（出典: https://clang.llvm.org/docs/JSONCompilationDatabase.html#alternatives ）

### 1.5 主な利用ツール

- **clangd** — Language Server Protocol によるコード補完・診断・ナビゲーション
- **clang-tidy** — 静的解析
- **clang-format** — コードの自動整形（一部利用）
- **IDE 統合** — VS Code (clangd 拡張)、Vim/Neovim (coc-clangd, LanguageClient 等)、Emacs (lsp-mode) 等

---

## 2. 生成方法の一覧

### 2.1 ビルドシステムのネイティブ対応

#### 2.1.1 CMake

CMake 3.5 以降で `CMAKE_EXPORT_COMPILE_COMMANDS` 変数をサポート。Makefile Generators および Ninja Generators で動作する。

```bash
cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -S . -B build
```

ビルドディレクトリに `compile_commands.json` が生成される。

> CMake 公式より: "If enabled, generates a compile_commands.json file containing the exact compiler calls for all translation units of the project in machine-readable form."
>
> "Note: This option is implemented only by Makefile Generators and Ninja Generators. It is ignored on other generators."
>
> 出典: https://cmake.org/cmake/help/latest/variable/CMAKE_EXPORT_COMPILE_COMMANDS.html

環境変数 `CMAKE_EXPORT_COMPILE_COMMANDS` でも初期化可能。

#### 2.1.2 Meson

Meson は `meson setup builddir` 実行時にビルドディレクトリ内へ `compile_commands.json` を**自動生成**する。オプション指定は不要。Ninja バックエンドを使用する（Meson のデフォルト）。

```bash
meson setup builddir
# builddir/compile_commands.json が自動生成される
```

> 注: Meson 公式ドキュメントの IDE 統合ページ（https://mesonbuild.com/IDE-integration.html ）では Meson 独自の introspection JSON ファイル群について記述されているが、compile_commands.json の自動生成は Ninja バックエンド利用時の標準動作として広く知られている。

#### 2.1.3 GN (Generate Ninja)

GN は `.gn` ファイルの `export_compile_commands` 変数、または `gn gen` コマンドの `--add-export-compile-commands` フラグで compile_commands.json を生成する。

```bash
# .gn ファイルに以下を記述
export_compile_commands = [
  "//base/*",
  "//tools:doom_melon",
]
```

```bash
# または gn gen のフラグで指定
gn gen out/Default --add-export-compile-commands="//base/*"
```

> GN リファレンスより: "When specified, GN will generate a compile_commands.json file in the root of the build directory containing information on how to compile each source file reachable from any label matching any pattern in the list."
>
> 出典: https://gn.googlesource.com/gn/+/main/docs/reference.md （".gn file" セクション、`export_compile_commands` 変数）

Chromium プロジェクトはこの方法を使用する。

#### 2.1.4 Bazel

Bazel はサードパーティの拡張を使用する。

> Clang 公式から: "Bazel can export a compilation database via this extractor extension. Bazel is otherwise resistant to Bear and other compiler-intercept techniques."
>
> 拡張: https://github.com/hedronvision/bazel-compile-commands-extractor
>
> 出典: https://clang.llvm.org/docs/JSONCompilationDatabase.html#supported-systems

#### 2.1.5 Ninja (単体)

Ninja 自体は compile_commands.json を生成する機能を**持たない**。Ninja はビルド実行エンジンであり、CMake や Meson がバックエンドとして Ninja を使用する場合はそれらのビルドシステムが生成を担当する。

#### 2.1.6 Clang の `-MJ` フラグ

Clang コンパイラ自身が `-MJ` フラグで compilation database フラグメントを出力できる。

> 仕様書より: "Clang has the ability to generate compilation database fragments via -MJ argument. You can concatenate those fragments together between [ and ] to create a compilation database."
>
> 出典: https://clang.llvm.org/docs/JSONCompilationDatabase.html#supported-systems

---

### 2.2 外部ツールによる生成

#### 2.2.1 Bear

**公式**: https://github.com/rizsotto/Bear

Bear はビルドプロセス中の実際のコンパイラ呼び出しをインターセプトして compile_commands.json を生成するツール。ビルドシステムに依存しない。

> Bear README より: "Bear is a tool that generates a compilation database for clang tooling. [...] Some build systems natively support the generation of a JSON compilation database. For projects that do not use such build tools, Bear generates the JSON file during the build process."
>
> 出典: https://github.com/rizsotto/Bear

**使用方法:**

```bash
# インストール（Ubuntu/Debian）
sudo apt install bear

# 使用（クリーンビルドが必要）
make clean
bear -- make -j$(nproc)
```

**動作原理:**

Bear はコンパイラの実行を OS レベル（`LD_PRELOAD` や `exec` のインターセプト）でフックする。そのため、あらゆるビルドシステム（Make, シェルスクリプト, カスタムビルドスクリプト等）で動作する。

**制限事項:**

- クロスコンパイル環境（リモート実行されるコンパイラはフックできない）
- 静的リンクされたビルドツール（`LD_PRELOAD` 方式が効かない場合がある）
- macOS の SIP (System Integrity Protection) — `/usr/bin/make` 等のシステムバイナリに対して `LD_PRELOAD` が効かない
- 分散ビルド（distcc 等）との相性問題

**バージョン:**

- 現在の最新は 4.0.3（2025 年 2 月リリース）
- 2.4.x 系と 3.x/4.x 系で CLI が異なる。3.x 以降は `bear -- <command>` 形式（`--` が必要）

> Bear README より: "Please be aware that some package managers still ship the 2.4.x release. In that case, please omit the extra -- or consult your local documentation."
>
> 出典: https://github.com/rizsotto/Bear

**ライセンス:** GPL-3.0

#### 2.2.2 compiledb

**公式**: https://github.com/nickdiego/compiledb

compiledb は GNU Make のドライラン出力（`make -Bnwk`）をパースして compile_commands.json を生成する Python ツール。Make ベースのプロジェクト専用。

> compiledb README より: "Tool for generating Clang's JSON Compilation Database file for GNU make-based build systems. [...] it's faster (mainly with large projects), since in most cases it doesn't need a clean build (as the mentioned tools do) to generate the compilation database file, to achieve this it uses the make options such as -n/--dry-run and -k/--keep-going to extract the compile commands."
>
> 出典: https://github.com/nickdiego/compiledb

**使用方法:**

```bash
# インストール
pip install compiledb

# Make ラッパーとして使用（ビルドも実行する）
compiledb make -j$(nproc)

# ビルドせずに compile_commands.json のみ生成
compiledb -n make

# 既存のビルドログからパース
make -Bnwk | compiledb -o-
```

**Bear との比較:**

| 項目 | Bear | compiledb |
|---|---|---|
| 対応ビルドシステム | 任意 | GNU Make のみ |
| 動作原理 | コンパイラ呼び出しのインターセプト | make -n 出力のパース |
| クリーンビルドの必要性 | 必要 | 不要（ドライランで可） |
| 正確性 | 高い（実際の呼び出しを記録） | やや劣る（パースに依存） |
| 速度 | フルビルドが必要 | ドライランのみで高速 |
| 出力形式 | `arguments` リスト形式 | デフォルト `arguments`、`--command-style` で `command` 形式も可 |

**ライセンス:** GPL-3.0

---

## 3. ビルドシステム別の推奨方法

| ビルドシステム | 推奨方法 | 備考 |
|---|---|---|
| CMake | `CMAKE_EXPORT_COMPILE_COMMANDS=ON` | ネイティブサポート。最も簡単で正確 |
| Meson | 自動生成（設定不要） | `meson setup` で自動的に生成 |
| GN | `export_compile_commands` / `--add-export-compile-commands` | Chromium 等で使用 |
| Bazel | hedronvision/bazel-compile-commands-extractor | Bear は Bazel に対して動作しない |
| GNU Make | Bear（推奨）または compiledb | Bear がより正確。compiledb はクリーンビルド不要で高速 |
| カスタムスクリプト | Bear | ビルドシステム非依存 |
| Ninja（単体） | Bear | Ninja 自体は compile_commands.json を生成しない |

---

## 4. トラブルシューティング

### 4.1 compile_commands.json が空

- Bear を使用する場合、**クリーンビルドが必要**。既にビルド済みの場合、再コンパイルが発生しないためエントリが記録されない。
- `make clean && bear -- make -j$(nproc)` を実行する。

### 4.2 clangd が compile_commands.json を見つけない

- clangd はソースファイルの親ディレクトリを上方向に走査する。プロジェクトルートまたは `build/` ディレクトリに配置する。
- ビルドディレクトリが別の場所にある場合、プロジェクトルートにシンボリックリンクを作成する:
  ```bash
  ln -s build/compile_commands.json .
  ```

### 4.3 インクルードパスが正しくない

- compiledb を使用している場合、`make -n` の出力パースが不完全な可能性がある。Bear に切り替えて実際のコンパイラ呼び出しを記録することを推奨。

---

## 5. 参考文献

すべて本資料の執筆時（2026 年 3 月）に内容を確認済み。

1. **JSON Compilation Database Format Specification** (Clang 公式)
   - https://clang.llvm.org/docs/JSONCompilationDatabase.html
   - フォーマット仕様、対応ビルドシステム一覧

2. **clangd — Getting Started — Project setup**
   - https://clangd.llvm.org/installation#compile_commandsjson
   - clangd での利用方法、各ビルドシステムの対応状況

3. **Bear — GitHub リポジトリ**
   - https://github.com/rizsotto/Bear
   - インストール方法、使用方法、制限事項

4. **compiledb — GitHub リポジトリ**
   - https://github.com/nickdiego/compiledb
   - インストール方法、使用方法、Bear との差異

5. **CMake — CMAKE_EXPORT_COMPILE_COMMANDS**
   - https://cmake.org/cmake/help/latest/variable/CMAKE_EXPORT_COMPILE_COMMANDS.html
   - CMake での compile_commands.json 生成方法

6. **GN Reference**
   - https://gn.googlesource.com/gn/+/main/docs/reference.md
   - `export_compile_commands` 変数、`--add-export-compile-commands` フラグ

7. **Meson — IDE integration**
   - https://mesonbuild.com/IDE-integration.html
   - Meson のビルドシステムインテグレーション

8. **Bazel Compile Commands Extractor**
   - https://github.com/hedronvision/bazel-compile-commands-extractor
   - Bazel 向けの compile_commands.json 生成拡張
