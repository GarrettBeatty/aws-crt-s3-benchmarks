#!/usr/bin/env python3
"""
Benchmark Results Analyzer for S3 Chunk Size Optimization

This script analyzes benchmark results to find optimal chunk sizes for different
part sizes, identifying performance tipping points and generating recommendations
for SDK implementation.

Usage:
    python analyze_chunk_benchmark.py results.csv [--output-dir ./analysis]
"""

import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple

# Set style for better-looking plots
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human-readable string."""
    if bytes_val < 1024:
        return f"{bytes_val}B"
    elif bytes_val < 1024**2:
        return f"{bytes_val // 1024}KB"
    elif bytes_val < 1024**3:
        return f"{bytes_val // (1024**2)}MB"
    else:
        return f"{bytes_val // (1024**3)}GB"


def load_and_preprocess_data(csv_path: str) -> pd.DataFrame:
    """Load CSV and calculate aggregate statistics."""
    print(f"Loading data from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    
    # Calculate statistics per (part_size, chunk_size) combination
    stats = df.groupby(['part_size', 'chunk_size', 'part_size_formatted', 'chunk_size_formatted'])['gbps'].agg([
        ('mean_gbps', 'mean'),
        ('std_gbps', 'std'),
        ('min_gbps', 'min'),
        ('max_gbps', 'max'),
        ('count', 'count')
    ]).reset_index()
    
    print(f"Loaded {len(df)} runs across {len(stats)} configurations")
    print(f"Part sizes: {sorted(df['part_size'].unique())}")
    print(f"Chunk sizes: {sorted(df['chunk_size'].unique())}")
    
    return stats


def create_heatmap(df: pd.DataFrame, output_dir: Path):
    """Create heatmap showing throughput for each part_size × chunk_size."""
    print("\nGenerating heatmap...")
    
    # Pivot data for heatmap
    pivot = df.pivot(index='part_size_formatted', 
                     columns='chunk_size_formatted', 
                     values='mean_gbps')
    
    # Sort by actual byte values
    part_order = df.sort_values('part_size')['part_size_formatted'].unique()
    chunk_order = df.sort_values('chunk_size')['chunk_size_formatted'].unique()
    pivot = pivot.reindex(index=part_order, columns=chunk_order)
    
    # Create heatmap
    plt.figure(figsize=(14, 10))
    sns.heatmap(pivot, annot=True, fmt='.2f', cmap='YlGnBu', 
                cbar_kws={'label': 'Throughput (Gb/s)'})
    plt.title('S3 Download Throughput by Part Size and Chunk Size', fontsize=16, pad=20)
    plt.xlabel('Chunk Size', fontsize=12)
    plt.ylabel('Part Size', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    output_path = output_dir / 'heatmap_throughput.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()


def create_line_charts_per_part_size(df: pd.DataFrame, output_dir: Path):
    """Create line charts showing throughput vs chunk size for each part size."""
    print("\nGenerating line charts per part size...")
    
    part_sizes = sorted(df['part_size'].unique())
    n_parts = len(part_sizes)
    
    # Create subplot grid
    n_cols = 3
    n_rows = (n_parts + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 5 * n_rows))
    axes = axes.flatten() if n_parts > 1 else [axes]
    
    for idx, part_size in enumerate(part_sizes):
        ax = axes[idx]
        part_data = df[df['part_size'] == part_size].sort_values('chunk_size')
        
        # Plot mean with error bars
        ax.errorbar(range(len(part_data)), part_data['mean_gbps'], 
                   yerr=part_data['std_gbps'], marker='o', capsize=5, 
                   linewidth=2, markersize=8)
        
        # Mark the optimal point
        optimal_idx = part_data['mean_gbps'].idxmax()
        optimal_row = part_data.loc[optimal_idx]
        ax.plot(part_data.index.get_loc(optimal_idx), optimal_row['mean_gbps'], 
               'r*', markersize=20, label='Optimal')
        
        ax.set_xticks(range(len(part_data)))
        ax.set_xticklabels(part_data['chunk_size_formatted'], rotation=45, ha='right')
        ax.set_xlabel('Chunk Size', fontsize=10)
        ax.set_ylabel('Throughput (Gb/s)', fontsize=10)
        ax.set_title(f'Part Size: {part_data.iloc[0]["part_size_formatted"]}', 
                    fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()
    
    # Hide empty subplots
    for idx in range(n_parts, len(axes)):
        axes[idx].set_visible(False)
    
    plt.suptitle('Throughput vs Chunk Size by Part Size', fontsize=16, y=1.00)
    plt.tight_layout()
    
    output_path = output_dir / 'lineplot_per_part_size.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()


def create_optimal_chunk_chart(optimal_configs: List[Dict], output_dir: Path):
    """Create bar chart showing optimal chunk size for each part size."""
    print("\nGenerating optimal chunk size chart...")
    
    part_sizes = [c['part_size_formatted'] for c in optimal_configs]
    chunk_sizes = [c['chunk_size_formatted'] for c in optimal_configs]
    throughputs = [c['mean_gbps'] for c in optimal_configs]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Chart 1: Optimal chunk sizes
    colors = plt.cm.viridis(np.linspace(0, 1, len(part_sizes)))
    bars1 = ax1.barh(part_sizes, range(len(chunk_sizes)), color=colors)
    ax1.set_yticks(range(len(part_sizes)))
    ax1.set_yticklabels(part_sizes)
    ax1.set_xticks(range(len(chunk_sizes)))
    ax1.set_xticklabels(chunk_sizes, rotation=45, ha='right')
    ax1.set_xlabel('Optimal Chunk Size', fontsize=12)
    ax1.set_ylabel('Part Size', fontsize=12)
    ax1.set_title('Optimal Chunk Size for Each Part Size', fontsize=14, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    
    # Add labels
    for i, (chunk, throughput) in enumerate(zip(chunk_sizes, throughputs)):
        ax1.text(i, i, f' {chunk}\n {throughput:.2f} Gb/s', 
                va='center', fontsize=9, fontweight='bold')
    
    # Chart 2: Throughput achieved
    bars2 = ax2.bar(part_sizes, throughputs, color=colors)
    ax2.set_xlabel('Part Size', fontsize=12)
    ax2.set_ylabel('Throughput (Gb/s)', fontsize=12)
    ax2.set_title('Maximum Throughput Achieved per Part Size', fontsize=14, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, val in zip(bars2, throughputs):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.2f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    output_path = output_dir / 'optimal_chunk_sizes.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_path}")
    plt.close()


def find_optimal_configurations(df: pd.DataFrame) -> List[Dict]:
    """Find the optimal chunk size for each part size."""
    print("\nAnalyzing optimal configurations...")
    
    optimal_configs = []
    part_sizes = sorted(df['part_size'].unique())
    
    for part_size in part_sizes:
        part_data = df[df['part_size'] == part_size]
        optimal_row = part_data.loc[part_data['mean_gbps'].idxmax()]
        
        config = {
            'part_size': optimal_row['part_size'],
            'part_size_formatted': optimal_row['part_size_formatted'],
            'chunk_size': optimal_row['chunk_size'],
            'chunk_size_formatted': optimal_row['chunk_size_formatted'],
            'mean_gbps': optimal_row['mean_gbps'],
            'std_gbps': optimal_row['std_gbps']
        }
        optimal_configs.append(config)
    
    return optimal_configs


def detect_tipping_points(df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Detect tipping points where increasing chunk size stops improving performance.
    Uses derivative analysis to find diminishing returns.
    """
    print("\nDetecting performance tipping points...")
    
    tipping_points = {}
    part_sizes = sorted(df['part_size'].unique())
    
    for part_size in part_sizes:
        part_data = df[df['part_size'] == part_size].sort_values('chunk_size')
        
        # Calculate rate of change (derivative)
        throughputs = part_data['mean_gbps'].values
        if len(throughputs) < 3:
            continue
            
        # Calculate percentage improvement between adjacent points
        improvements = np.diff(throughputs) / throughputs[:-1] * 100
        
        # Find where improvement drops below threshold (e.g., 5%)
        threshold = 5.0  # 5% improvement threshold
        tipping_idx = None
        
        for i, improvement in enumerate(improvements):
            if improvement < threshold:
                tipping_idx = i + 1  # Index in original array
                break
        
        if tipping_idx:
            tipping_row = part_data.iloc[tipping_idx]
            tipping_points[part_data.iloc[0]['part_size_formatted']] = {
                'chunk_size': tipping_row['chunk_size'],
                'chunk_size_formatted': tipping_row['chunk_size_formatted'],
                'throughput': tipping_row['mean_gbps'],
                'improvement_before': improvements[tipping_idx-1] if tipping_idx > 0 else None
            }
    
    return tipping_points


