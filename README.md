# slurmMCP

Slurmクラスタ向けの最小構成MCPサーバです。AIサービスから以下のジョブ支援機能を利用できます。

- `suggest_job_script`: Slurmジョブスクリプトのテンプレート生成
- `submit_job`: `sbatch` を使ったジョブ投入
- `job_status`: `squeue` でジョブ状態確認
- `list_queue`: キュー一覧取得
- `cancel_job`: `scancel` でジョブ停止

## 実行

```bash
python /home/runner/work/slurmMCP/slurmMCP/slurm_mcp_server.py
```

## テスト

```bash
python -m unittest -v
```