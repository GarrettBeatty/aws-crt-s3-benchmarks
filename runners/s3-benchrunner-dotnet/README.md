# S3 Benchmark Runner for .NET SDK

This benchmark runner tests the AWS SDK for .NET's TransferUtility implementation.

## Requirements

- .NET 8.0 SDK
- AWS credentials configured with S3 access

## Building

From the root of this directory:

```bash
cd S3BenchRunner
dotnet build -c Release
```

## Running

The runner expects to be executed from the directory containing the files to upload/download. It follows the standard command line interface used by all benchmark runners:

```bash
dotnet run -c Release -- sdk-dotnet-tm WORKLOAD BUCKET REGION TARGET_THROUGHPUT
```

Arguments:
- `sdk-dotnet-tm`: The only supported S3 client ID (current TransferUtility implementation)
- `WORKLOAD`: Path to workload .run.json file
- `BUCKET`: S3 bucket name
- `REGION`: AWS region (e.g., us-west-2)
- `TARGET_THROUGHPUT`: Target throughput in Gbps (floating point). This parameter not used for now.

Optional Arguments:
- `--chunk-size BYTES`: Internal buffer chunk size for downloads (default: 65536 bytes / 64KB)
- `--part-size BYTES`: Part size for multipart downloads (default: 8388608 bytes / 8MB)
- `--mock`: Use mock HTTP handler to eliminate network I/O (for CPU/memory benchmarking)

Example:
```bash
dotnet run -c Release -- sdk-dotnet-tm workloads/download-1MB-1.run.json my-test-bucket us-west-2 100.0
```

Example with custom chunk and part sizes:
```bash
dotnet run -c Release -- sdk-dotnet-tm workloads/download-1MB-1.run.json my-test-bucket us-west-2 100.0 --chunk-size 131072 --part-size 16777216
```

Example with mock mode (no network I/O):
```bash
dotnet run -c Release -- sdk-dotnet-tm workloads/download-1MB-1.run.json my-test-bucket us-west-2 100.0 --mock --chunk-size 65536 --part-size 8388608
```

## Mock Mode (Network-Free Benchmarking)

The `--mock` flag enables mock HTTP mode, which eliminates network I/O to isolate CPU and memory performance:

### How It Works

When `--mock` is enabled:
1. A mock HTTP message handler intercepts all S3 API calls
2. Mock responses simulate S3 multipart download behavior
3. Mock data streams return fake data without actual network transfers
4. The SDK's buffering, streaming, and memory management logic runs as normal

### Use Cases

**CPU/Memory Benchmarking:**
- Isolate buffering and streaming overhead
- Measure pure CPU performance without network variability
- Test memory efficiency of different chunk/part size combinations
- Profile ArrayPool usage and allocation patterns

**Fast Iteration:**
- No S3 costs or network latency
- Reproducible results (same mock data every time)
- Faster benchmark runs for large object sizes

### Limitations

- Only supports download operations (uploads still use actual S3 in mock mode)
- Does not simulate network latency or bandwidth constraints
- Results reflect CPU/memory performance, not real-world network throughput

### Example Usage

Pure CPU/memory benchmark with various chunk sizes:
```bash
# Benchmark 100MB download with different chunk sizes (no network)
dotnet run -c Release -- sdk-dotnet-tm workloads/download-100MB-1.run.json bucket us-west-2 100.0 --mock --chunk-size 65536 --part-size 8388608
dotnet run -c Release -- sdk-dotnet-tm workloads/download-100MB-1.run.json bucket us-west-2 100.0 --mock --chunk-size 131072 --part-size 8388608
dotnet run -c Release -- sdk-dotnet-tm workloads/download-100MB-1.run.json bucket us-west-2 100.0 --mock --chunk-size 262144 --part-size 8388608
```

Compare mock mode vs. real network:
```bash
# Mock mode (CPU/memory only)
dotnet run -c Release -- sdk-dotnet-tm workloads/download-50MB-1.run.json bucket us-west-2 100.0 --mock

# Real network (includes network I/O)
dotnet run -c Release -- sdk-dotnet-tm workloads/download-50MB-1.run.json bucket us-west-2 100.0
```


