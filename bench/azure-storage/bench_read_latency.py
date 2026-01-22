#!/usr/bin/env python3
"""
Azure Blob Storage Read Latency Benchmark

Measures read latency for different blob sizes and read patterns.
Uses random offsets and unique blob names to minimize cache effects.

Usage:
    # Prepare test data (upload blobs of various sizes with unique names)
    python bench_read_latency.py prepare --sas-url "https://<account>.blob.core.windows.net/<container>?<sas_token>"

    # Run benchmark (uses the manifest from prepare)
    python bench_read_latency.py run --sas-url "https://<account>.blob.core.windows.net/<container>?<sas_token>"

    # Clean up test data
    python bench_read_latency.py cleanup --sas-url "https://<account>.blob.core.windows.net/<container>?<sas_token>"
"""

import argparse
import json
import os
import random
import statistics
import string
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from azure.storage.blob import ContainerClient, BlobClient
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# Benchmark configuration
BLOB_PREFIX = "bench_latency_"
MANIFEST_FILE = "bench_manifest.json"
DEFAULT_ITERATIONS = 50
WARMUP_ITERATIONS = 5

# Blob sizes to test (in bytes)
BLOB_SIZES = {
    "1KB": 1 * 1024,
    "4KB": 4 * 1024,
    "16KB": 16 * 1024,
    "64KB": 64 * 1024,
    "256KB": 256 * 1024,
    "1MB": 1 * 1024 * 1024,
    "4MB": 4 * 1024 * 1024,
    "16MB": 16 * 1024 * 1024,
}

# Read sizes to test (in bytes)
READ_SIZES = {
    "1KB": 1 * 1024,
    "4KB": 4 * 1024,
    "16KB": 16 * 1024,
    "64KB": 64 * 1024,
    "256KB": 256 * 1024,
    "1MB": 1 * 1024 * 1024,
}


@dataclass
class LatencyResult:
    """Result of a latency measurement."""
    blob_size: str
    read_size: str
    latencies_ms: list[float]
    
    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.latencies_ms)
    
    @property
    def median_ms(self) -> float:
        return statistics.median(self.latencies_ms)
    
    @property
    def p95_ms(self) -> float:
        return statistics.quantiles(self.latencies_ms, n=20)[18] if len(self.latencies_ms) >= 20 else max(self.latencies_ms)
    
    @property
    def p99_ms(self) -> float:
        return statistics.quantiles(self.latencies_ms, n=100)[98] if len(self.latencies_ms) >= 100 else max(self.latencies_ms)
    
    @property
    def min_ms(self) -> float:
        return min(self.latencies_ms)
    
    @property
    def max_ms(self) -> float:
        return max(self.latencies_ms)
    
    @property
    def stddev_ms(self) -> float:
        return statistics.stdev(self.latencies_ms) if len(self.latencies_ms) > 1 else 0.0


