# PUFForge

**PUFForge** — A Python tool to generate Challenge-Response Pairs (CRPs) for various Physically Unclonable Function (PUF) types using the [pypuf](https://github.com/nils-wisiol/pypuf) library v2.2.0.

```
  ____  ____  ____  ____  ____  ____  ____ 
 |  _ \|  _ \|  _ \|  _ \|  _ \|  _ \|  _ \
 | |_) | |_) | |_) | |_) | |_) | |_) | |_)
 |  __/|  __/|  __/|  __/|  __/|  __/|  __/
 |_|   |_|   |_|   |_|   |_|   |_|   |_|   

   P U F F O R G E
```

Forge your PUF responses with precision.

## Features

- **Generates CRPs for all 10 PUF types** supported by pypuf v2.2.0
- **Two modes of operation:**
  - **Random mode (default)**: Generate random challenges and get PUF responses
  - **User-provided challenges**: Supply your own challenges (via file or CLI) and get responses
- **Configurable response length**: 1-512 bits per PUF type (via multiple independent PUF instances with sequential seeds)
- **128-bit challenges** (fixed)
- **Config-driven** via `config.yml` - no code changes needed
- **Outputs** individual CSV files per PUF type + combined CSV
- **Uses `uv`** for fast dependency management
- **Reproducible**: Same seed + challenge + config = identical output

## Supported PUF Types

| PUF Type | Description | Key Parameters |
|----------|-------------|----------------|
| `arbiter_puf` | Basic Arbiter PUF | `n` (stages) |
| `xor_arbiter_puf` | XOR Arbiter PUF (multiple chains XORed) | `n`, `k` (chains) |
| `lightweight_secure_puf` | Lightweight Secure PUF | `n` |
| `permutation_puf` | Permutation PUF | `n` |
| `interpose_puf` | Interpose PUF (XOR → permutation → XOR) | `n`, `k_down`, `k_up`, `interpose_pos` |
| `feedforward_arbiter_puf` | Feed-Forward Arbiter PUF | `n`, `feedforward_connections` |
| `xor_feedforward_arbiter_puf` | XOR of Feed-Forward Arbiter PUFs | `n`, `k`, `feedforward_connections` |
| `bistable_ring_puf` | Bistable Ring PUF | `n`, `weights` |
| `xor_bistable_ring_puf` | XOR of Bistable Ring PUFs | `n`, `k`, `weights` |
| `random_transformation_puf` | Random Transformation PUF | `n` |

> **Note**: `xor_feedforward_arbiter_puf` has a known pypuf library limitation at response lengths >4 bits (IndexError in feedforward challenge handling). Works correctly at 1-4 bits.

## Installation

```bash
# Clone the repository
git clone https://github.com/TakMashhido/PUFForge.git
cd PUFForge

# Install dependencies with uv
uv sync

# Install the package (optional, for CLI access)
uv pip install -e .
```

After installation, you can run PUFForge via:
```bash
# Using uv
uv run puf-crp-gen

# Or if installed with pip
puf-crp-gen
```

## Configuration (`config.yml`)

The tool is fully configured via `config.yml`. All parameters can be overridden per PUF type.

### Global Settings

```yaml
global:
  num_crp_pairs: 1000          # CRPs per PUF type (random mode only)
  challenge_length: 128        # Challenge length in bits (fixed at 128)
  seed: 42                     # Random seed for reproducibility
  output_dir: "output"         # Output directory for CSV files
  response_length: 1           # Default response length (1-512 bits)
```

### Per-PUF Configuration

Each PUF type has its own section with `enabled`, `response_length`, and type-specific parameters:

```yaml
pufs:
  # Arbiter PUF-based designs
  arbiter_puf:
    enabled: true
    response_length: 1         # Response length in bits (1-512)
    n: 128                     # Challenge length (number of stages)

  xor_arbiter_puf:
    enabled: true
    response_length: 1
    n: 128
    k: 4                       # Number of XOR chains

  lightweight_secure_puf:
    enabled: true
    response_length: 1
    n: 128

  permutation_puf:
    enabled: true
    response_length: 1
    n: 128

  interpose_puf:
    enabled: true
    response_length: 1
    n: 128
    k_down: 2                  # XOR chains before permutation
    k_up: 2                    # XOR chains after permutation
    # interpose_pos: 64       # Optional: interposition position (default: n/2)

  feedforward_arbiter_puf:
    enabled: true
    response_length: 1
    n: 128
    # feedforward_connections: null  # Optional: list of (from, to) tuples, e.g. [[0, 5], [10, 20]]
    # If not provided, generated randomly based on seed

  xor_feedforward_arbiter_puf:
    enabled: true
    response_length: 1
    n: 128
    k: 4
    # feedforward_connections: null  # Optional: list of lists of tuples per chain

  bistable_ring_puf:
    enabled: true
    response_length: 1
    n: 128
    # weights: null              # Optional: array of n+1 weights (generated if not provided)

  xor_bistable_ring_puf:
    enabled: true
    response_length: 1
    n: 128
    k: 4
    # weights: null              # Optional: array of n+1 weights per chain

  random_transformation_puf:
    enabled: true
    response_length: 1
    n: 128
```

### Response Length Details

- **Range**: 1-512 bits
- **Implementation**: Creates `N` independent PUF instances with sequential seeds (`base_seed`, `base_seed+1`, ..., `base_seed+N-1`), evaluates each on the same challenge, concatenates the 1-bit responses into a single binary string
- **Example**: `response_length: 4` with seed `42` → uses seeds 42, 43, 44, 45 → produces 4-bit responses like "1010"
- **Backward compatible**: `response_length: 1` uses the original single-instance logic

## Usage

### Random Mode (Default)

Generate random challenges and responses for all enabled PUFs:

```bash
uv run python -m PUFForge
```

Generate for a specific PUF type:

```bash
uv run python -m PUFForge --puf-type arbiter_puf
```

Generate for multiple specific PUFs (run separately and combine):

```bash
uv run python -m PUFForge --puf-type arbiter_puf
uv run python -m PUFForge --puf-type xor_arbiter_puf
```

### User-Provided Challenges Mode

#### From CSV File

Create a CSV file with a `challenge` column containing 128-bit binary strings:

```csv
challenge
11111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111
000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
10101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010
010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010
```

Run with:

```bash
uv run python -m PUFForge --challenge-file my_challenges.csv
```

For a specific PUF type:

```bash
uv run python -m PUFForge --challenge-file my_challenges.csv --puf-type xor_arbiter_puf
```

#### From Command Line

Pass space-separated 128-bit binary strings:

```bash
uv run python -m PUFForge --challenges "111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111" "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000" "101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010"
```

For a specific PUF type:

```bash
uv run python -m PUFForge --challenges "1111...1111" "0000...0000" --puf-type interpose_puf
```

### Other Options

```bash
# List available PUF types and their enabled status
uv run python -m PUFForge --list-pufs

# Use custom config file
uv run python -m PUFForge --config my_config.yml

# Override output directory
uv run python -m PUFForge --output-dir my_output

# Combine options
uv run python -m PUFForge --config custom.yml --output-dir results --puf-type arbiter_puf --challenge-file challenges.csv
```

## Output

### File Naming

| Mode | Individual Files | Combined File |
|------|------------------|---------------|
| Random | `output/{puf_type}_crps.csv` | `output/all_pufs_crps.csv` |
| User Challenges | `output/{puf_type}_crps_user.csv` | `output/all_pufs_crps.csv` |

### CSV Format

Each CSV contains three columns:

| Column | Description |
|--------|-------------|
| `challenge` | 128-bit binary string (0/1) |
| `response` | Binary string of length `response_length` (1-512 bits) |
| `puf_type` | Name of the PUF type |

### Example Output

**Single-bit response (response_length: 1):**
```csv
challenge,response,puf_type
11111011101000001011000001011111101011010001010001110001100111110010000101000100010011100001001111011000010111100000111101101100,0,arbiter_puf
01010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101,1,arbiter_puf
```

**Multi-bit response (response_length: 8):**
```csv
challenge,response,puf_type
11111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111,10101011,arbiter_puf
0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000,10100001,arbiter_puf
```

**Multi-bit response (response_length: 128):**
```csv
challenge,response,puf_type
11010010101110010100110100110000001101101101101111100111001010011001110001111110011001010110100100111001100001110100111011101011,11000100101101001000100110101101011000011110100000100000100010110111001100100000011010001110111100001001100110100001010010010000,arbiter_puf
```

## Reproducibility

The tool is fully deterministic:

```bash
# Run 1
uv run python -m PUFForge --puf-type arbiter_puf --challenges "1111...1111"
# Output: challenge,response,puf_type
# 1111...1111,1010,arbiter_puf

# Run 2 (same seed, same config)
uv run python -m PUFForge --puf-type arbiter_puf --challenges "1111...1111"
# Output: challenge,response,puf_type
# 1111...1111,1010,arbiter_puf  ← IDENTICAL
```

To get different outputs, change the `seed` in `config.yml` or use a different `config.yml`.

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (for dependency management)

Dependencies (installed via `uv sync`):
- `pypuf>=2.2.0`
- `pyyaml`
- `pandas`
- `numpy`

## Project Structure

```
PUFForge/
├── config.yml              # Configuration file
├── pyproject.toml          # Project metadata and dependencies
├── README.md               # This file
├── LICENSE                 # MIT License
├── PUFForge/          # Main package
│   ├── __init__.py
│   └── __main__.py         # Entry point (puf-crp-gen command)
└── output/                 # Generated CSV files (created at runtime)
```

## Advanced: Custom PUF Parameters

For advanced use cases, you can specify optional parameters in `config.yml`:

### Feed-Forward Connections (Arbiter PUF variants)
```yaml
feedforward_arbiter_puf:
  enabled: true
  n: 128
  feedforward_connections: [[0, 10], [5, 20], [15, 30], [25, 40], [35, 50]]
```

### Bistable Ring Weights
```yaml
bistable_ring_puf:
  enabled: true
  n: 128
  weights: [1.0, 0.8, 1.2, ...]  # Array of 129 floats (n+1)
```

### Interpose Position
```yaml
interpose_puf:
  enabled: true
  n: 128
  k_down: 2
  k_up: 2
  interpose_pos: 64  # Default: n/2
```

If not specified, these are auto-generated based on the global seed for reproducibility.

## Troubleshooting

### Challenge Length Errors
All challenges must be exactly 128 bits. The tool validates this and will error if challenges are shorter/longer.

### xor_feedforward_arbiter_puf Limitations
At `response_length > 4`, this PUF type may fail with an IndexError due to a pypuf library bug in feedforward challenge handling. Use `response_length: 1-4` for this PUF type.

### No PUFs Enabled
If all PUFs are disabled in config, the tool will exit with a message. Enable at least one PUF type.

## License

[MIT](LICENSE)