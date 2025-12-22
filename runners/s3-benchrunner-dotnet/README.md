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

Example:
```bash
dotnet run -c Release -- sdk-dotnet-tm workloads/download-1MB-1.run.json my-test-bucket us-west-2 100.0
```

Example with custom chunk and part sizes:
```bash
dotnet run -c Release -- sdk-dotnet-tm workloads/download-1MB-1.run.json my-test-bucket us-west-2 100.0 --chunk-size 131072 --part-size 16777216
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
