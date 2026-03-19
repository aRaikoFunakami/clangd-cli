
## C++ Code Navigation

When investigating C++ symbols, **always follow this workflow**:
```
1. clangd-cli workspace-symbols --query "SymbolName"   # get exact file/line/col
2. clangd-cli impact-analysis --file F --line L --col C # trace callers/callees
3. Only if gaps remain, supplement with Grep             # text/comment search only
```
**Do NOT start with Grep** — it lacks column info, causing slow fallback resolution.
See `.claude/rules/cpp-navigation.md` for the full command reference.
