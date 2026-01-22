# Azure Blob Storage Read Latency Benchmark

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage/bootstrap.sh | bash
```

## Update to Latest

```bash
curl -fsSL https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage/bootstrap.sh | bash -s -- --update
```

## Usage

```bash
cd ~/azure-storage-bench
export SAS_URL='https://<account>.blob.core.windows.net/<container>?<sas_token>'

# Run benchmark (auto-prepares test data if needed)
uv run python bench_read_latency.py run --sas-url "$SAS_URL"
```