def generate_sdk_recommendations(optimal_configs: List[Dict], output_dir: Path):
    """Generate SDK code recommendations based on analysis."""
    print("\nGenerating SDK recommendations...")
    
    recommendations = []
    recommendations.append("// Optimal Chunk Size Selection Logic")
    recommendations.append("// Based on benchmark analysis")
    recommendations.append("")
    
    for i, config in enumerate(optimal_configs):
        part_bytes = config['part_size']
        chunk_bytes = config['chunk_size']
        throughput = config['mean_gbps']
        
        if i == 0:
            recommendations.append(f"if (partSize <= {part_bytes}L) // {config['part_size_formatted']}")
        elif i == len(optimal_configs) - 1:
            recommendations.append(f"else // > {optimal_configs[i-1]['part_size_formatted']}")
        else:
            recommendations.append(f"else if (partSize <= {part_bytes}L) // {config['part_size_formatted']}")
        
        recommendations.append(f"{{")
        recommendations.append(f"    chunkSize = {chunk_bytes}; // {config['chunk_size_formatted']} - {throughput:.2f} Gb/s")
        recommendations.append(f"}}")
    
    # Save to file
    output_path = output_dir / 'sdk_recommendations.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(recommendations))
    
    print(f"Saved: {output_path}")
    
    return recommendations


