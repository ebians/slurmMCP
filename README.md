# slurmMCP

Slurmクラスタ向けの最小構成MCPサーバです。AIサービスから以下のジョブ支援機能を利用できます。

- `suggest_job_script`: Slurmジョブスクリプトのテンプレート生成
- `submit_job`: `sbatch` を使ったジョブ投入
- `job_status`: `squeue` でジョブ状態確認
- `list_queue`: キュー一覧取得
- `cancel_job`: `scancel` でジョブ停止

## 実行

```bash
python slurm_mcp_server.py
```

## テスト

```bash
python -m unittest -v
```

## セキュリティ注意点

- `submit_job` で `script_content` を渡した場合、投入用の一時ファイルは `mkstemp` (0600) で作成され、投入後に削除されます。
- `suggest_job_script` の `job_name` は英数字・`._-` 以外を `-` に正規化します。クラスタ側ポリシーで先頭文字制約がある場合は投入前に調整してください。