def generate_unique_id(length: int = 12) -> str:
    """Generate a unique random ID."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_manifest_path() -> Path:
    """Get the path to the manifest file (in the same directory as the script)."""
    return Path(__file__).parent / MANIFEST_FILE


def load_manifest() -> dict[str, str]:
    """Load the blob manifest from file."""
    manifest_path = get_manifest_path()
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest file not found: {manifest_path}\n"
            "Run 'prepare' command first to create test blobs."
        )
    with open(manifest_path) as f:
        return json.load(f)


def save_manifest(manifest: dict[str, str]) -> None:
    """Save the blob manifest to file."""
    manifest_path = get_manifest_path()
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    console.print(f"[dim]Manifest saved to {manifest_path}[/dim]")


def parse_container_sas_url(sas_url: str) -> tuple[str, str, str]:
    """
    Parse a container SAS URL into components.
    
    Args:
        sas_url: Full container SAS URL like 
                 https://<account>.blob.core.windows.net/<container>?<sas_token>
    
    Returns:
        Tuple of (account_url, container_name, sas_token)
    """
    parsed = urlparse(sas_url)
    
    # Extract account URL (scheme + netloc)
    account_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Extract container name from path (remove leading slash)
    container_name = parsed.path.lstrip("/").split("/")[0]
    
    # Extract SAS token (query string)
    sas_token = parsed.query
    
    return account_url, container_name, sas_token


def get_container_client(sas_url: str) -> ContainerClient:
    """Create a ContainerClient from a SAS URL."""
    account_url, container_name, sas_token = parse_container_sas_url(sas_url)
    return ContainerClient(
        account_url=account_url,
        container_name=container_name,
        credential=sas_token
    )


def generate_random_data(size: int) -> bytes:
    """Generate random bytes of specified size."""
    return os.urandom(size)


def prepare_test_data(sas_url: str) -> None:
    """Upload test blobs of various sizes with unique names."""
    container_client = get_container_client(sas_url)
    
    # Generate unique run ID for this preparation
    run_id = generate_unique_id()
    
    console.print("[bold blue]Preparing test data...[/bold blue]")
    console.print(f"[dim]Run ID: {run_id}[/dim]")
    
    # Manifest maps size_name -> blob_name
    manifest: dict[str, str] = {"_run_id": run_id}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading blobs...", total=len(BLOB_SIZES))
        
        for size_name, size_bytes in BLOB_SIZES.items():
            # Generate unique blob name for each size
            blob_id = generate_unique_id()
            blob_name = f"{BLOB_PREFIX}{run_id}_{size_name}_{blob_id}"
            blob_client = container_client.get_blob_client(blob_name)
            
            progress.update(task, description=f"Uploading {size_name} blob...")
            
            # Generate and upload random data
            data = generate_random_data(size_bytes)
            blob_client.upload_blob(data, overwrite=True)
            
            manifest[size_name] = blob_name
            progress.advance(task)
    
    # Save manifest for later use
    save_manifest(manifest)
    
    console.print("[bold green]Test data prepared successfully![/bold green]")
    console.print(f"Uploaded {len(BLOB_SIZES)} blobs with unique names")


def cleanup_test_data(sas_url: str, cleanup_all: bool = False) -> None:
    """Delete test blobs."""
    container_client = get_container_client(sas_url)
    
    console.print("[bold blue]Cleaning up test data...[/bold blue]")
    
    if cleanup_all:
        # Delete all blobs with the benchmark prefix
        console.print(f"[yellow]Deleting ALL blobs with prefix '{BLOB_PREFIX}'...[/yellow]")
        deleted_count = 0
        for blob in container_client.list_blobs(name_starts_with=BLOB_PREFIX):
            blob_client = container_client.get_blob_client(blob.name)
            blob_client.delete_blob()
            deleted_count += 1
            console.print(f"  Deleted: {blob.name}")
        console.print(f"[bold green]Cleaned up {deleted_count} blobs[/bold green]")
    else:
        # Delete only blobs from the manifest
        try:
            manifest = load_manifest()
        except FileNotFoundError as e:
            console.print(f"[yellow]{e}[/yellow]")
            console.print("[yellow]Use --all to delete all benchmark blobs.[/yellow]")
            return
        
        deleted_count = 0
        for size_name, blob_name in manifest.items():
            if size_name.startswith("_"):
                continue  # Skip metadata keys
            blob_client = container_client.get_blob_client(blob_name)
            try:
                blob_client.delete_blob()
                deleted_count += 1
                console.print(f"  Deleted: {blob_name}")
            except Exception as e:
                console.print(f"  [yellow]Could not delete {blob_name}: {e}[/yellow]")
        
        # Remove manifest file
        manifest_path = get_manifest_path()
        if manifest_path.exists():
            manifest_path.unlink()
            console.print(f"[dim]Removed manifest file[/dim]")
        
        console.print(f"[bold green]Cleaned up {deleted_count} blobs[/bold green]")


def measure_read_latency(
    blob_client: BlobClient,
    blob_size: int,
    read_size: int,
    iterations: int,
    warmup: int = WARMUP_ITERATIONS,
) -> list[float]:
    """
    Measure read latency for a blob.
    
    Reads from random offsets to avoid cache effects.
    
    Args:
        blob_client: The blob client to read from
        blob_size: Total size of the blob in bytes
        read_size: Size of each read in bytes
        iterations: Number of measurements to take
        warmup: Number of warmup iterations (not counted)
    
    Returns:
        List of latency measurements in milliseconds
    """
    latencies = []
    
    # Calculate valid offset range
    max_offset = max(0, blob_size - read_size)
    
    # Warmup reads (not measured)
    for _ in range(warmup):
        offset = random.randint(0, max_offset) if max_offset > 0 else 0
        blob_client.download_blob(offset=offset, length=read_size).readall()
    
    # Measured reads
    for _ in range(iterations):
        # Random offset to avoid cache effects
        offset = random.randint(0, max_offset) if max_offset > 0 else 0
        
        start_time = time.perf_counter()
        blob_client.download_blob(offset=offset, length=read_size).readall()
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        latencies.append(latency_ms)
    
    return latencies


def run_benchmark(
    sas_url: str,
    iterations: int = DEFAULT_ITERATIONS,
    blob_sizes: Optional[list[str]] = None,
    read_sizes: Optional[list[str]] = None,
) -> list[LatencyResult]:
    """
    Run the read latency benchmark.
    
    Automatically prepares test data if not already present.
    
    Args:
        sas_url: Container SAS URL
        iterations: Number of iterations per test
        blob_sizes: List of blob size names to test (default: all)
        read_sizes: List of read size names to test (default: all)
    
    Returns:
        List of LatencyResult objects
    """
    container_client = get_container_client(sas_url)
    
    # Auto-prepare if manifest doesn't exist
    try:
        manifest = load_manifest()
        run_id = manifest.get("_run_id", "unknown")
        console.print(f"[dim]Using blobs from run: {run_id}[/dim]")
    except FileNotFoundError:
        console.print("[yellow]No test data found. Preparing automatically...[/yellow]")
        console.print()
        prepare_test_data(sas_url)
        manifest = load_manifest()
        run_id = manifest.get("_run_id", "unknown")
        console.print()
        console.print(f"[dim]Using blobs from run: {run_id}[/dim]")
    
    # Filter sizes if specified
    test_blob_sizes = {k: v for k, v in BLOB_SIZES.items() if blob_sizes is None or k in blob_sizes}
    test_read_sizes = {k: v for k, v in READ_SIZES.items() if read_sizes is None or k in read_sizes}
    
    results = []
    total_tests = sum(
        1 for bs_name, bs in test_blob_sizes.items()
        for rs_name, rs in test_read_sizes.items()
        if rs <= bs
    )
    
    console.print(f"[bold blue]Running benchmark with {iterations} iterations per test...[/bold blue]")
    console.print(f"Testing {len(test_blob_sizes)} blob sizes × {len(test_read_sizes)} read sizes")
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running tests...", total=total_tests)
        
        for blob_size_name, blob_size_bytes in test_blob_sizes.items():
            # Get blob name from manifest
            blob_name = manifest.get(blob_size_name)
            if not blob_name:
                console.print(f"[red]Blob for size {blob_size_name} not found in manifest. Run 'prepare' first.[/red]")
                raise ValueError(f"Missing blob for size {blob_size_name}")
            
            blob_client = container_client.get_blob_client(blob_name)
            
            # Verify blob exists
            try:
                props = blob_client.get_blob_properties()
            except Exception as e:
                console.print(f"[red]Blob {blob_name} not found. Run 'prepare' first.[/red]")
                raise
            
            for read_size_name, read_size_bytes in test_read_sizes.items():
                # Skip if read size > blob size
                if read_size_bytes > blob_size_bytes:
                    continue
                
                progress.update(
                    task, 
                    description=f"Testing blob={blob_size_name}, read={read_size_name}..."
                )
                
                latencies = measure_read_latency(
                    blob_client,
                    blob_size_bytes,
                    read_size_bytes,
                    iterations,
                )
                
                results.append(LatencyResult(
                    blob_size=blob_size_name,
                    read_size=read_size_name,
                    latencies_ms=latencies,
                ))
                
                progress.advance(task)
    
    return results


def display_results(results: list[LatencyResult]) -> None:
    """Display benchmark results in a formatted table."""
    console.print()
    console.print("[bold green]Benchmark Results[/bold green]")
    console.print()
    
    table = Table(title="Read Latency (ms)")
    table.add_column("Blob Size", style="cyan")
    table.add_column("Read Size", style="cyan")
    table.add_column("Mean", justify="right")
    table.add_column("Median", justify="right")
    table.add_column("P95", justify="right")
    table.add_column("P99", justify="right")
    table.add_column("Min", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("StdDev", justify="right")
    
    for result in results:
        table.add_row(
            result.blob_size,
            result.read_size,
            f"{result.mean_ms:.2f}",
            f"{result.median_ms:.2f}",
            f"{result.p95_ms:.2f}",
            f"{result.p99_ms:.2f}",
            f"{result.min_ms:.2f}",
            f"{result.max_ms:.2f}",
            f"{result.stddev_ms:.2f}",
        )
    
    console.print(table)
    
    # Summary by read size
    console.print()
    console.print("[bold]Summary by Read Size (mean latency across all blob sizes):[/bold]")
    
    read_size_groups: dict[str, list[float]] = {}
    for result in results:
        if result.read_size not in read_size_groups:
            read_size_groups[result.read_size] = []
        read_size_groups[result.read_size].append(result.mean_ms)
    
    for read_size, means in sorted(read_size_groups.items(), key=lambda x: READ_SIZES.get(x[0], 0)):
        avg_mean = statistics.mean(means)
        console.print(f"  {read_size}: {avg_mean:.2f} ms")


def export_results_csv(results: list[LatencyResult], output_path: str) -> None:
    """Export results to CSV file."""
    import csv
    
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "blob_size", "read_size", "mean_ms", "median_ms", 
            "p95_ms", "p99_ms", "min_ms", "max_ms", "stddev_ms"
        ])
        
        for result in results:
            writer.writerow([
                result.blob_size,
                result.read_size,
                f"{result.mean_ms:.3f}",
                f"{result.median_ms:.3f}",
                f"{result.p95_ms:.3f}",
                f"{result.p99_ms:.3f}",
                f"{result.min_ms:.3f}",
                f"{result.max_ms:.3f}",
                f"{result.stddev_ms:.3f}",
            ])
    
    console.print(f"[green]Results exported to {output_path}[/green]")


def main():
    parser = argparse.ArgumentParser(
        description="Azure Blob Storage Read Latency Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prepare test data (creates unique blob names)
  python bench_read_latency.py prepare --sas-url "https://myaccount.blob.core.windows.net/mycontainer?sv=2022-11-02&..."

  # Run benchmark with default settings
  python bench_read_latency.py run --sas-url "https://myaccount.blob.core.windows.net/mycontainer?sv=2022-11-02&..."

  # Run benchmark with custom iterations and export to CSV
  python bench_read_latency.py run --sas-url "..." --iterations 100 --output results.csv

  # Test specific sizes only
  python bench_read_latency.py run --sas-url "..." --blob-sizes 1MB 4MB --read-sizes 64KB 256KB

  # Clean up test data from current run
  python bench_read_latency.py cleanup --sas-url "https://myaccount.blob.core.windows.net/mycontainer?sv=2022-11-02&..."

  # Clean up ALL benchmark blobs (from any run)
  python bench_read_latency.py cleanup --sas-url "..." --all
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Prepare command
    prepare_parser = subparsers.add_parser("prepare", help="Upload test blobs with unique names")
    prepare_parser.add_argument(
        "--sas-url", 
        required=True,
        help="Container SAS URL (https://<account>.blob.core.windows.net/<container>?<sas_token>)"
    )
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run the benchmark")
    run_parser.add_argument(
        "--sas-url",
        required=True,
        help="Container SAS URL"
    )
    run_parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of iterations per test (default: {DEFAULT_ITERATIONS})"
    )
    run_parser.add_argument(
        "--blob-sizes",
        nargs="+",
        choices=list(BLOB_SIZES.keys()),
        help="Blob sizes to test (default: all)"
    )
    run_parser.add_argument(
        "--read-sizes",
        nargs="+",
        choices=list(READ_SIZES.keys()),
        help="Read sizes to test (default: all)"
    )
    run_parser.add_argument(
        "--output",
        help="Output CSV file path"
    )
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Delete test blobs")
    cleanup_parser.add_argument(
        "--sas-url",
        required=True,
        help="Container SAS URL"
    )
    cleanup_parser.add_argument(
        "--all",
        action="store_true",
        dest="cleanup_all",
        help="Delete ALL benchmark blobs (not just from current run)"
    )
    
    args = parser.parse_args()
    
    if args.command == "prepare":
        prepare_test_data(args.sas_url)
    
    elif args.command == "run":
        results = run_benchmark(
            args.sas_url,
            iterations=args.iterations,
            blob_sizes=args.blob_sizes,
            read_sizes=args.read_sizes,
        )
        display_results(results)
        
        if args.output:
            export_results_csv(results, args.output)
    
    elif args.command == "cleanup":
        cleanup_test_data(args.sas_url, cleanup_all=args.cleanup_all)


if __name__ == "__main__":
    main()