def generate_summary_report(df: pd.DataFrame, optimal_configs: List[Dict], 
                           tipping_points: Dict, output_dir: Path):
    """Generate a text summary report."""
    print("\nGenerating summary report...")
    
    report = []
    report.append("=" * 80)
    report.append("S3 CHUNK SIZE BENCHMARK ANALYSIS REPORT")
    report.append("=" * 80)
    report.append("")
    
    # Overall statistics
    report.append("OVERALL STATISTICS")
    report.append("-" * 80)
    report.append(f"Total configurations tested: {len(df)}")
    report.append(f"Part sizes tested: {len(df['part_size'].unique())}")
    report.append(f"Chunk sizes tested: {len(df['chunk_size'].unique())}")
    report.append(f"Best overall throughput: {df['mean_gbps'].max():.2f} Gb/s")
    report.append(f"Worst overall throughput: {df['mean_gbps'].min():.2f} Gb/s")
    report.append("")
    
    # Optimal configurations
    report.append("OPTIMAL CONFIGURATIONS")
    report.append("-" * 80)
    report.append(f"{'Part Size':<15} {'Optimal Chunk':<15} {'Throughput':<15} {'Std Dev':<15}")
    report.append("-" * 80)
    for config in optimal_configs:
        report.append(f"{config['part_size_formatted']:<15} "
                     f"{config['chunk_size_formatted']:<15} "
                     f"{config['mean_gbps']:.2f} Gb/s{'':<6} "
                     f"±{config['std_gbps']:.2f} Gb/s")
    report.append("")
    
    # Tipping points
    if tipping_points:
        report.append("PERFORMANCE TIPPING POINTS")
        report.append("-" * 80)
        report.append("Points where increasing chunk size shows diminishing returns (<5% improvement)")
        report.append("")
        for part_size, data in tipping_points.items():
            report.append(f"Part Size {part_size}:")
            report.append(f"  Tipping point at chunk size: {data['chunk_size_formatted']}")
            report.append(f"  Throughput: {data['throughput']:.2f} Gb/s")
            if data['improvement_before']:
                report.append(f"  Previous improvement: {data['improvement_before']:.1f}%")
            report.append("")
    
    # Key insights
    report.append("KEY INSIGHTS")
    report.append("-" * 80)
    
    # LOH threshold analysis (85KB)
    loh_threshold = 87040  # 85KB
    below_loh = [c for c in optimal_configs if c['chunk_size'] < loh_threshold]
    above_loh = [c for c in optimal_configs if c['chunk_size'] >= loh_threshold]
    
    report.append(f"1. LOH Threshold Analysis (85KB):")
    report.append(f"   - {len(below_loh)} optimal configs use chunks < 85KB (stay off LOH)")
    report.append(f"   - {len(above_loh)} optimal configs use chunks ≥ 85KB (may trigger LOH)")
    report.append("")
    
    # Throughput range analysis
    throughputs = [c['mean_gbps'] for c in optimal_configs]
    report.append(f"2. Throughput Range:")
    report.append(f"   - Minimum optimal: {min(throughputs):.2f} Gb/s")
    report.append(f"   - Maximum optimal: {max(throughputs):.2f} Gb/s")
    report.append(f"   - Average optimal: {np.mean(throughputs):.2f} Gb/s")
    report.append(f"   - Improvement range: {((max(throughputs) - min(throughputs)) / min(throughputs) * 100):.1f}%")
    report.append("")
    
    report.append("=" * 80)
    
    # Save report
    output_path = output_dir / 'analysis_report.txt'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"Saved: {output_path}")
    
    # Also print to console
    print("\n" + '\n'.join(report))


def main():
    parser = argparse.ArgumentParser(
        description='Analyze S3 chunk size benchmark results',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('csv_file', help='Path to benchmark results CSV file')
    parser.add_argument('--output-dir', default='./analysis', 
                       help='Output directory for generated files (default: ./analysis)')
    
    args = parser.parse_args()
    
    # Validate input file
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir.absolute()}")
    
    try:
        # Load and preprocess data
        df = load_and_preprocess_data(str(csv_path))
        
        # Find optimal configurations
        optimal_configs = find_optimal_configurations(df)
        
        # Detect tipping points
        tipping_points = detect_tipping_points(df)
        
        # Generate visualizations
        create_heatmap(df, output_dir)
        create_line_charts_per_part_size(df, output_dir)
        create_optimal_chunk_chart(optimal_configs, output_dir)
        
        # Generate recommendations and reports
        sdk_recommendations = generate_sdk_recommendations(optimal_configs, output_dir)
        generate_summary_report(df, optimal_configs, tipping_points, output_dir)
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE!")
        print("=" * 80)
        print(f"\nAll outputs saved to: {output_dir.absolute()}")
        print("\nGenerated files:")
        print("  - heatmap_throughput.png")
        print("  - lineplot_per_part_size.png")
        print("  - optimal_chunk_sizes.png")
        print("  - sdk_recommendations.txt")
        print("  - analysis_report.txt")
        
    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
