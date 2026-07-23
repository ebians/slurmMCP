# slurmMCP

Slurmクラスタ向けの最小構成MCPサーバです。AIサービスから以下のジョブ支援機能を利用できます。

- `suggest_job_script`: Slurmジョブスクリプトのテンプレート生成
- `submit_job`: `sbatch` を使ったジョブ投入
- `job_status`: `squeue` でジョブ状態確認
- `list_queue`: キュー一覧取得
- `cancel_job`: `scancel` でジョブ停止

## 実行

```bash
# stdio（既定）
python slurm_mcp_server.py

# HTTP
python slurm_mcp_server.py --transport http --host 127.0.0.1 --port 8000
```

HTTPモードでは以下のエンドポイントを提供します。

- `POST /mcp`: JSON-RPC 2.0 のMCPリクエスト
- `GET /health`: ヘルスチェック

環境変数でも起動設定できます。

- `SLURM_MCP_TRANSPORT` (`stdio` / `http`)
- `SLURM_MCP_HOST` (例: `127.0.0.1`)
- `SLURM_MCP_PORT` (例: `8000`)

## テスト

```bash
python -m unittest -v
```

## セキュリティ注意点

- `submit_job` で `script_content` を渡した場合、投入用の一時ファイルは `mkstemp` (0600) で作成され、投入後に削除されます。
- `suggest_job_script` の `job_name` は英数字・`._-` 以外を `-` に正規化します。クラスタ側ポリシーで先頭文字制約がある場合は投入前に調整してください。