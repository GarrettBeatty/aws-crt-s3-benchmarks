#!/bin/zsh

# Benchmark script for testing optimal chunk sizes with different part sizes
# This script runs the S3 benchmark runner with various combinations of chunk sizes
# and part sizes to find the optimal configuration for performance.

# Exit on error
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
PROJECT_PATH="${PROJECT_PATH:-/home/ec2-user/aws-crt-s3-benchmarks/runners/s3-benchrunner-dotnet/S3BenchRunner}"
WORKLOAD_PATH="${WORKLOAD_PATH:-/home/ec2-user/aws-crt-s3-benchmarks/workloads/download-5GiB-1x-ram.run.json}"
BUCKET_NAME="${BUCKET_NAME:-multibucketgarrett}"
REGION="${REGION:-us-west-2}"
TARGET_THROUGHPUT="${TARGET_THROUGHPUT:-100}"

# Part sizes to test (in bytes)
# 8MB, 16MB, 32MB, 64MB, 128MB, 256MB, 512MB, 1GB, 2GB, 5GB
PART_SIZES=(8388608 16777216 33554432 67108864 134217728 268435456 536870912 1073741824 2147483648 5368709120)

# Chunk sizes to test (in bytes)
# 64KB, 256KB, 1MB, 4MB, 16MB, 64MB, 256MB, 512MB, 1GB, 2GB
CHUNK_SIZES=(65536 262144 1048576 4194304 16777216 67108864 268435456 536870912 1073741824 2147483648)

# Output files
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT_DIR="benchmark-results-${TIMESTAMP}"
CSV_FILE="${OUTPUT_DIR}/results.csv"
LOG_FILE="${OUTPUT_DIR}/benchmark.log"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Helper function to format bytes
format_bytes() {
    local bytes=$1
    if [ $bytes -lt 1024 ]; then
        echo "${bytes}B"
    elif [ $bytes -lt 1048576 ]; then
        echo "$((bytes / 1024))KB"
    else
        echo "$((bytes / 1048576))MB"
    fi
}

# Print header
echo "${BLUE}============================================${NC}"
echo "${BLUE}S3 Chunk Size Benchmark${NC}"
echo "${BLUE}============================================${NC}"
echo ""
echo "Configuration:"
echo "  Project: $PROJECT_PATH"
echo "  Workload: $WORKLOAD_PATH"
echo "  Bucket: $BUCKET_NAME"
echo "  Region: $REGION"
echo "  Target Throughput: ${TARGET_THROUGHPUT} Gbps"
echo ""
echo "Testing:"
echo "  Part Sizes: ${#PART_SIZES[@]} variations"
echo "  Chunk Sizes: ${#CHUNK_SIZES[@]} variations"
echo "  Total Tests: $((${#PART_SIZES[@]} * ${#CHUNK_SIZES[@]}))"
echo ""
echo "Output:"
echo "  Directory: $OUTPUT_DIR"
echo "  CSV: $CSV_FILE"
echo "  Log: $LOG_FILE"
echo "${BLUE}============================================${NC}"
echo ""

# Create CSV header
echo "part_size,part_size_formatted,chunk_size,chunk_size_formatted,run,seconds,gbps" > "$CSV_FILE"

# Counter for progress
total_tests=$((${#PART_SIZES[@]} * ${#CHUNK_SIZES[@]}))
current_test=0

# Main benchmark loop
for part_size in "${PART_SIZES[@]}"; do
    part_size_fmt=$(format_bytes $part_size)
    
    for chunk_size in "${CHUNK_SIZES[@]}"; do
        current_test=$((current_test + 1))
        chunk_size_fmt=$(format_bytes $chunk_size)
        
        echo "${YELLOW}[${current_test}/${total_tests}]${NC} Testing: Part=${part_size_fmt}, Chunk=${chunk_size_fmt}"
        
        # Run benchmark and capture output
        output=$(dotnet run -c Release --project "$PROJECT_PATH" -- \
            sdk-dotnet-tm "$WORKLOAD_PATH" "$BUCKET_NAME" "$REGION" "$TARGET_THROUGHPUT" \
            --part-size "$part_size" --chunk-size "$chunk_size" 2>&1)
        
        # Check if run was successful
        if [ $? -ne 0 ]; then
            echo "${RED}  ✗ Failed${NC}"
            echo "$output" >> "$LOG_FILE"
            echo ""
            continue
        fi
        
        # Parse output for benchmark results
        # Expected format: "Run:N Secs:X.XXXX Gb/s:Y.YYYY"
        run_count=0
        echo "$output" | grep "Run:" | while IFS= read -r line; do
            run=$(echo "$line" | sed -n 's/.*Run:\([0-9]*\).*/\1/p')
            secs=$(echo "$line" | sed -n 's/.*Secs:\([0-9.]*\).*/\1/p')
            gbps=$(echo "$line" | sed -n 's/.*Gb\/s:\([0-9.]*\).*/\1/p')
            
            if [ -n "$run" ] && [ -n "$secs" ] && [ -n "$gbps" ]; then
                echo "$part_size,$part_size_fmt,$chunk_size,$chunk_size_fmt,$run,$secs,$gbps" >> "$CSV_FILE"
                run_count=$((run_count + 1))
            fi
        done
        
        # Calculate average throughput from this test
        avg_gbps=$(echo "$output" | grep "Run:" | \
            sed -n 's/.*Gb\/s:\([0-9.]*\).*/\1/p' | \
            awk '{ sum += $1; n++ } END { if (n > 0) print sum / n; else print 0 }')
        
        echo "${GREEN}  ✓ Complete${NC} - Average: ${avg_gbps} Gb/s"
        
        # Log full output
        echo "======================================" >> "$LOG_FILE"
        echo "Part Size: $part_size_fmt ($part_size bytes)" >> "$LOG_FILE"
        echo "Chunk Size: $chunk_size_fmt ($chunk_size bytes)" >> "$LOG_FILE"
        echo "Timestamp: $(date)" >> "$LOG_FILE"
        echo "--------------------------------------" >> "$LOG_FILE"
        echo "$output" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
    done
    
    echo ""
done

# Generate summary
echo "${BLUE}============================================${NC}"
echo "${GREEN}Benchmark Complete!${NC}"
echo "${BLUE}============================================${NC}"
echo ""
echo "Results saved to:"
echo "  CSV: $CSV_FILE"
echo "  Log: $LOG_FILE"
echo ""

# Find optimal configuration
if command -v awk &> /dev/null; then
    echo "Top 5 configurations by average throughput:"
    echo "-------------------------------------------"
    tail -n +2 "$CSV_FILE" | \
        awk -F',' '{ key=$1","$2","$3","$4; sum[key]+=$7; count[key]++ } 
                    END { for (k in sum) print k","sum[k]/count[k] }' | \
        sort -t',' -k5 -rn | head -5 | \
        awk -F',' 'BEGIN { printf "%-10s %-10s %10s\n", "Part Size", "Chunk Size", "Avg Gb/s" }
                   { printf "%-10s %-10s %10.4f\n", $2, $4, $5 }'
    echo ""
fi

echo "To analyze results, you can use:"
echo "  cat $CSV_FILE | column -t -s,"
echo ""
echo "Or import into a spreadsheet application for detailed analysis."
