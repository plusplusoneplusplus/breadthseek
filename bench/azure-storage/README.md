# Azure Blob Storage Read Latency Benchmark

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/plusplusoneplusplus/breadthseek/main/bench/azure-storage/bootstrap.sh | bash
```

## Usage

```bash
export SAS_URL='https://<account>.blob.core.windows.net/<container>?<sas_token>'

# Prepare test data
uv run python bench_read_latency.py prepare --sas-url "$SAS_URL"

# Run benchmark
uv run python bench_read_latency.py run --sas-url "$SAS_URL"

# Clean up
uv run python bench_read_latency.py cleanup --sas-url "$SAS_URL"
```