## Output

Results are written to stdout in a user-friendly format:
```
Run:N Secs:X.XXXXXX Gb/s:X.XXXXXX
```

Where:
- N: Run number (1 to maxRepeatCount)
- X.XXXXXX: Values with 6 decimal precision
- Secs: Duration of executing all tasks in the workload
- Gb/s: Throughput in gigabits per second (based on total bytes transferred)

For workloads with multiple tasks:
- Tasks are executed in parallel using async/await
- Each run executes all tasks concurrently
- Reports total time and aggregate throughput for the run

File Handling:
- When filesOnDisk is true (default):
  * Downloads write to local files
  * Uploads read from local files
  * Files are cleaned up between runs
- When filesOnDisk is false:
  * Downloads write to /dev/null
  * Uploads use random data from memory
  * No files are created on disk

Example output:
```
Run:1 Secs:0.056775 Gb/s:0.009235
Run:2 Secs:0.027504 Gb/s:0.019063
Run:3 Secs:0.057251 Gb/s:0.009158
```

## Chunk Size Benchmarking

### Running Automated Benchmarks

The `benchmark_chunk_sizes.zsh` script automates testing various chunk size and part size combinations:

```bash
./benchmark_chunk_sizes.zsh
```

**Prerequisites:**
- zsh shell
- A workload file (e.g., `workloads/download-50MB-1.run.json`)
- AWS credentials configured
- Sufficient S3 bucket space

**Configuration:**
Edit the script to set:
- `BUCKET`: Your S3 bucket name
- `REGION`: AWS region (e.g., us-west-2)
- `WORKLOAD`: Path to workload file
- `OUTPUT_DIR`: Directory for results (default: results)

The script will:
1. Test multiple chunk size values (8KB, 16KB, 32KB, 64KB, 128KB, 256KB, 512KB, 1MB, 2MB, 4MB, 8MB, 16MB, 32MB, 64MB, 128MB, 256MB, 512MB, 1GB, 2GB)
2. Test multiple part size values (8KB, 16KB, 32KB, 64KB, 128KB, 256KB, 512KB, 1MB, 2MB, 4MB, 8MB, 16MB, 32MB, 64MB, 128MB, 256MB, 512MB, 1GB, 2GB)
3. Skip invalid combinations where chunk size > part size
4. Save results to CSV file: `results/results_TIMESTAMP.csv`

**Output Format:**
Each line in the CSV contains:
```
chunk_size,part_size,run,seconds,gbps
```

### Analyzing Results

The `analyze_chunk_benchmark.py` script analyzes benchmark results and generates visualizations:

```bash
python analyze_chunk_benchmark.py results/results_TIMESTAMP.csv
```

**Prerequisites:**
- Python 3.x
- Required packages:
  ```bash
  pip install pandas matplotlib seaborn
  ```

**Generated Visualizations:**

The script creates an `analysis` directory with:

1. **heatmap_throughput.png**: Heatmap showing throughput (Gb/s) for each chunk/part size combination
   - X-axis: Part sizes
   - Y-axis: Chunk sizes
   - Color: Average throughput

2. **lineplot_per_part_size.png**: Line plots showing throughput vs chunk size for each part size
   - Helps identify optimal chunk sizes for different part sizes
   - Shows trends and performance characteristics

3. **optimal_chunk_sizes.png**: Bar chart showing the optimal chunk size for each part size
   - Displays which chunk size achieved the best throughput for each part size
   - Useful for configuration recommendations

**Console Output:**
The script also prints:
- Overall best configuration (chunk size + part size)
- Top 10 configurations by throughput
- Optimal chunk size for each part size

Example:
```
Overall Best Configuration:
  Chunk Size: 128KB, Part Size: 8MB, Avg Throughput: 1.234 Gb/s

Top 10 Configurations:
  1. Chunk: 128KB, Part: 8MB -> 1.234 Gb/s
  2. Chunk: 256KB, Part: 8MB -> 1.198 Gb/s
  ...
```
